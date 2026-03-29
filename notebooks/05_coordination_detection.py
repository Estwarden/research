#!/usr/bin/env python3
"""
05. Coordination Detection Validation
======================================

Hypothesis: State-media coordinated clusters have statistically different
temporal patterns (burstiness) than organic clusters.

Method: Burstiness parameter B = (CV - 1) / (CV + 1) where
CV = std(inter-arrival gaps) / mean(inter-arrival gaps)

B = -1: perfectly regular (clock-like)
B =  0: Poisson random (organic)
B = +1: maximally bursty (coordinated bursts)

Data: cluster_members.csv from EstWarden prod DB
Ground truth: has_ru_state = contains ru_state/ru_proxy signals

Tests:
1. Welch's t-test: ru_state vs non-ru_state burstiness
2. Confound test: is burstiness correlated with cluster size?
3. Mixed cluster test: do mixed clusters behave like state or clean?
4. Size-controlled test: compare within same size buckets
"""

import csv
import math
import re
import os
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')


def parse_time_minutes(s):
    """Parse timestamp to minutes for gap calculation."""
    m = re.match(r'(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})', str(s))
    if m:
        p = [int(x) for x in m.groups()]
        return p[0] * 525960 + p[1] * 43830 + p[2] * 1440 + p[3] * 60 + p[4]
    return None


def mean(x):
    return sum(x) / len(x) if x else 0


def std(x):
    if len(x) < 2:
        return 0
    m = mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def welch_t(x, y):
    """Welch's t-test for two independent samples."""
    mx, my = mean(x), mean(y)
    sx, sy = std(x), std(y)
    nx, ny = len(x), len(y)
    if sx == 0 and sy == 0:
        return 0
    se = math.sqrt(sx ** 2 / nx + sy ** 2 / ny)
    return (mx - my) / se if se > 0 else 0


def cohens_d(x, y):
    """Effect size."""
    pooled = math.sqrt((std(x) ** 2 + std(y) ** 2) / 2)
    return (mean(x) - mean(y)) / pooled if pooled > 0 else 0


def compute_burstiness(times):
    """Compute burstiness from sorted list of times."""
    gaps = [times[i + 1] - times[i] for i in range(len(times) - 1)]
    gaps = [g for g in gaps if g > 0]
    if len(gaps) < 3:
        return None
    m, s = mean(gaps), std(gaps)
    if m == 0:
        return None
    cv = s / m
    return (cv - 1) / (cv + 1)


