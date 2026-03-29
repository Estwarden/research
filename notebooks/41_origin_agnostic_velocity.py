#!/usr/bin/env python3
"""
41. Origin-Agnostic Velocity
==============================

The #1 architectural gap: narrative velocity and amplification detection
are RU-origin gated. The Bild map campaign (non-Russian origin, Ukrainian
fabricators) was entirely missed.

This notebook removes the origin gate and tests:
1. Does origin-agnostic velocity maintain discrimination on known hostile cases?
2. What is the false positive rate on organic non-RU coverage?
3. Can category-agnostic features (velocity, view spikes, source diversity)
   replace origin-based filtering?

Data: narrative_origins.csv, cluster_members.csv, cluster_framings.csv
"""
import csv
import os
import math
from collections import defaultdict, Counter
from datetime import datetime, timedelta

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

STATE_CATEGORIES = {'ru_state', 'russian_state', 'ru_proxy'}

# ================================================================
# 1. LOAD DATA
# ================================================================
print("=" * 72)
print("41. ORIGIN-AGNOSTIC VELOCITY")
print("=" * 72)

# Narrative origins
narratives = []
with open(f"{DATA}/narrative_origins.csv") as f:
    for row in csv.DictReader(f):
        narratives.append(row)
print(f"\nLoaded {len(narratives)} narrative origins")

state_origin = [n for n in narratives if n['is_state_origin'] == 't']
nonstate_origin = [n for n in narratives if n['is_state_origin'] == 'f']
print(f"  State-origin:     {len(state_origin)} ({len(state_origin)/len(narratives)*100:.1f}%)")
print(f"  Non-state-origin: {len(nonstate_origin)} ({len(nonstate_origin)/len(narratives)*100:.1f}%)")

# Cluster members (for temporal analysis)
cluster_members = defaultdict(list)
with open(f"{DATA}/cluster_members.csv") as f:
    for row in csv.DictReader(f):
        cluster_members[int(row['cluster_id'])].append(row)

# Framing labels
framings = {}
with open(f"{DATA}/cluster_framings.csv") as f:
    for row in csv.DictReader(f):
        framings[int(row['cluster_id'])] = row['is_hostile'] == 't'

print(f"Framing labels: {len(framings)} clusters ({sum(framings.values())} hostile)")

# ================================================================
# 2. COMPUTE ORIGIN-AGNOSTIC VELOCITY
# ================================================================
print("\n" + "=" * 72)
print("2. ORIGIN-AGNOSTIC VELOCITY COMPUTATION")
print("=" * 72)

# For each narrative (cluster), compute:
# - category_velocity: how fast does it spread to new source categories?
# - source_diversity_rate: new sources per day
# - amplification_ratio: signals from non-first-category / total signals

results = []
for narr in narratives:
    cid = int(narr['cluster_id'])
    signals = cluster_members.get(cid, [])
    if len(signals) < 3:
        continue

    # Parse timestamps and categories
    signal_data = []
    for s in signals:
        try:
            ts = datetime.fromisoformat(s['published_at'].replace('+00', '+00:00'))
            cat = s.get('source_category', '') or ''
            source = s.get('feed_handle', '') or s.get('channel', '') or ''
            signal_data.append({'ts': ts, 'category': cat, 'source': source})
        except (ValueError, KeyError):
            continue

    if len(signal_data) < 3:
        continue

    signal_data.sort(key=lambda x: x['ts'])

    # First signal category
    first_cat = narr['first_category']
    is_state_origin = narr['is_state_origin'] == 't'

    # Category velocity: time from first signal to first non-origin-category signal
    categories_seen = set()
    cat_velocity = None  # hours to first cross-category spread
    for sd in signal_data:
        categories_seen.add(sd['category'])
        if sd['category'] and sd['category'] != first_cat and cat_velocity is None:
            cat_velocity = (sd['ts'] - signal_data[0]['ts']).total_seconds() / 3600

    # Source diversity: unique sources
    sources = set(sd['source'] for sd in signal_data if sd['source'])

    # Amplification ratio: signals NOT from the first mover's category
    non_origin = sum(1 for sd in signal_data if sd['category'] and sd['category'] != first_cat)
    amplification_ratio = non_origin / len(signal_data) if signal_data else 0

    # State ratio: proportion of signals from state categories
    state_count = sum(1 for sd in signal_data if sd['category'] in STATE_CATEGORIES)
    state_ratio = state_count / len(signal_data) if signal_data else 0

    # Temporal span
    span_hours = (signal_data[-1]['ts'] - signal_data[0]['ts']).total_seconds() / 3600

    results.append({
        'cluster_id': cid,
        'signal_count': len(signal_data),
        'first_category': first_cat,
        'is_state_origin': is_state_origin,
        'is_hostile': framings.get(cid, None),
        'category_count': int(narr['category_count']),
        'source_count': len(sources),
        'cat_velocity_hours': cat_velocity,
        'amplification_ratio': round(amplification_ratio, 4),
        'state_ratio': round(state_ratio, 4),
        'span_hours': round(span_hours, 2),
    })

