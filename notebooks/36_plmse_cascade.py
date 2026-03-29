#!/usr/bin/env python3
"""
36. PLMSE Cascade Shape Metric
===============================

Implements the Power Law MSE (PLMSE) metric from "Signals of Propaganda"
(PLOS ONE, 2025). PLMSE measures how well a cascade's temporal shape fits
a power-law distribution. Political manipulation cascades have LOWER PLMSE
(closer to power-law) than organic cascades, with p=0.0001 discrimination.

Method:
1. For each cluster with >= 5 signals, extract inter-arrival times
2. Fit power-law CDF to the cumulative signal count curve
3. Compute MSE of fit (PLMSE)
4. Compare distributions: hostile-labeled vs clean vs all clusters

Lower PLMSE = more power-law-like = more likely coordinated/political.

Data: cluster_members.csv (7,587 signals in 2,278 clusters)
Labels: cluster_framings.csv (30 framing analyses, ~10 hostile)
"""
import csv
import os
import math
import json
from collections import defaultdict
from datetime import datetime

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

# ================================================================
# 1. LOAD CLUSTER TEMPORAL DATA
# ================================================================
print("=" * 72)
print("36. PLMSE CASCADE SHAPE METRIC")
print("=" * 72)

# Load cluster members and extract timestamps per cluster
clusters = defaultdict(list)
with open(f"{DATA}/cluster_members.csv") as f:
    for row in csv.DictReader(f):
        try:
            ts = datetime.fromisoformat(row['published_at'].replace('+00', '+00:00'))
            clusters[int(row['cluster_id'])].append(ts)
        except (ValueError, KeyError):
            continue

# Sort timestamps within each cluster
for cid in clusters:
    clusters[cid].sort()

total_clusters = len(clusters)
print(f"\nLoaded {total_clusters} clusters")
print(f"Size distribution:")
sizes = [len(v) for v in clusters.values()]
for threshold in [1, 2, 3, 5, 10, 15, 20]:
    count = sum(1 for s in sizes if s >= threshold)
    print(f"  >= {threshold:2d} signals: {count:5d} clusters ({count/total_clusters*100:.1f}%)")

# ================================================================
# 2. PLMSE COMPUTATION
# ================================================================
print("\n" + "=" * 72)
print("2. PLMSE COMPUTATION")
print("=" * 72)

MIN_SIGNALS = 5  # need enough points for a meaningful fit


def compute_plmse(timestamps):
    """
    Compute Power Law MSE for a cascade's temporal profile.

    1. Normalize timestamps to [0, 1] range (first signal = 0, last = 1)
    2. Build empirical CDF: y[i] = i / N
    3. Fit power-law CDF: y = x^alpha via least squares on log-log
    4. PLMSE = mean squared error between empirical and fitted CDF

    Returns (plmse, alpha, n_signals) or None if insufficient data.
    """
    n = len(timestamps)
    if n < MIN_SIGNALS:
        return None

    # Normalize to [0, 1]
    t0 = timestamps[0].timestamp()
    t_end = timestamps[-1].timestamp()
    span = t_end - t0
    if span <= 0:
        return None  # all signals at same time

    x = np.array([(t.timestamp() - t0) / span for t in timestamps])
    y_empirical = np.arange(1, n + 1) / n  # empirical CDF

    # Remove x=0 (first point) for log fitting
    mask = x > 0
    if mask.sum() < 3:
        return None

    x_fit = x[mask]
    y_fit = y_empirical[mask]

    # Fit power law: y = x^alpha => log(y) = alpha * log(x)
    log_x = np.log(x_fit)
    log_y = np.log(y_fit)

    # Least squares: alpha = sum(log_x * log_y) / sum(log_x^2)
    denom = np.dot(log_x, log_x)
    if denom == 0 or not np.isfinite(denom):
        return None
    alpha = np.dot(log_x, log_y) / denom
    if not np.isfinite(alpha):
        return None

    # Compute fitted CDF and MSE
    y_fitted = x_fit ** alpha
    mse = np.mean((y_fit - y_fitted) ** 2)

    return (mse, alpha, n)


# Compute PLMSE for all qualifying clusters
results = {}
for cid, timestamps in clusters.items():
    r = compute_plmse(timestamps)
    if r is not None:
        results[cid] = {'plmse': r[0], 'alpha': r[1], 'n_signals': r[2]}

print(f"\nComputed PLMSE for {len(results)} clusters (>= {MIN_SIGNALS} signals)")
print(f"Skipped: {total_clusters - len(results)} (too few signals or zero time span)")

plmse_values = [r['plmse'] for r in results.values()]
alphas = [r['alpha'] for r in results.values()]

print(f"\nPLMSE distribution (all clusters):")
print(f"  Mean:   {np.mean(plmse_values):.6f}")
print(f"  Median: {np.median(plmse_values):.6f}")
print(f"  Std:    {np.std(plmse_values):.6f}")
print(f"  P10:    {np.percentile(plmse_values, 10):.6f}")
print(f"  P25:    {np.percentile(plmse_values, 25):.6f}")
print(f"  P75:    {np.percentile(plmse_values, 75):.6f}")
print(f"  P90:    {np.percentile(plmse_values, 90):.6f}")

