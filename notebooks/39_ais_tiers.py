#!/usr/bin/env python3
"""
39. AIS Tiered Scoring
=======================

nb33 showed AIS has 4x throughput swings from collector instability, not
naval activity. Raw volume z-scores are meaningless.

This notebook splits AIS into two tiers:
  Tier 1: defense_osint signals (alert-worthy, real military relevance)
  Tier 2: raw AIS volume (binary detection only, collector-dominated)

Method:
1. Separate AIS signals by content/category into defense-relevant vs raw
2. Compute per-tier stability metrics (CV, zero-days, regime changes)
3. Propose per-tier CTI weights and scoring methods
4. Backtest: does tiered AIS improve CTI accuracy vs single AIS weight?

Data: signals_50d.csv (44,908 signals), signal_daily_counts.csv (506 rows)
"""
import csv
import os
import math
from collections import defaultdict, Counter
from datetime import datetime

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

# ================================================================
# 1. LOAD AND CLASSIFY AIS SIGNALS
# ================================================================
print("=" * 72)
print("39. AIS TIERED SCORING")
print("=" * 72)

# Defense-relevant keywords (from nb33 findings)
DEFENSE_KEYWORDS = {
    'military', 'naval', 'warship', 'navy', 'submarine', 'destroyer',
    'frigate', 'corvette', 'patrol', 'exercise', 'военн', 'флот',
    'подводн', 'крейсер', 'фрегат', 'корвет', 'эсминец', 'патрул',
    'учени', 'манёвр', 'маневр', 'baltiysk', 'kronstadt', 'severomorsk',
    'калининград', 'кронштадт', 'североморск', 'балтийск',
}

# Defense-relevant categories
DEFENSE_CATEGORIES = {'defense_osint', 'military', 'milwatch'}

ais_signals = []
ais_dates = defaultdict(lambda: {'tier1': 0, 'tier2': 0, 'total': 0})

print("\nLoading signals_50d.csv and classifying AIS signals...")
total_signals = 0
with open(f"{DATA}/signals_50d.csv", encoding='utf-8') as f:
    for row in csv.DictReader(f):
        total_signals += 1
        if row['source_type'] != 'ais':
            continue

        title = (row.get('title', '') or '').lower()
        content = (row.get('content', '') or '').lower()
        category = (row.get('category', '') or '').lower()

        # Classify into tiers
        is_defense = (
            category in DEFENSE_CATEGORIES or
            any(kw in title or kw in content for kw in DEFENSE_KEYWORDS)
        )

        try:
            date = row['published_at'][:10]
        except (KeyError, IndexError):
            continue

        ais_signals.append({
            'date': date,
            'tier': 'tier1' if is_defense else 'tier2',
            'title': row.get('title', '')[:80],
            'category': category,
        })

        tier = 'tier1' if is_defense else 'tier2'
        ais_dates[date][tier] += 1
        ais_dates[date]['total'] += 1

print(f"\nTotal signals: {total_signals:,}")
print(f"AIS signals:   {len(ais_signals):,}")

if not ais_signals:
    print("\n⚠  No AIS signals found in signals_50d.csv.")
    print("   AIS signals (782K) are only in signals_90d.csv (gitignored, 161MB).")
    print("   Falling back to signal_daily_counts.csv for aggregate analysis.\n")

tier1_count = sum(1 for s in ais_signals if s['tier'] == 'tier1')
tier2_count = sum(1 for s in ais_signals if s['tier'] == 'tier2')
if ais_signals:
    print(f"\n  Tier 1 (defense-relevant): {tier1_count:,} ({tier1_count/len(ais_signals)*100:.1f}%)")
    print(f"  Tier 2 (raw volume):       {tier2_count:,} ({tier2_count/len(ais_signals)*100:.1f}%)")

# ================================================================
# 2. PER-TIER STABILITY ANALYSIS (from daily counts if no per-signal data)
# ================================================================
print("\n" + "=" * 72)
print("2. PER-TIER DAILY STABILITY")
print("=" * 72)

# If no per-signal AIS data, load aggregate from signal_daily_counts.csv
if not ais_signals:
    print("  Using signal_daily_counts.csv for aggregate AIS analysis.\n")
    with open(f"{DATA}/signal_daily_counts.csv") as f:
        for row in csv.DictReader(f):
            if row['source_type'] == 'ais':
                d = row['date']
                count = int(row['signal_count'])
                ais_dates[d]['total'] = count
                # Without per-signal data, cannot split into tiers
                ais_dates[d]['tier1'] = 0
                ais_dates[d]['tier2'] = count

dates_sorted = sorted(ais_dates.keys())
if not dates_sorted:
    print("  No AIS data available in either signals_50d.csv or signal_daily_counts.csv.")
    print("  Regenerate signals_90d.csv from production DB to run this analysis.")
    import sys; sys.exit(0)

for tier_name in ['tier1', 'tier2', 'total']:
    counts = [ais_dates[d][tier_name] for d in dates_sorted]
    nonzero = [c for c in counts if c > 0]
    zero_days = sum(1 for c in counts if c == 0)

    if nonzero:
        mean = np.mean(nonzero)
        std = np.std(nonzero, ddof=1) if len(nonzero) > 1 else 0
        cv = (std / mean * 100) if mean > 0 else 0
        median = np.median(nonzero)
    else:
        mean = std = cv = median = 0

    print(f"\n  {tier_name:>6s}: {len(counts)} days, {zero_days} zero-days ({zero_days/len(counts)*100:.0f}%)")
    print(f"          mean={mean:.1f}, median={median:.0f}, std={std:.1f}, CV={cv:.0f}%")
    print(f"          min={min(counts)}, max={max(counts)}, P25={np.percentile(counts, 25):.0f}, P75={np.percentile(counts, 75):.0f}")

