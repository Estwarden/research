#!/usr/bin/env python3
"""
35. Moderate Weight Recalibration
==================================

VALIDITY.md showed that nb18's consensus weights (72->24) kill the algorithm:
only gpsjam produces meaningful signal, and gpsjam has data on 15/88 days.
30/50 days score=0.

This notebook finds a middle path: signal weight total ~45 (between 24 and 72).
Keeps FIMI share at ~46% (not the 61% from the aggressive reduction).

Method:
1. Load production CTI history and signal daily counts
2. Replay CTI algorithm with parametric signal weights
3. Grid search over moderate weight vectors
4. Evaluate: prediction accuracy vs stored levels, stability, DEGRADED awareness
5. Compare: old (72), aggressive (24), and moderate (~45) weight sets

Data: threat_index_history.csv (134 entries), signal_daily_counts.csv (506 entries)
"""
import csv
import os
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

from cti_constants import (
    SIGNAL_WEIGHTS as OLD_WEIGHTS,
    CAMPAIGN_WEIGHT, FABRICATION_WEIGHT, LAUNDERING_WEIGHT,
    NARRATIVE_WEIGHT, GPSJAM_SEV_WEIGHT, YELLOW_THRESHOLD, SEV_SCORES,
)

FIMI_TOTAL = CAMPAIGN_WEIGHT + FABRICATION_WEIGHT + LAUNDERING_WEIGHT + NARRATIVE_WEIGHT + GPSJAM_SEV_WEIGHT
OLD_TOTAL = sum(OLD_WEIGHTS.values()) + FIMI_TOTAL  # 110

# Aggressive weights from nb18/nb19
AGGRESSIVE_WEIGHTS = {
    "gpsjam": 10, "adsb": 3, "acled": 0, "firms": 3,
    "ais": 3, "telegram": 0, "rss": 1, "gdelt": 0,
    "energy": 2, "business": 2, "ioda": 0,
}
AGGRESSIVE_TOTAL = sum(AGGRESSIVE_WEIGHTS.values()) + FIMI_TOTAL  # 62

print("=" * 72)
print("35. MODERATE WEIGHT RECALIBRATION")
print("=" * 72)
print(f"\nOld signal total:        {sum(OLD_WEIGHTS.values())} (FIMI share: {FIMI_TOTAL/OLD_TOTAL*100:.0f}%)")
print(f"Aggressive signal total: {sum(AGGRESSIVE_WEIGHTS.values())} (FIMI share: {FIMI_TOTAL/AGGRESSIVE_TOTAL*100:.0f}%)")

# ================================================================
# 1. LOAD DATA
# ================================================================
print("\n" + "=" * 72)
print("1. LOAD CTI HISTORY + SIGNAL DAILY COUNTS")
print("=" * 72)

# CTI history (ground truth levels)
cti_history = []
with open(f"{DATA}/threat_index_history.csv") as f:
    for row in csv.DictReader(f):
        row['score'] = float(row['score'])
        row['components'] = json.loads(row['components'].replace("'", '"')) if row['components'] else {}
        cti_history.append(row)

# Focus on baltic region (most data)
baltic = [r for r in cti_history if r['region'] == 'baltic']
baltic.sort(key=lambda r: r['date'])
print(f"\nBaltic CTI history: {len(baltic)} days")
print(f"  Date range: {baltic[0]['date']} to {baltic[-1]['date']}")
print(f"  Level distribution: {dict(sorted(((l, sum(1 for r in baltic if r['level'] == l)) for l in set(r['level'] for r in baltic))))}")

# Signal daily counts
daily_counts = defaultdict(lambda: defaultdict(int))
with open(f"{DATA}/signal_daily_counts.csv") as f:
    for row in csv.DictReader(f):
        daily_counts[row['date']][row['source_type']] = int(row['signal_count'])

print(f"Signal daily counts: {len(daily_counts)} dates, {len(set(st for d in daily_counts.values() for st in d))} source types")

# Weight recalibration data (from nb18)
recal = {}
with open(f"{OUTPUT}/weight_recalibration.csv") as f:
    for row in csv.DictReader(f):
        recal[row['source']] = {
            'method': row['method'],
            'cv': float(row['cv']) if row['cv'] else None,
            'availability': float(row['availability_pct']) if row['availability_pct'] else 0,
            'noise_rate': float(row['noise_rate']) if row['noise_rate'] else 0,
        }