print(f"\nAlpha (power-law exponent) distribution:")
print(f"  Mean:   {np.mean(alphas):.4f}")
print(f"  Median: {np.median(alphas):.4f}")
print(f"  Std:    {np.std(alphas):.4f}")

# ================================================================
# 3. HOSTILE vs CLEAN COMPARISON
# ================================================================
print("\n" + "=" * 72)
print("3. HOSTILE vs CLEAN COMPARISON")
print("=" * 72)

# Load framing labels
framings = {}
with open(f"{DATA}/cluster_framings.csv") as f:
    for row in csv.DictReader(f):
        cid = int(row['cluster_id'])
        framings[cid] = row['is_hostile'] == 't'

hostile_plmse = [results[cid]['plmse'] for cid in framings if framings[cid] and cid in results]
clean_plmse = [results[cid]['plmse'] for cid in framings if not framings[cid] and cid in results]

print(f"\nLabeled clusters with PLMSE data:")
print(f"  Hostile: {len(hostile_plmse)}")
print(f"  Clean:   {len(clean_plmse)}")

if hostile_plmse and clean_plmse:
    print(f"\nHostile PLMSE: mean={np.mean(hostile_plmse):.6f}, median={np.median(hostile_plmse):.6f}")
    print(f"Clean PLMSE:   mean={np.mean(clean_plmse):.6f}, median={np.median(clean_plmse):.6f}")

    # Welch's t-test
    n_h, n_c = len(hostile_plmse), len(clean_plmse)
    m_h, m_c = np.mean(hostile_plmse), np.mean(clean_plmse)
    v_h, v_c = np.var(hostile_plmse, ddof=1), np.var(clean_plmse, ddof=1)

    if v_h > 0 or v_c > 0:
        se = math.sqrt(v_h / n_h + v_c / n_c) if (v_h / n_h + v_c / n_c) > 0 else 1e-10
        t_stat = (m_h - m_c) / se

        # Welch-Satterthwaite degrees of freedom
        num = (v_h / n_h + v_c / n_c) ** 2
        denom = ((v_h / n_h) ** 2 / (n_h - 1) if n_h > 1 else 0) + \
                ((v_c / n_c) ** 2 / (n_c - 1) if n_c > 1 else 0)
        df = num / denom if denom > 0 else 1

        print(f"\n  Welch's t = {t_stat:.4f}, df = {df:.1f}")
        print(f"  Direction: hostile {'<' if m_h < m_c else '>'} clean")

        # Cohen's d
        pooled_std = math.sqrt((v_h + v_c) / 2) if (v_h + v_c) > 0 else 1e-10
        d = (m_h - m_c) / pooled_std
        print(f"  Cohen's d = {d:.4f}")

        if m_h < m_c:
            print("\n  ✓ Hostile cascades have LOWER PLMSE (more power-law-like)")
            print("    This is consistent with the 'Signals of Propaganda' finding:")
            print("    coordinated political cascades follow power-law temporal patterns.")
        else:
            print("\n  ✗ Hostile cascades have HIGHER PLMSE (less power-law-like)")
            print("    This contradicts the paper's prediction. Possible reasons:")
            print("    - Small sample size, - Different definition of 'hostile',")
            print("    - EstWarden cascades structurally different from Twitter cascades")
    else:
        print("\n  Zero variance in one or both groups -- cannot compute t-test")
else:
    print("\n  Insufficient labeled data for comparison.")
    print("  Need framing analyses with PLMSE-eligible clusters (>= 5 signals).")

# ================================================================
# 4. CAMPAIGN-LEVEL ANALYSIS
# ================================================================
print("\n" + "=" * 72)
print("4. CAMPAIGN-LEVEL ANALYSIS")
print("=" * 72)

campaigns = []
with open(f"{DATA}/campaigns_full.csv") as f:
    for row in csv.DictReader(f):
        campaigns.append(row)

# Map campaign cluster_ids to PLMSE
campaign_plmse = []
for c in campaigns:
    cid_str = c.get('cluster_id', '').strip()
    if cid_str:
        try:
            cid = int(cid_str)
            if cid in results:
                campaign_plmse.append({
                    'campaign_id': c['id'],
                    'name': c['name'][:60],
                    'severity': c['severity'],
                    'detection_method': c.get('detection_method', ''),
                    'plmse': results[cid]['plmse'],
                    'alpha': results[cid]['alpha'],
                    'n_signals': results[cid]['n_signals'],
                })
        except ValueError:
            pass

print(f"\nCampaigns with cluster-level PLMSE: {len(campaign_plmse)} / {len(campaigns)}")
if campaign_plmse:
    print(f"\n  {'ID':>4s} {'Sev':>6s} {'Method':>16s} {'PLMSE':>10s} {'Alpha':>6s} {'N':>4s} Name")
    print("  " + "-" * 100)
    for cp in sorted(campaign_plmse, key=lambda x: x['plmse']):
        print(f"  {cp['campaign_id']:>4s} {cp['severity']:>6s} {cp['detection_method']:>16s} "
              f"{cp['plmse']:>10.6f} {cp['alpha']:>6.2f} {cp['n_signals']:>4d} {cp['name']}")