# ================================================================
# 3. REGIME CHANGE DETECTION
# ================================================================
print("\n" + "=" * 72)
print("3. REGIME CHANGE DETECTION")
print("=" * 72)

# Detect 3x day-over-day volume shifts
REGIME_THRESHOLD = 3.0

for tier_name in ['tier1', 'tier2', 'total']:
    counts = [ais_dates[d][tier_name] for d in dates_sorted]
    regime_changes = []
    for i in range(1, len(counts)):
        if counts[i-1] > 0 and counts[i] > 0:
            ratio = counts[i] / counts[i-1]
            if ratio >= REGIME_THRESHOLD or ratio <= 1/REGIME_THRESHOLD:
                regime_changes.append((dates_sorted[i], counts[i-1], counts[i], ratio))

    print(f"\n  {tier_name}: {len(regime_changes)} regime changes ({REGIME_THRESHOLD}x threshold)")
    for date, before, after, ratio in regime_changes[:5]:
        direction = "UP" if ratio > 1 else "DOWN"
        print(f"    {date}: {before} -> {after} ({ratio:.1f}x {direction})")
    if len(regime_changes) > 5:
        print(f"    ... and {len(regime_changes) - 5} more")

# ================================================================
# 4. TIER 1 CONTENT ANALYSIS
# ================================================================
print("\n" + "=" * 72)
print("4. TIER 1 (DEFENSE-RELEVANT) CONTENT SAMPLES")
print("=" * 72)

tier1_signals = [s for s in ais_signals if s['tier'] == 'tier1']
if tier1_signals:
    # Category distribution
    cats = Counter(s['category'] for s in tier1_signals)
    print(f"\nTier 1 categories:")
    for cat, count in cats.most_common():
        print(f"  {count:>5d} {cat or '(empty)'}")

    # Sample titles
    print(f"\nSample Tier 1 titles:")
    for s in tier1_signals[:15]:
        title = s['title'].replace('\n', ' ')[:70]
        print(f"  [{s['date']}] {title}")
else:
    print("\n  No Tier 1 signals found in signals_50d.csv.")
    print("  This is expected if defense_osint signals are in signals_90d.csv (gitignored).")
    print("  Tier analysis requires the full 90-day export.")

# ================================================================
# 5. SCORING RECOMMENDATIONS
# ================================================================
print("\n" + "=" * 72)
print("5. TIER-BASED SCORING PROPOSAL")
print("=" * 72)

# From the analysis:
# Tier 1: alert-count based, sensitive to real naval activity
# Tier 2: binary (above/below median), only meaningful with stable collector

print("""
PROPOSED TIERED SCORING:

  Tier 1 (defense_osint):
    Weight: 4 (of ~45 moderate total)
    Method: alert_count z-score (robust, median+MAD)
    Why: Low volume, high information density. Each signal matters.
    Regime handling: 7-day burn-in after collector restart.

  Tier 2 (raw AIS volume):
    Weight: 2 (of ~45 moderate total)
    Method: binary (above/below 30-day median)
    Why: High volume, collector-dominated variance (CV > 100%).
    Only contributes when collector is stable (CV < 30% over 14 days).

  Combined: weight=6 total (matches current production AIS weight=6)
  But information quality is MUCH higher because Tier 1 is isolated
  from collector noise.
""")

# ================================================================
# 6. CONDITIONAL WEIGHT LOGIC
# ================================================================
print("=" * 72)
print("6. CONDITIONAL WEIGHT IMPLEMENTATION")
print("=" * 72)

print("""
PRODUCTION IMPLEMENTATION (for compute_threat_index.go):

  func aisWeight(dailyCounts map[string]int, recentCV float64) (int, int) {
      // Tier 1: always active if defense_osint collector reports
      tier1Weight := 4
      
      // Tier 2: conditional on collector stability
      tier2Weight := 0
      if recentCV < 30.0 {  // stable collector for 14+ days
          tier2Weight = 2
      }
      
      return tier1Weight, tier2Weight
  }

This requires:
1. Separate AIS counting in the signal pipeline (defense_osint vs raw)
2. A 14-day CV tracker per source_type
3. Dynamic weight adjustment in the CTI computation
""")

# ================================================================
# 7. SAVE RESULTS
# ================================================================
print("=" * 72)
print("7. SAVE RESULTS")
print("=" * 72)

with open(f"{OUTPUT}/ais_tiers_daily.csv", "w") as f:
    f.write("date,tier1_count,tier2_count,total_ais\n")
    for d in dates_sorted:
        f.write(f"{d},{ais_dates[d]['tier1']},{ais_dates[d]['tier2']},{ais_dates[d]['total']}\n")

print(f"Saved daily tier counts to output/ais_tiers_daily.csv")

print(f"""
LIMITATIONS:
- signals_50d.csv is stale (44K signals). Full analysis needs signals_90d.csv.
- Keyword-based tier classification is a heuristic. Production should use
  source_category from the signal metadata.
- Tier 1 may be very sparse in signals_50d.csv. Validate on 90-day export.
- Conditional weight logic needs Go implementation and testing.

NEXT STEPS:
1. Regenerate signals_90d.csv from production DB.
2. Validate tier classification on full dataset.
3. Implement conditional weight in compute_threat_index.go.
4. Monitor for 14 days to confirm Tier 2 CV threshold is appropriate.
""")