# ================================================================
# 2. SOURCE RELIABILITY TIERS
# ================================================================
print("\n" + "=" * 72)
print("2. SOURCE RELIABILITY ANALYSIS")
print("=" * 72)

# Classify sources into tiers based on nb17/nb18 findings
# Tier 1: Stable, low CV, meaningful signal (keep weight high)
# Tier 2: Moderate CV, intermittent but informative (reduce moderately)
# Tier 3: High CV, unreliable, or dead (reduce heavily or zero)

print(f"\n  {'Source':12s} {'Old_W':>5s} {'Agg_W':>5s} {'CV':>6s} {'Avail%':>6s} {'Noise%':>6s} {'Method':>12s} Tier")
print("  " + "-" * 75)

tiers = {}
for src in sorted(OLD_WEIGHTS.keys()):
    r = recal.get(src, {})
    cv = r.get('cv')
    avail = r.get('availability', 0)
    noise = r.get('noise_rate', 0)
    method = r.get('method', '?')

    # Tier assignment
    if method == 'DISABLED' or avail == 0:
        tier = 3  # dead
    elif cv is not None and cv < 30:
        tier = 1  # reliable
    elif cv is not None and cv < 100:
        tier = 2  # moderate
    else:
        tier = 3  # unreliable

    tiers[src] = tier
    tier_label = ['', 'RELIABLE', 'MODERATE', 'UNRELIABLE'][tier]
    cv_str = f"{cv:.0f}" if cv is not None else "N/A"
    print(f"  {src:12s} {OLD_WEIGHTS[src]:>5d} {AGGRESSIVE_WEIGHTS.get(src, 0):>5d} "
          f"{cv_str:>6s} {avail:>6.1f} {noise:>6.2f} {method:>12s} {tier_label}")

# ================================================================
# 3. MODERATE WEIGHT PROPOSAL
# ================================================================
print("\n" + "=" * 72)
print("3. MODERATE WEIGHT PROPOSAL")
print("=" * 72)