# ================================================================
# 5. PLMSE PERCENTILE RANKING
# ================================================================
print("\n" + "=" * 72)
print("5. PLMSE PERCENTILE RANKING — LOWEST (most power-law) CLUSTERS")
print("=" * 72)

# Load cluster metadata for context
cluster_meta = {}
with open(f"{DATA}/clusters.csv") as f:
    for row in csv.DictReader(f):
        cluster_meta[int(row['id'])] = row

sorted_by_plmse = sorted(results.items(), key=lambda x: x[1]['plmse'])
print(f"\nTop 20 most power-law-like cascades (lowest PLMSE):")
print(f"  {'Rank':>4s} {'CID':>6s} {'PLMSE':>10s} {'Alpha':>6s} {'N':>4s} {'State':>5s} {'Trust':>5s} Summary")
print("  " + "-" * 100)
for i, (cid, r) in enumerate(sorted_by_plmse[:20]):
    meta = cluster_meta.get(cid, {})
    has_state = 't' if meta.get('has_state') == 't' else ''
    has_trust = 't' if meta.get('has_trusted') == 't' else ''
    summary = (meta.get('event_summary') or '')[:50]
    print(f"  {i+1:>4d} {cid:>6d} {r['plmse']:>10.6f} {r['alpha']:>6.2f} {r['n_signals']:>4d} "
          f"{has_state:>5s} {has_trust:>5s} {summary}")

# ================================================================
# 6. CORRELATION WITH STATE MEDIA PRESENCE
# ================================================================
print("\n" + "=" * 72)
print("6. CORRELATION: PLMSE vs STATE MEDIA PRESENCE")
print("=" * 72)

state_plmse = []
nostate_plmse = []
for cid, r in results.items():
    meta = cluster_meta.get(cid, {})
    if meta.get('has_state') == 't':
        state_plmse.append(r['plmse'])
    else:
        nostate_plmse.append(r['plmse'])

print(f"\nClusters with state media:    {len(state_plmse):>5d}, PLMSE mean={np.mean(state_plmse):.6f}, median={np.median(state_plmse):.6f}")
print(f"Clusters without state media: {len(nostate_plmse):>5d}, PLMSE mean={np.mean(nostate_plmse):.6f}, median={np.median(nostate_plmse):.6f}")

if state_plmse and nostate_plmse:
    n_s, n_n = len(state_plmse), len(nostate_plmse)
    m_s, m_n = np.mean(state_plmse), np.mean(nostate_plmse)
    v_s, v_n = np.var(state_plmse, ddof=1), np.var(nostate_plmse, ddof=1)
    se = math.sqrt(v_s / n_s + v_n / n_n)
    t_stat = (m_s - m_n) / se if se > 0 else 0

    print(f"\n  Welch's t = {t_stat:.4f}")
    print(f"  Direction: state media clusters {'more' if m_s < m_n else 'less'} power-law-like")

# ================================================================
# 7. SAVE RESULTS
# ================================================================
print("\n" + "=" * 72)
print("7. SAVE RESULTS")
print("=" * 72)

with open(f"{OUTPUT}/plmse_scores.csv", "w") as f:
    f.write("cluster_id,plmse,alpha,n_signals,has_state,has_trusted,is_hostile\n")
    for cid, r in sorted(results.items()):
        meta = cluster_meta.get(cid, {})
        hostile = framings.get(cid, '')
        hostile_str = 't' if hostile is True else ('f' if hostile is False else '')
        f.write(f"{cid},{r['plmse']:.8f},{r['alpha']:.4f},{r['n_signals']},"
                f"{meta.get('has_state', '')},{meta.get('has_trusted', '')},{hostile_str}\n")

print(f"Saved {len(results)} PLMSE scores to output/plmse_scores.csv")

# Summary
print("\n" + "=" * 72)
print("SUMMARY")
print("=" * 72)
print(f"""
Computed PLMSE for {len(results)} clusters (>= {MIN_SIGNALS} signals).
Hostile-labeled: {len(hostile_plmse)}, Clean-labeled: {len(clean_plmse)}.

PLMSE measures how well a cascade's temporal shape fits a power law.
Lower PLMSE = more power-law-like = more likely coordinated/political
(per "Signals of Propaganda", PLOS ONE 2025, p=0.0001).

NEXT STEPS:
1. Cross-reference with Fisher pre-screen: does PLMSE improve discrimination?
2. Use PLMSE as a feature in the campaign detection pipeline (zero-cost, no LLM).
3. Accumulate more hostile-labeled clusters (currently N={len(hostile_plmse)}) for
   statistical validation.
4. Test at different MIN_SIGNALS thresholds (3, 5, 10) for sensitivity.
""")