def load_clusters():
    """Load cluster data with burstiness features."""
    clusters = defaultdict(list)
    path = os.path.join(DATA_DIR, 'cluster_members.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            cid = row.get('cluster_id', '')
            ts = row.get('signal_time', '') or ''
            cat = row.get('signal_category', '') or ''
            t = parse_time_minutes(ts)
            if cid and t:
                clusters[cid].append({'time': t, 'category': cat})

    results = []
    for cid, sigs in clusters.items():
        if len(sigs) < 6:
            continue
        times = sorted(s['time'] for s in sigs)
        b = compute_burstiness(times)
        if b is None:
            continue

        cats = set(s['category'] for s in sigs if s['category'])
        has_ru_state = any('state' in c or 'ru_proxy' in c for c in cats)
        only_state = all('state' in c or 'ru_proxy' in c for c in cats if c)
        has_mixed = has_ru_state and not only_state

        results.append({
            'cid': cid,
            'n': len(sigs),
            'burstiness': b,
            'n_cats': len(cats),
            'has_ru_state': has_ru_state,
            'only_state': only_state,
            'has_mixed': has_mixed,
            'clean': not has_ru_state,
        })
    return results


def main():
    results = load_clusters()
    state = [r for r in results if r['has_ru_state']]
    clean = [r for r in results if r['clean']]

    sb = [r['burstiness'] for r in state]
    cb = [r['burstiness'] for r in clean]

    print("=" * 70)
    print("TEST 1: Welch's t-test — State vs Clean Burstiness")
    print("=" * 70)
    t = welch_t(sb, cb)
    d = cohens_d(sb, cb)
    print(f"  State (n={len(sb)}): B = {mean(sb):.4f} ± {std(sb):.4f}")
    print(f"  Clean (n={len(cb)}): B = {mean(cb):.4f} ± {std(cb):.4f}")
    print(f"  t = {t:.4f}")
    print(f"  |t| = {abs(t):.2f} → p {'< 0.001' if abs(t) > 3.29 else '< 0.01' if abs(t) > 2.58 else '< 0.05' if abs(t) > 1.96 else '> 0.05 (NOT SIGNIFICANT)'}")
    print(f"  Cohen's d = {d:.2f} ({'large' if abs(d) > 0.8 else 'medium' if abs(d) > 0.5 else 'small'})")

    print()
    print("=" * 70)
    print("TEST 2: Confound — Burstiness vs Cluster Size")
    print("=" * 70)
    sizes = [r['n'] for r in results]
    bursts = [r['burstiness'] for r in results]
    mx, my = mean(sizes), mean(bursts)
    num = sum((x - mx) * (y - my) for x, y in zip(sizes, bursts))
    dx = math.sqrt(sum((x - mx) ** 2 for x in sizes))
    dy = math.sqrt(sum((y - my) ** 2 for y in bursts))
    r_size = num / (dx * dy) if dx > 0 and dy > 0 else 0
    print(f"  Pearson r = {r_size:.3f}")
    print(f"  {'⚠️ CONFOUNDED' if abs(r_size) > 0.3 else '✅ INDEPENDENT'}")

    print()
    print("=" * 70)
    print("TEST 3: Mixed Clusters — Who Drives Burstiness?")
    print("=" * 70)
    mixed = [r for r in results if r['has_mixed']]
    only_s = [r for r in results if r['only_state']]
    mb = mean([r['burstiness'] for r in mixed]) if mixed else 0
    ob = mean([r['burstiness'] for r in only_s]) if only_s else 0
    clb = mean(cb)
    print(f"  Mixed (state+clean, n={len(mixed)}): B = {mb:.4f}")
    print(f"  Only-state (n={len(only_s)}):         B = {ob:.4f}")
    print(f"  Clean-only (n={len(clean)}):           B = {clb:.4f}")
    if abs(mb - clb) < abs(mb - ob):
        print(f"  → Mixed closer to CLEAN → burstiness may be event-driven ⚠️")
    else:
        print(f"  → Mixed closer to STATE → Russian state media DRIVES burstiness ✅")

    print()
    print("=" * 70)
    print("TEST 4: Size-Controlled Comparison")
    print("=" * 70)
    for lo, hi in [(6, 8), (8, 12), (12, 20)]:
        s_bucket = [r['burstiness'] for r in state if lo <= r['n'] < hi]
        c_bucket = [r['burstiness'] for r in clean if lo <= r['n'] < hi]
        if s_bucket and c_bucket:
            diff = mean(s_bucket) - mean(c_bucket)
            print(f"  Size {lo}-{hi}: state B={mean(s_bucket):.3f} (n={len(s_bucket)}), "
                  f"clean B={mean(c_bucket):.3f} (n={len(c_bucket)}), "
                  f"diff={diff:+.3f} {'✅' if diff > 0.05 else '⚠️'}")

    print()
    print("=" * 70)
    print("VERDICT")
    print("=" * 70)
    if abs(t) > 2.58 and abs(r_size) < 0.3:
        print("✅ VALIDATED: Burstiness is a statistically significant, confound-free")
        print("   signal for Russian state media coordination detection.")
    elif abs(t) > 1.96:
        print("🟡 PARTIALLY VALIDATED: Signal is significant but needs more data.")
    else:
        print("❌ NOT VALIDATED: Burstiness does not separate state from clean.")


if __name__ == '__main__':
    main()