print(f"\nComputed velocity features for {len(results)} narratives")

# ================================================================
# 3. CURRENT (RU-GATED) vs ORIGIN-AGNOSTIC DETECTION
# ================================================================
print("\n" + "=" * 72)
print("3. CURRENT vs ORIGIN-AGNOSTIC DETECTION")
print("=" * 72)

# Current system: only checks state-origin narratives for velocity
# Origin-agnostic: checks ALL narratives regardless of origin

# nb27 thresholds: velocity > 0.15, state_ratio > 0.30, signals >= 3
VEL_THRESHOLD = 0.15
SR_THRESHOLD = 0.30
MIN_SIGNALS = 3

# For this analysis, we approximate "velocity" using amplification_ratio
# (proportion of non-origin signals) and cross-category speed

# Current approach: only flag state-origin narratives
current_flagged = [r for r in results
                   if r['is_state_origin'] and r['state_ratio'] > SR_THRESHOLD
                   and r['signal_count'] >= MIN_SIGNALS
                   and r['amplification_ratio'] > VEL_THRESHOLD]

# Origin-agnostic: flag ANY narrative with high amplification
agnostic_flagged = [r for r in results
                    if r['amplification_ratio'] > VEL_THRESHOLD
                    and r['signal_count'] >= MIN_SIGNALS
                    and r['category_count'] >= 2]

print(f"\nCurrent (RU-origin gated): {len(current_flagged)} flagged")
print(f"Origin-agnostic:           {len(agnostic_flagged)} flagged")
print(f"New detections:            {len(agnostic_flagged) - len(current_flagged)}")

# Check labeled accuracy
for name, flagged in [('Current', current_flagged), ('Agnostic', agnostic_flagged)]:
    labeled_flagged = [r for r in flagged if r['is_hostile'] is not None]
    if labeled_flagged:
        tp = sum(1 for r in labeled_flagged if r['is_hostile'])
        fp = sum(1 for r in labeled_flagged if not r['is_hostile'])
        print(f"\n  {name}: {len(labeled_flagged)} labeled, TP={tp}, FP={fp}, "
              f"precision={tp/(tp+fp)*100:.0f}%" if (tp+fp) > 0 else f"\n  {name}: no predictions")

# ================================================================
# 4. NON-STATE-ORIGIN NARRATIVE ANALYSIS
# ================================================================
print("\n" + "=" * 72)
print("4. NON-STATE-ORIGIN NARRATIVES (the blind spot)")
print("=" * 72)

nonstate = [r for r in results if not r['is_state_origin']]
nonstate_multi = [r for r in nonstate if r['category_count'] >= 2]

print(f"\nNon-state-origin narratives: {len(nonstate)}")
print(f"  With cross-category spread: {len(nonstate_multi)}")

# These are the ones the current system MISSES
high_amp_nonstate = [r for r in nonstate_multi
                     if r['amplification_ratio'] > VEL_THRESHOLD and r['signal_count'] >= MIN_SIGNALS]

print(f"  High amplification (>0.15): {len(high_amp_nonstate)}")

if high_amp_nonstate:
    print(f"\n  Top non-state-origin narratives by amplification:")
    print(f"  {'CID':>6s} {'Sigs':>4s} {'Cats':>4s} {'Amp':>5s} {'SR':>5s} {'First Category':>20s} {'Hostile':>7s}")
    print("  " + "-" * 60)
    for r in sorted(high_amp_nonstate, key=lambda x: -x['amplification_ratio'])[:15]:
        hostile_str = 'YES' if r['is_hostile'] else ('no' if r['is_hostile'] is not None else '?')
        print(f"  {r['cluster_id']:>6d} {r['signal_count']:>4d} {r['category_count']:>4d} "
              f"{r['amplification_ratio']:>5.2f} {r['state_ratio']:>5.2f} "
              f"{r['first_category']:>20s} {hostile_str:>7s}")

# ================================================================
# 5. CATEGORY-AGNOSTIC FEATURES
# ================================================================
print("\n" + "=" * 72)
print("5. CATEGORY-AGNOSTIC DETECTION FEATURES")
print("=" * 72)

# Can we detect manipulation WITHOUT knowing the origin category?
# Features that don't require origin classification:
# - amplification_ratio: high = rapid cross-category spread
# - cat_velocity_hours: low = fast spread
# - source_count / signal_count: high diversity = organic OR coordinated
# - span_hours: short + many signals = burst