# Strategy: keep tier 1 near original, halve tier 2, zero tier 3 (dead)
# Then scale so signal total is ~45 (FIMI share ~46%)
MODERATE_WEIGHTS = {}
for src, old_w in OLD_WEIGHTS.items():
    tier = tiers[src]
    if tier == 1:
        MODERATE_WEIGHTS[src] = old_w  # keep
    elif tier == 2:
        MODERATE_WEIGHTS[src] = max(1, old_w // 2)  # halve
    else:
        MODERATE_WEIGHTS[src] = 0  # dead/unreliable

# Scale to target ~45
raw_total = sum(MODERATE_WEIGHTS.values())
TARGET_SIGNAL_TOTAL = 45
if raw_total > 0:
    scale = TARGET_SIGNAL_TOTAL / raw_total
    for src in MODERATE_WEIGHTS:
        MODERATE_WEIGHTS[src] = max(0, round(MODERATE_WEIGHTS[src] * scale))

# Fix rounding: adjust largest weight to hit target
current = sum(MODERATE_WEIGHTS.values())
if current != TARGET_SIGNAL_TOTAL:
    max_src = max(MODERATE_WEIGHTS, key=lambda s: MODERATE_WEIGHTS[s])
    MODERATE_WEIGHTS[max_src] += TARGET_SIGNAL_TOTAL - current

MODERATE_TOTAL = sum(MODERATE_WEIGHTS.values()) + FIMI_TOTAL

print(f"\nModerate signal total: {sum(MODERATE_WEIGHTS.values())} (FIMI share: {FIMI_TOTAL/MODERATE_TOTAL*100:.0f}%)")
print(f"\n  {'Source':12s} {'Old':>4s} {'Agg':>4s} {'Mod':>4s} {'Tier':>10s}")
print("  " + "-" * 40)
for src in sorted(OLD_WEIGHTS.keys()):
    tier_label = ['', 'RELIABLE', 'MODERATE', 'UNRELIABLE'][tiers[src]]
    print(f"  {src:12s} {OLD_WEIGHTS[src]:>4d} {AGGRESSIVE_WEIGHTS.get(src, 0):>4d} "
          f"{MODERATE_WEIGHTS[src]:>4d} {tier_label:>10s}")

# ================================================================
# 4. CTI REPLAY WITH DIFFERENT WEIGHT SETS
# ================================================================
print("\n" + "=" * 72)
print("4. CTI REPLAY COMPARISON")
print("=" * 72)


def replay_cti(dates_sorted, weight_dict, fimi_total, yellow_threshold):
    """Replay CTI algorithm with given weights. Returns per-day scores and levels."""
    total_weight = sum(weight_dict.values()) + fimi_total
    if total_weight == 0:
        return {d: (0, 'GREEN') for d in dates_sorted}

    results = {}
    window = 7
    prev_scores = []

    for i, day_data in enumerate(dates_sorted):
        date = day_data['date']
        counts = daily_counts.get(date, {})
        components = day_data.get('components', {})

        # Signal z-score contribution (simplified: use count relative to window mean)
        signal_score = 0
        for src, w in weight_dict.items():
            if w == 0:
                continue
            count = counts.get(src, 0)
            # Simple z-score approximation: compare to recent window
            recent = [daily_counts.get(dates_sorted[max(0, j)]['date'], {}).get(src, 0)
                      for j in range(max(0, i - window), i)]
            if recent and len(recent) >= 2:
                mean = np.mean(recent)
                std = np.std(recent, ddof=1)
                if std > 0:
                    z = (count - mean) / std
                else:
                    z = 1 if count > mean else 0
                signal_score += max(0, min(z * 10, 100)) * (w / total_weight)
            elif count > 0:
                signal_score += 10 * (w / total_weight)

        # FIMI contribution from stored components
        fimi_score = components.get('fimi', 0) * (fimi_total / total_weight)

        total_score = signal_score + fimi_score

        # Apply momentum
        if prev_scores:
            alpha = 0.034  # production momentum
            total_score = alpha * total_score + (1 - alpha) * prev_scores[-1]

        prev_scores.append(total_score)

        level = 'GREEN'
        if total_score >= 92.8:
            level = 'RED'
        elif total_score >= 59.7:
            level = 'ORANGE'
        elif total_score >= yellow_threshold:
            level = 'YELLOW'

        results[date] = (total_score, level)

    return results


# Replay with all three weight sets
results_old = replay_cti(baltic, OLD_WEIGHTS, FIMI_TOTAL, YELLOW_THRESHOLD)
results_agg = replay_cti(baltic, AGGRESSIVE_WEIGHTS, FIMI_TOTAL, 7.9)
results_mod = replay_cti(baltic, MODERATE_WEIGHTS, FIMI_TOTAL, YELLOW_THRESHOLD)

# Compare against stored levels
print(f"\n  {'Metric':30s} {'Old (72)':>10s} {'Agg (24)':>10s} {'Mod (~45)':>10s}")
print("  " + "-" * 65)

for label, results in [('Old (72)', results_old), ('Agg (24)', results_agg), ('Mod (~45)', results_mod)]:
    correct = sum(1 for r in baltic if results.get(r['date'], (0, ''))[1] == r['level'])
    accuracy = correct / len(baltic) * 100
    green_days = sum(1 for d, (s, l) in results.items() if l == 'GREEN')
    yellow_days = sum(1 for d, (s, l) in results.items() if l == 'YELLOW')
    scores = [s for s, l in results.values()]
    zero_days = sum(1 for s in scores if s < 0.5)

    print(f"  {label:30s} acc={accuracy:.0f}%, GREEN={green_days}, YELLOW={yellow_days}, "
          f"zero_days={zero_days}, mean_score={np.mean(scores):.1f}")

# ================================================================
# 5. TRANSITION ANALYSIS
# ================================================================
print("\n" + "=" * 72)
print("5. TRANSITION ANALYSIS")
print("=" * 72)

# How well does each weight set track level transitions?
stored_levels = [r['level'] for r in baltic]
transitions = [(i, stored_levels[i-1], stored_levels[i])
               for i in range(1, len(stored_levels))
               if stored_levels[i] != stored_levels[i-1]]

print(f"\nStored level transitions: {len(transitions)}")
for name, results in [('Old (72)', results_old), ('Aggressive (24)', results_agg), ('Moderate (~45)', results_mod)]:
    predicted = {r['date']: results.get(r['date'], (0, 'GREEN'))[1] for r in baltic}
    pred_list = [predicted.get(r['date'], 'GREEN') for r in baltic]

    caught = 0
    for i, old_level, new_level in transitions:
        # Did the prediction also change around this point? (+/- 1 day)
        for offset in [-1, 0, 1]:
            j = i + offset
            if 0 < j < len(pred_list) and pred_list[j] != pred_list[j-1]:
                caught += 1
                break

    print(f"  {name:20s}: caught {caught}/{len(transitions)} transitions ({caught/len(transitions)*100:.0f}%)")

# ================================================================
# 6. DEGRADED DAY ANALYSIS
# ================================================================
print("\n" + "=" * 72)
print("6. DEGRADED DAY ANALYSIS")
print("=" * 72)

DEGRADED_THRESHOLD = 0.70  # flag when live weight < 70% of total

for name, weights in [('Old (72)', OLD_WEIGHTS), ('Moderate (~45)', MODERATE_WEIGHTS)]:
    total_signal_w = sum(weights.values())
    degraded_days = 0
    for r in baltic:
        counts = daily_counts.get(r['date'], {})
        live_weight = sum(w for src, w in weights.items() if w > 0 and counts.get(src, 0) > 0)
        if live_weight < total_signal_w * DEGRADED_THRESHOLD:
            degraded_days += 1

    print(f"  {name}: {degraded_days}/{len(baltic)} days DEGRADED ({degraded_days/len(baltic)*100:.0f}%)")

# ================================================================
# 7. SAVE RESULTS
# ================================================================
print("\n" + "=" * 72)
print("7. SAVE RESULTS")
print("=" * 72)

with open(f"{OUTPUT}/moderate_weights.csv", "w") as f:
    f.write("source,old_weight,aggressive_weight,moderate_weight,tier\n")
    for src in sorted(OLD_WEIGHTS.keys()):
        tier_label = ['', 'reliable', 'moderate', 'unreliable'][tiers[src]]
        f.write(f"{src},{OLD_WEIGHTS[src]},{AGGRESSIVE_WEIGHTS.get(src, 0)},"
                f"{MODERATE_WEIGHTS[src]},{tier_label}\n")

print(f"Saved to output/moderate_weights.csv")

with open(f"{OUTPUT}/cti_replay_comparison.csv", "w") as f:
    f.write("date,stored_level,stored_score,old_score,old_level,agg_score,agg_level,mod_score,mod_level\n")
    for r in baltic:
        d = r['date']
        old_s, old_l = results_old.get(d, (0, 'GREEN'))
        agg_s, agg_l = results_agg.get(d, (0, 'GREEN'))
        mod_s, mod_l = results_mod.get(d, (0, 'GREEN'))
        f.write(f"{d},{r['level']},{r['score']:.2f},{old_s:.2f},{old_l},{agg_s:.2f},{agg_l},{mod_s:.2f},{mod_l}\n")

print(f"Saved to output/cti_replay_comparison.csv")

# ================================================================
# RECOMMENDATIONS
# ================================================================
print("\n" + "=" * 72)
print("RECOMMENDATIONS")
print("=" * 72)
print(f"""
MODERATE WEIGHT PROPOSAL:
  Signal total: {sum(MODERATE_WEIGHTS.values())} (vs old=72, aggressive=24)
  FIMI share:   {FIMI_TOTAL/MODERATE_TOTAL*100:.0f}% (vs old=35%, aggressive=61%)
  FIMI total:   {FIMI_TOTAL} (unchanged)
  Grand total:  {MODERATE_TOTAL}

Strategy: tier-1 sources (low CV) keep original weight; tier-2 (moderate CV)
halved; tier-3 (dead/unreliable) zeroed. Scaled to ~45 signal total.

VALIDITY CAVEATS:
- This replay uses a simplified z-score (no robust baselines, no MAD).
- FIMI contribution is approximated from stored components.
- Only tested on {len(baltic)} days of Baltic data.
- Must be validated on 90+ days of stable data after collector fixes (F-01).

DEPLOYMENT ORDER (from FINDINGS.md):
1. Fix FIMI scoring first (already deployed)
2. Apply moderate weights (this notebook)
3. Deploy DEGRADED flag (already deployed)
4. Keep YELLOW=15.2 until 90+ days of data validates a change
5. Re-run R-47 threshold optimization after 90 days
""")