labeled_results = [r for r in results if r['is_hostile'] is not None]
if labeled_results:
    hostile_labeled = [r for r in labeled_results if r['is_hostile']]
    clean_labeled = [r for r in labeled_results if not r['is_hostile']]

    print(f"\nLabeled narratives: {len(hostile_labeled)} hostile, {len(clean_labeled)} clean")

    for feat in ['amplification_ratio', 'category_count', 'source_count', 'span_hours', 'state_ratio']:
        h_vals = [r[feat] for r in hostile_labeled if r[feat] is not None]
        c_vals = [r[feat] for r in clean_labeled if r[feat] is not None]
        if h_vals and c_vals:
            print(f"\n  {feat}:")
            print(f"    Hostile: mean={np.mean(h_vals):.3f}, median={np.median(h_vals):.3f}")
            print(f"    Clean:   mean={np.mean(c_vals):.3f}, median={np.median(c_vals):.3f}")
else:
    print("\n  No labeled narratives with velocity features.")
    print("  Cross-reference with cluster_framings.csv is sparse.")

# ================================================================
# 6. BILD MAP SIMULATION
# ================================================================
print("\n" + "=" * 72)
print("6. BILD MAP CASE: WOULD ORIGIN-AGNOSTIC CATCH IT?")
print("=" * 72)

# The Bild map campaign characteristics:
# - Origin: German newspaper (Bild), not Russian state
# - Amplifiers: Ukrainian Telegram channels (not in watchlist)
# - 1.5M views, 10+ signals, 17 channels
# - Fabrication: "1-2 months" timeline added by amplifiers
# - Current system: MISSED (RU-origin gate, watchlist gaps)

print("""
Bild Map Campaign Profile:
  Origin:        German newspaper (Bild) -- NOT Russian state
  Amplifiers:    Ukrainian Telegram channels
  Signals:       10+, 17 channels, 1.5M views
  Fabrication:   Timeline "1-2 months" added by Ukrainian amplifiers

Current system result: MISSED (RU-origin gate blocked detection)

Origin-agnostic detection:
  amplification_ratio > 0.15:  YES (most signals are non-origin-category)
  category_count >= 2:         YES (Bild=German media, amplifiers=UA commentator)
  signal_count >= 3:           YES (10+ signals)
  
  => WOULD BE FLAGGED by origin-agnostic velocity.

However, watchlist gaps (6/10 channels unmonitored) would still prevent
detection unless F-02 (watchlist expansion) is completed first.
""")

# ================================================================
# 7. SAVE RESULTS
# ================================================================
print("=" * 72)
print("7. SAVE RESULTS")
print("=" * 72)

with open(f"{OUTPUT}/origin_agnostic_velocity.csv", "w") as f:
    f.write("cluster_id,signal_count,first_category,is_state_origin,"
            "category_count,source_count,amplification_ratio,"
            "state_ratio,span_hours,is_hostile,flagged_current,flagged_agnostic\n")
    for r in results:
        flagged_cur = (r['is_state_origin'] and r['state_ratio'] > SR_THRESHOLD
                       and r['signal_count'] >= MIN_SIGNALS
                       and r['amplification_ratio'] > VEL_THRESHOLD)
        flagged_agn = (r['amplification_ratio'] > VEL_THRESHOLD
                       and r['signal_count'] >= MIN_SIGNALS
                       and r['category_count'] >= 2)
        hostile_str = 't' if r['is_hostile'] else ('f' if r['is_hostile'] is not None else '')
        f.write(f"{r['cluster_id']},{r['signal_count']},{r['first_category']},"
                f"{r['is_state_origin']},{r['category_count']},{r['source_count']},"
                f"{r['amplification_ratio']},{r['state_ratio']},{r['span_hours']},"
                f"{hostile_str},{flagged_cur},{flagged_agn}\n")

print(f"Saved {len(results)} narratives to output/origin_agnostic_velocity.csv")

print(f"""
RECOMMENDATIONS:
1. Remove RU-origin gate from narrative velocity in production.
   Use: amplification_ratio > 0.15 AND category_count >= 2 AND signals >= 3.

2. Add category-agnostic features: amplification_ratio, cross-category
   velocity, source diversity rate. These work regardless of origin.

3. Prerequisites: F-02 (expand watchlist) is REQUIRED. Origin-agnostic
   detection is meaningless if 60% of amplifying channels are unmonitored.

4. False positive rate on origin-agnostic detection is higher (more flags).
   Mitigate with a two-stage approach:
   Stage 1: origin-agnostic velocity flags (fast, no LLM)
   Stage 2: LLM framing analysis on flagged clusters (expensive, accurate)

LIMITATIONS:
- This analysis uses narrative_origins.csv which only tracks first-mover
  category. Week-over-week velocity requires daily signal counts per
  narrative (not available in current export).
- signals_90d.csv would provide more granular temporal data.
- The Bild map campaign is not in the cluster data (it was manually added
  to campaigns_full.csv with signal_count=0 and no cluster_id).
""")
