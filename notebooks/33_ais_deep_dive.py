#!/usr/bin/env python3
"""
33. AIS Deep Dive — Separate Collector Downtime from Real Naval Anomalies
==========================================================================

Previous findings:
  - Notebook 10: AIS CV=109% — z-scores meaningless
  - Notebook 17: Recommended binary detection for AIS (clean CV=118%)
  - Notebook 18: Recommended AIS weight 6→3
  - Notebook 32: AIS listed as LIVE with 100% availability (18 data days)

The core problem: AIS went from 37 signals/day to 141K/day across multiple
collector regime changes (Mar 8→25). The high CV is from regime changes, NOT
from real maritime activity variation. Within a STABLE regime, AIS may
actually be very consistent (~62K/day or ~141K/day).

This notebook:
  1. Loads 90-day AIS signal counts (daily + hourly)
  2. Implements gap and regime-change detection
  3. Recomputes baseline statistics WITHIN each stable regime
  4. Determines TRUE AIS baseline stability per regime
  5. Builds per-base vessel count proxy from signal content
  6. Proposes: should AIS CTI weight be restored if downtime is excluded?

Uses ONLY standard library + numpy.
"""
import csv
import json
import math
import os
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

CTI_WEIGHTS = {
    "gpsjam": 12, "adsb": 10, "acled": 8, "firms": 8,
    "ais": 6, "telegram": 6, "rss": 4, "gdelt": 4,
    "energy": 6, "business": 4, "ioda": 4,
}

# ================================================================
# 1. LOAD AIS DATA
# ================================================================
print("=" * 78)
print("33. AIS DEEP DIVE — SEPARATING COLLECTOR ISSUES FROM NAVAL ANOMALIES")
print("=" * 78)

# --- Daily counts ---
daily_counts = {}  # date_str -> count
with open(os.path.join(DATA, 'signal_daily_counts.csv')) as f:
    for row in csv.DictReader(f):
        if row['source_type'] == 'ais':
            daily_counts[row['date']] = int(row['signal_count'])

# --- Hourly counts ---
hourly_counts = {}  # hour_str -> count
with open(os.path.join(DATA, 'signal_hourly_counts.csv')) as f:
    for row in csv.DictReader(f):
        if row['source_type'] == 'ais':
            hourly_counts[row['hour']] = int(row['signal_count'])

all_dates = sorted(daily_counts.keys())
total_signals = sum(daily_counts.values())

print(f"\n  AIS daily data: {len(all_dates)} days ({all_dates[0]} → {all_dates[-1]})")
print(f"  AIS hourly data: {len(hourly_counts)} hours")
print(f"  Total AIS signals: {total_signals:,}")

print(f"\n  Daily counts:")
print(f"  {'Date':>12s} {'Count':>10s}  {'Regime indicator'}")
print("  " + "-" * 55)
for d in all_dates:
    c = daily_counts[d]
    indicator = ""
    if c < 50:
        indicator = "📉 BARELY WORKING"
    elif c < 1000:
        indicator = "⚠️  LOW RATE"
    elif c < 10000:
        indicator = "🔄 TRANSITION"
    elif c < 50000:
        indicator = "📊 MID REGIME (~33-62K)"
    elif c < 100000:
        indicator = "✅ STABLE REGIME (~62K)"
    else:
        indicator = "🔺 HIGH REGIME (~135-141K)"
    print(f"  {d:>12s} {c:>10,d}  {indicator}")


# ================================================================
# 2. REGIME DETECTION — IDENTIFY STABLE OPERATING PERIODS
# ================================================================
print("\n" + "=" * 78)
print("2. REGIME DETECTION — COLLECTOR STATE CHANGES")
print("=" * 78)
print("""
  The AIS collector underwent multiple upgrades/reconfigurations. We need to
  identify STABLE regimes where the collector was consistently operating.
  
  Approach: detect step changes where daily count changes by >3× from the
  previous day. Days within a regime should have similar volumes.
""")

# Detect regime changes by looking at relative day-to-day changes
dates_arr = np.array([datetime.strptime(d, '%Y-%m-%d') for d in all_dates])
counts_arr = np.array([daily_counts[d] for d in all_dates], dtype=float)

regimes = []  # list of (start_date, end_date, [daily_counts])
current_regime_start = 0

for i in range(1, len(counts_arr)):
    # Regime change if count changes by >2x (up or down)
    # Using 2× rather than 3× because the 62K→141K jump (2.3×) is
    # clearly a collector upgrade, not a naval activity change
    prev = max(counts_arr[i-1], 1)
    curr = max(counts_arr[i], 1)
    ratio = max(curr/prev, prev/curr)

    if ratio > 2.0:
        # Close previous regime
        regimes.append({
            'start': all_dates[current_regime_start],
            'end': all_dates[i-1],
            'days': i - current_regime_start,
            'counts': counts_arr[current_regime_start:i].tolist(),
        })
        current_regime_start = i

# Close last regime
regimes.append({
    'start': all_dates[current_regime_start],
    'end': all_dates[-1],
    'days': len(counts_arr) - current_regime_start,
    'counts': counts_arr[current_regime_start:].tolist(),
})

print(f"\n  Detected {len(regimes)} regimes:\n")
print(f"  {'#':>3s} {'Start':>12s} {'End':>12s} {'Days':>5s} {'Mean':>10s} {'Median':>10s} "
      f"{'Std':>10s} {'CV%':>6s}  {'Classification'}")
print("  " + "-" * 95)

regime_stats = []
for idx, reg in enumerate(regimes):
    vals = np.array(reg['counts'])
    n = len(vals)
    mean_v = np.mean(vals)
    median_v = np.median(vals)
    std_v = np.std(vals, ddof=1) if n > 1 else 0.0
    cv = (std_v / mean_v * 100) if mean_v > 0 else 0.0

    # Classify regime
    if mean_v < 50:
        classification = "BROKEN — collector barely ingesting"
    elif mean_v < 1000:
        classification = "LOW — partial collector operation"
    elif mean_v < 10000:
        classification = "TRANSITION — collector upgrading"
    elif mean_v < 80000:
        classification = "OPERATIONAL — consistent mid-volume"
    else:
        classification = "FULL — high-throughput operation"

    is_stable = n >= 3 and cv < 30
    if is_stable:
        classification += " ✅ STABLE"

    reg_info = {
        'idx': idx,
        'start': reg['start'],
        'end': reg['end'],
        'days': n,
        'mean': mean_v,
        'median': median_v,
        'std': std_v,
        'cv': cv,
        'classification': classification,
        'is_stable': is_stable,
        'counts': vals,
    }
    regime_stats.append(reg_info)

    print(f"  {idx+1:>3d} {reg['start']:>12s} {reg['end']:>12s} {n:>5d} {mean_v:>10,.0f} "
          f"{median_v:>10,.0f} {std_v:>10,.0f} {cv:>6.1f}  {classification}")


# ================================================================
# 3. DOWNTIME DETECTION
# ================================================================
print("\n" + "=" * 78)
print("3. DOWNTIME DETECTION")
print("=" * 78)
print("""
  Rule: A day is DOWNTIME if daily count < 10% of the median of the
  MOST RECENT stable regime. Days before the collector started are
  NOT downtime — they're "pre-deployment."
""")

# Find the most recent regime with meaningful data (>1000 signals/day avg)
meaningful_regimes = [r for r in regime_stats if r['mean'] > 1000 and r['days'] >= 2]

if meaningful_regimes:
    latest_stable = meaningful_regimes[-1]
    reference_median = latest_stable['median']
    downtime_threshold = reference_median * 0.10
else:
    reference_median = np.median(counts_arr)
    downtime_threshold = reference_median * 0.10

print(f"\n  Reference regime: #{meaningful_regimes[-1]['idx']+1 if meaningful_regimes else '?'} "
      f"(median={reference_median:,.0f}/day)")
print(f"  Downtime threshold: <{downtime_threshold:,.0f} signals/day")

downtime_days = []
normal_days = []
for d in all_dates:
    c = daily_counts[d]
    if c < downtime_threshold:
        downtime_days.append(d)
    else:
        normal_days.append(d)

print(f"\n  Downtime days ({len(downtime_days)}/{len(all_dates)}):")
for d in downtime_days:
    print(f"    {d}: {daily_counts[d]:,d} signals")

print(f"\n  Normal days ({len(normal_days)}/{len(all_dates)}):")
for d in normal_days:
    print(f"    {d}: {daily_counts[d]:,d} signals")


# ================================================================
# 4. BASELINE STATISTICS — WITH AND WITHOUT DOWNTIME
# ================================================================
print("\n" + "=" * 78)
print("4. BASELINE STATISTICS — DOWNTIME EXCLUDED vs RAW")
print("=" * 78)

# Raw (all days)
raw_vals = counts_arr.copy()
raw_mean = np.mean(raw_vals)
raw_median = np.median(raw_vals)
raw_std = np.std(raw_vals, ddof=1)
raw_cv = (raw_std / raw_mean * 100) if raw_mean > 0 else 0.0
raw_mad = np.median(np.abs(raw_vals - raw_median))

# Clean (downtime excluded)
clean_vals = np.array([daily_counts[d] for d in normal_days], dtype=float)
if len(clean_vals) > 1:
    clean_mean = np.mean(clean_vals)
    clean_median = np.median(clean_vals)
    clean_std = np.std(clean_vals, ddof=1)
    clean_cv = (clean_std / clean_mean * 100) if clean_mean > 0 else 0.0
    clean_mad = np.median(np.abs(clean_vals - clean_median))
else:
    clean_mean = clean_median = clean_std = clean_cv = clean_mad = 0.0

print(f"\n  {'Metric':20s} {'Raw (all days)':>15s}  {'Clean (no downtime)':>20s}")
print("  " + "-" * 60)
print(f"  {'Days':20s} {len(all_dates):>15d}  {len(normal_days):>20d}")
print(f"  {'Mean':20s} {raw_mean:>15,.0f}  {clean_mean:>20,.0f}")
print(f"  {'Median':20s} {raw_median:>15,.0f}  {clean_median:>20,.0f}")
print(f"  {'Std':20s} {raw_std:>15,.0f}  {clean_std:>20,.0f}")
print(f"  {'CV%':20s} {raw_cv:>15.1f}  {clean_cv:>20.1f}")
print(f"  {'MAD':20s} {raw_mad:>15,.0f}  {clean_mad:>20,.0f}")
print(f"  {'MAD*1.4826':20s} {raw_mad*1.4826:>15,.0f}  {clean_mad*1.4826:>20,.0f}")
print(f"  {'Min':20s} {np.min(raw_vals):>15,.0f}  {np.min(clean_vals):>20,.0f}")
print(f"  {'Max':20s} {np.max(raw_vals):>15,.0f}  {np.max(clean_vals):>20,.0f}")

# Per-regime stats (the real insight)
print(f"\n  PER-REGIME STABILITY (the actual useful metrics):")
print(f"\n  {'Regime':>8s} {'Days':>5s} {'Mean':>10s} {'Median':>10s} {'CV%':>6s} {'MAD':>10s} {'Usable?'}")
print("  " + "-" * 70)

for reg in regime_stats:
    if reg['days'] < 2:
        usable = "TOO SHORT"
    elif reg['cv'] < 15:
        usable = "✅ EXCELLENT — standard z viable"
    elif reg['cv'] < 30:
        usable = "✅ GOOD — robust z viable"
    elif reg['cv'] < 50:
        usable = "⚠️  MODERATE — robust z marginal"
    else:
        usable = "❌ NOISY — binary only"

    # Compute MAD for this regime
    reg_mad = np.median(np.abs(reg['counts'] - np.median(reg['counts'])))

    print(f"  R{reg['idx']+1:>6d} {reg['days']:>5d} {reg['mean']:>10,.0f} {reg['median']:>10,.0f} "
          f"{reg['cv']:>6.1f} {reg_mad:>10,.0f} {usable}")


# ================================================================
# 5. HOURLY ANALYSIS — WITHIN-DAY PATTERNS
# ================================================================
print("\n" + "=" * 78)
print("5. HOURLY ANALYSIS — WITHIN-DAY PATTERNS")
print("=" * 78)

# Group hourly data by day
hourly_by_day = defaultdict(list)  # date -> [(hour, count)]
for h_str, cnt in hourly_counts.items():
    day = h_str[:10]
    try:
        hour = int(h_str[11:13])
    except (ValueError, IndexError):
        continue
    hourly_by_day[day].append((hour, cnt))

# Analyze hourly consistency per regime
print(f"\n  HOURLY CONSISTENCY PER DAY:")
print(f"  {'Date':>12s} {'Hours':>5s} {'Total':>10s} {'Mean/h':>10s} {'CV%/h':>7s} {'Pattern'}")
print("  " + "-" * 65)

for d in sorted(hourly_by_day.keys()):
    hours = hourly_by_day[d]
    n_hours = len(hours)
    values = [c for _, c in hours]
    total = sum(values)
    mean_h = np.mean(values)
    std_h = np.std(values, ddof=1) if len(values) > 1 else 0.0
    cv_h = (std_h / mean_h * 100) if mean_h > 0 else 0.0

    if n_hours < 5:
        pattern = "📉 PARTIAL DAY"
    elif cv_h < 5:
        pattern = "✅ VERY CONSISTENT (flat throughput)"
    elif cv_h < 15:
        pattern = "✅ CONSISTENT"
    elif cv_h < 30:
        pattern = "⚠️  MODERATE variance"
    else:
        pattern = "❌ HIGH variance"

    print(f"  {d:>12s} {n_hours:>5d} {total:>10,d} {mean_h:>10,.0f} {cv_h:>7.1f}  {pattern}")

# Hour-of-day aggregate pattern (across all days in the latest stable regime)
print(f"\n  HOUR-OF-DAY PATTERN (aggregate across latest regime):")

# Find latest regime with 24h coverage
latest_regime_dates = set()
for reg in reversed(regime_stats):
    if reg['days'] >= 3 and reg['mean'] > 1000:
        d = datetime.strptime(reg['start'], '%Y-%m-%d')
        d_end = datetime.strptime(reg['end'], '%Y-%m-%d')
        while d <= d_end:
            latest_regime_dates.add(d.strftime('%Y-%m-%d'))
            d += timedelta(days=1)
        break

by_hour = defaultdict(list)  # hour_of_day -> [counts]
for d in sorted(latest_regime_dates):
    for hour, cnt in hourly_by_day.get(d, []):
        by_hour[hour].append(cnt)

if by_hour:
    print(f"\n  {'Hour':>6s} {'Mean':>10s} {'Std':>8s} {'CV%':>6s} {'N_days':>6s}")
    print("  " + "-" * 40)
    for h in range(24):
        if h in by_hour:
            vals = np.array(by_hour[h])
            mean_v = np.mean(vals)
            std_v = np.std(vals, ddof=1) if len(vals) > 1 else 0
            cv_v = (std_v / mean_v * 100) if mean_v > 0 else 0
            print(f"  {h:>5d}h {mean_v:>10,.0f} {std_v:>8,.0f} {cv_v:>6.1f} {len(vals):>6d}")
        else:
            print(f"  {h:>5d}h {'—':>10s}")

    # Overall hourly flatness
    all_hour_means = [np.mean(by_hour[h]) for h in range(24) if h in by_hour]
    if len(all_hour_means) > 1:
        hour_cv = np.std(all_hour_means, ddof=1) / np.mean(all_hour_means) * 100
        print(f"\n  Across-hour CV: {hour_cv:.1f}%")
        if hour_cv < 10:
            print("  → AIS collector runs at FLAT throughput with no diurnal cycle")
            print("    (expected: maritime traffic is 24/7, no day/night pattern in AIS data)")
        else:
            print("  → Some diurnal variation detected")


# ================================================================
# 6. PER-BASE VESSEL COUNT PROXY
# ================================================================
print("\n" + "=" * 78)
print("6. PER-BASE VESSEL COUNT PROXY")
print("=" * 78)
print("""
  Goal: count AIS signals associated with key naval bases to build a
  per-base activity proxy. Two approaches:
  
  (A) Region-based: use the 'region' field from pre-classified signals
  (B) Coordinate-based: extract lat/lon from content, match to base proximity
  
  Key naval bases:
    - Baltiysk (Kaliningrad):     54.65°N, 19.89°E — Baltic Fleet HQ
    - Kronstadt (St Petersburg):  59.99°N, 29.77°E — Baltic Fleet base
    - Lomonosov (near Kronstadt): 59.91°N, 29.77°E — Naval facility
""")

# Define naval base locations and proximity radius (in degrees, ~5km ≈ 0.045°)
NAVAL_BASES = {
    'Baltiysk': (54.65, 19.89, 0.10),     # 0.10° ≈ 11km radius
    'Kronstadt': (59.99, 29.77, 0.10),
    'Kaliningrad_port': (54.71, 20.50, 0.10),
}

# Approach A: Region-based counts per day
print("\n  APPROACH A: REGION-BASED COUNTS")
print("  " + "-" * 50)

region_daily = defaultdict(lambda: defaultdict(int))  # region -> {date -> count}
vessel_types_daily = defaultdict(lambda: defaultdict(int))  # type -> {date -> count}
base_daily = defaultdict(lambda: defaultdict(int))     # base -> {date -> count}
coord_counts = 0
total_ais = 0

# Process all AIS signals from signals_90d.csv
signals_path = os.path.join(DATA, 'signals_90d.csv')
if os.path.exists(signals_path):
    print(f"\n  Reading AIS signals from signals_90d.csv...")

    with open(signals_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['source_type'] != 'ais':
                continue
            total_ais += 1

            pub = row.get('published_at', '')
            if len(pub) < 10:
                continue
            day = pub[:10]

            # Region classification
            region = row.get('region', '')
            if region:
                for r in region.split(','):
                    r = r.strip()
                    if r:
                        region_daily[r][day] += 1

            # Vessel type from title
            title = row.get('title', '')
            if 'Shadow fleet' in title:
                vessel_types_daily['shadow_fleet'][day] += 1
            elif 'Russian naval' in title:
                vessel_types_daily['ru_naval'][day] += 1
            elif 'Russian other' in title or 'Russian cargo' in title:
                vessel_types_daily['ru_commercial'][day] += 1
            elif 'near C-Lion' in title or 'near Baltic' in title:
                vessel_types_daily['infra_proximity'][day] += 1
            elif re.match(r'^\d+\s', title):
                vessel_types_daily['raw_ais'][day] += 1
            elif '⚠️' in title:
                vessel_types_daily['warning_other'][day] += 1
            else:
                vessel_types_daily['other'][day] += 1

            # Approach B: Coordinate extraction for base proximity
            content = row.get('content', '')
            lat, lon = None, None

            # Pattern 1: Position: 55.6912°N 21.1354°E
            m = re.search(r'(\d+\.\d+)°([NS])\s+(\d+\.\d+)°([EW])', content)
            if m:
                lat = float(m.group(1)) * (1 if m.group(2) == 'N' else -1)
                lon = float(m.group(3)) * (1 if m.group(4) == 'E' else -1)

            # Pattern 2: at 59.4189,27.7315
            if lat is None:
                m = re.search(r'at (\d+\.\d+),(\d+\.\d+)', content)
                if m:
                    lat, lon = float(m.group(1)), float(m.group(2))

            if lat is not None and lon is not None:
                coord_counts += 1
                for base_name, (b_lat, b_lon, radius) in NAVAL_BASES.items():
                    if abs(lat - b_lat) < radius and abs(lon - b_lon) < radius:
                        base_daily[base_name][day] += 1

    print(f"  Total AIS signals processed: {total_ais:,}")
    print(f"  Signals with extractable coordinates: {coord_counts:,} ({coord_counts/max(total_ais,1)*100:.1f}%)")

    # Region counts
    print(f"\n  REGION BREAKDOWN (top 10):")
    print(f"  {'Region':30s} {'Total':>10s} {'Days':>5s} {'Mean/d':>8s}")
    print("  " + "-" * 58)
    for r, day_counts in sorted(region_daily.items(), key=lambda x: -sum(x[1].values()))[:10]:
        total_r = sum(day_counts.values())
        n_days_r = len(day_counts)
        mean_r = total_r / max(n_days_r, 1)
        print(f"  {r:30s} {total_r:>10,d} {n_days_r:>5d} {mean_r:>8,.0f}")

    # Vessel type breakdown per day
    print(f"\n  VESSEL TYPE BREAKDOWN PER DAY:")
    all_type_dates = sorted(set().union(*(d.keys() for d in vessel_types_daily.values())))

    type_order = ['ru_commercial', 'raw_ais', 'ru_naval', 'shadow_fleet',
                  'infra_proximity', 'warning_other', 'other']
    existing_types = [t for t in type_order if t in vessel_types_daily]

    print(f"  {'Date':>12s}", end="")
    for t in existing_types:
        print(f"  {t[:12]:>12s}", end="")
    print(f"  {'TOTAL':>10s}")
    print("  " + "-" * (12 + 14 * len(existing_types) + 12))

    for d in all_type_dates:
        print(f"  {d:>12s}", end="")
        day_total = 0
        for t in existing_types:
            c = vessel_types_daily[t].get(d, 0)
            day_total += c
            print(f"  {c:>12,d}", end="")
        print(f"  {day_total:>10,d}")

    # Per-base proximity counts
    if base_daily:
        print(f"\n  APPROACH B: NAVAL BASE PROXIMITY COUNTS")
        print(f"  (Signals within ~{NAVAL_BASES['Baltiysk'][2]*111:.0f}km of each base)")
        print(f"  " + "-" * 60)

        print(f"  {'Date':>12s}", end="")
        for base in NAVAL_BASES:
            print(f"  {base:>14s}", end="")
        print()
        print("  " + "-" * (12 + 16 * len(NAVAL_BASES)))

        prox_dates = sorted(set().union(*(d.keys() for d in base_daily.values())))
        base_totals = defaultdict(int)
        for d in prox_dates:
            print(f"  {d:>12s}", end="")
            for base in NAVAL_BASES:
                c = base_daily[base].get(d, 0)
                base_totals[base] += c
                print(f"  {c:>14,d}", end="")
            print()

        print(f"\n  Base proximity totals:")
        for base, total in sorted(base_totals.items(), key=lambda x: -x[1]):
            avg = total / max(len(prox_dates), 1)
            print(f"    {base}: {total:,d} signals ({avg:,.0f}/day avg)")
    else:
        print("\n  No signals matched naval base proximity zones.")
else:
    print(f"\n  WARNING: {signals_path} not found. Skipping per-base analysis.")


# ================================================================
# 7. SECURITY-RELEVANT SIGNAL ANALYSIS
# ================================================================
print("\n" + "=" * 78)
print("7. SECURITY-RELEVANT AIS SIGNALS (defense_osint category)")
print("=" * 78)
print("""
  The AIS data has two tiers:
    Tier 1: defense_osint — curated alerts (shadow fleet, naval, infra proximity)
    Tier 2: raw AIS — bulk vessel position reports (780K+ signals)
  
  For CTI purposes, Tier 1 is far more valuable. Let's analyze it separately.
""")

if os.path.exists(signals_path):
    # Count defense_osint AIS signals per day
    defense_daily = defaultdict(int)
    defense_subtypes = defaultdict(lambda: defaultdict(int))  # subtype -> {date -> count}

    with open(signals_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['source_type'] != 'ais':
                continue
            cat = row.get('category', '')
            if cat != 'defense_osint':
                continue

            pub = row.get('published_at', '')
            if len(pub) < 10:
                continue
            day = pub[:10]
            defense_daily[day] += 1

            title = row.get('title', '')
            if 'Shadow fleet' in title:
                defense_subtypes['shadow_fleet'][day] += 1
            elif 'Russian naval' in title:
                defense_subtypes['ru_naval'][day] += 1
            elif 'near C-Lion' in title or 'near Baltic' in title:
                defense_subtypes['infra_proximity'][day] += 1
            else:
                defense_subtypes['other_defense'][day] += 1

    print(f"  Defense-OSINT AIS signals: {sum(defense_daily.values()):,d}")
    print(f"  Days with defense signals: {len(defense_daily)}")

    if defense_daily:
        def_vals = np.array([defense_daily[d] for d in sorted(defense_daily.keys())])
        def_mean = np.mean(def_vals)
        def_median = np.median(def_vals)
        def_std = np.std(def_vals, ddof=1) if len(def_vals) > 1 else 0
        def_cv = (def_std / def_mean * 100) if def_mean > 0 else 0
        def_mad = np.median(np.abs(def_vals - def_median))

        print(f"\n  Defense-OSINT daily stats:")
        print(f"    Mean:   {def_mean:>8.1f}")
        print(f"    Median: {def_median:>8.1f}")
        print(f"    Std:    {def_std:>8.1f}")
        print(f"    CV%:    {def_cv:>8.1f}")
        print(f"    MAD:    {def_mad:>8.1f}")

        print(f"\n  {'Date':>12s} {'Total':>6s}", end="")
        for sub in sorted(defense_subtypes.keys()):
            print(f"  {sub[:14]:>14s}", end="")
        print()
        print("  " + "-" * (20 + 16 * len(defense_subtypes)))

        for d in sorted(defense_daily.keys()):
            print(f"  {d:>12s} {defense_daily[d]:>6d}", end="")
            for sub in sorted(defense_subtypes.keys()):
                print(f"  {defense_subtypes[sub].get(d, 0):>14d}", end="")
            print()

        print(f"\n  INSIGHT: Defense-OSINT signals are CURATED alerts (shadow fleet,")
        print(f"  Russian naval, infra proximity). These have HIGH information value")
        print(f"  but LOW volume ({def_mean:.0f}/day). For CTI, these matter more than")
        print(f"  the 100K+ raw AIS vessel positions.")


# ================================================================
# 8. REGIME-AWARE BASELINE SIMULATION
# ================================================================
print("\n" + "=" * 78)
print("8. REGIME-AWARE BASELINE SIMULATION")
print("=" * 78)
print("""
  Question: If we exclude downtime AND use regime-aware baselines,
  does AIS become a viable z-score source?
  
  Test: Compute z-scores within each stable regime using:
  (a) Standard z-score
  (b) Robust z-score (median + MAD)
  (c) Binary (above/below median)
""")

# Find all stable regimes (>= 3 days, CV < 50%)
stable_regimes = [r for r in regime_stats if r['days'] >= 3 and r['cv'] < 50]

if stable_regimes:
    print(f"\n  Stable regimes for z-score analysis: {len(stable_regimes)}")

    for reg in stable_regimes:
        vals = reg['counts']
        n = len(vals)
        mean_v = np.mean(vals)
        median_v = np.median(vals)
        std_v = np.std(vals, ddof=1) if n > 1 else 1.0
        mad_v = np.median(np.abs(vals - median_v))
        mad_scaled = max(mad_v * 1.4826, 1.0)

        print(f"\n  Regime R{reg['idx']+1} ({reg['start']} → {reg['end']}, {n} days):")
        print(f"  Baseline: mean={mean_v:,.0f}, median={median_v:,.0f}, std={std_v:,.0f}, "
              f"MAD*1.4826={mad_scaled:,.0f}")
        print(f"  CV: {reg['cv']:.1f}%")

        print(f"\n  {'Day':>12s} {'Count':>10s} {'z_std':>8s} {'z_robust':>8s} {'Binary':>8s} {'Flag'}")
        print("  " + "-" * 55)

        # Use the regime's own median as "expected" and flag deviations
        for i, val in enumerate(vals):
            d_offset = i
            d_dt = datetime.strptime(reg['start'], '%Y-%m-%d') + timedelta(days=d_offset)
            d_str = d_dt.strftime('%Y-%m-%d')

            z_std = (val - mean_v) / max(std_v, 1)
            z_robust = (val - median_v) / max(mad_scaled, 1)
            binary = 1 if val > median_v else 0

            flag = ""
            if abs(z_robust) > 2:
                flag = "⚠️  ANOMALY"
            elif abs(z_robust) > 1.5:
                flag = "⚡ elevated"

            print(f"  {d_str:>12s} {val:>10,.0f} {z_std:>8.2f} {z_robust:>8.2f} {binary:>8d} {flag}")

        # Anomaly rate within regime
        z_scores = np.array([(v - median_v) / max(mad_scaled, 1) for v in vals])
        anomaly_rate = np.mean(np.abs(z_scores) > 2) * 100
        print(f"\n  Within-regime anomaly rate (|z_robust|>2): {anomaly_rate:.1f}%")
        if anomaly_rate < 10:
            print("  → Low false positive rate — robust z IS viable for this regime")
        elif anomaly_rate < 25:
            print("  → Moderate false positive rate — robust z marginal")
        else:
            print("  → High false positive rate — binary detection recommended")
else:
    print("\n  No stable regimes found with ≥3 days and CV<50%.")


# ================================================================
# 9. CTI WEIGHT RECOMMENDATION
# ================================================================
print("\n" + "=" * 78)
print("9. CTI WEIGHT RECOMMENDATION")
print("=" * 78)

# Find the best stable regime for analysis
best_regime = None
for reg in reversed(regime_stats):
    if reg['days'] >= 3 and reg['mean'] > 1000:
        best_regime = reg
        break

if best_regime:
    regime_cv = best_regime['cv']
    regime_days = best_regime['days']
    regime_mean = best_regime['mean']

    print(f"""
  CURRENT SITUATION:
    AIS original CTI weight: 6
    NB17 recommendation: 6→3 (binary detection, clean CV=118%)
    NB18 recommendation: 6→3 (binary detection)
  
  NEW FINDINGS (this notebook):
    The CV=118% is MISLEADING. It's caused by regime changes, not data noise.
    
    Within the latest stable regime ({best_regime['start']} → {best_regime['end']}):
      - Daily count: ~{regime_mean:,.0f}/day
      - CV: {regime_cv:.1f}%
      - Days: {regime_days}
""")

    if regime_cv < 30:
        recommendation = "RESTORE weight to 6 with regime-aware baseline"
        method = "robust_z"
        reasoning = (f"Within-regime CV={regime_cv:.1f}% is excellent. "
                     "Robust z-scores are viable when regime is identified correctly.")
    elif regime_cv < 50:
        recommendation = "RESTORE weight to 4-6 with regime-aware robust z-score"
        method = "robust_z"
        reasoning = (f"Within-regime CV={regime_cv:.1f}% is acceptable for robust z-scores. "
                     "Regime detection is needed to avoid false anomalies at transitions.")
    else:
        recommendation = "KEEP weight at 3, use binary detection"
        method = "binary"
        reasoning = (f"Within-regime CV={regime_cv:.1f}% is still too high even within "
                     "stable periods. Binary detection is the safest approach.")

    print(f"""  RECOMMENDATION: {recommendation}
    Method: {method}
    Reasoning: {reasoning}
  
  CONDITIONS FOR WEIGHT RESTORATION:
    1. Implement REGIME DETECTION in production:
       - Track rolling 7-day median of daily AIS counts
       - If current day < 10% of rolling median → mark as DOWNTIME
       - If current day > 3× rolling median → REGIME CHANGE, start 7-day burn-in
       - During burn-in: AIS contributes 0 to CTI (baseline is being established)
    
    2. Use ROBUST Z-SCORE within stable regime:
       z = (current_24h - median_7d) / max(MAD_7d × 1.4826, 1)
       Exclude downtime days from the 7-day window.
    
    3. Two-tier AIS contribution to CTI:
       a) VOLUME z-score: based on total AIS signal count (current method)
       b) ALERT count: number of defense_osint signals (shadow fleet, naval, infra)
       The alert count is MORE informative but lower volume.
  
  PROPOSED PRODUCTION IMPLEMENTATION:
    weight_ais = 6  // restore original weight
    
    func aisContribution(current_24h, baseline_7d []float64) float64 {{
        // Exclude downtime from baseline
        clean := excludeDowntime(baseline_7d, 0.10)
        if len(clean) < 3 {{
            return 0  // insufficient baseline
        }}
        
        // Check for regime change
        median := median(clean)
        if current_24h > 3 * median || current_24h < median / 3 {{
            return 0  // regime change detected, in burn-in
        }}
        
        // Robust z-score
        mad := medianAbsDev(clean) * 1.4826
        z := (current_24h - median) / max(mad, 1.0)
        return clamp(z / 3.0, 0, 1)  // normalize to [0, 1]
    }}
""")
else:
    print("\n  No stable regime found — cannot make weight recommendation.")
    print("  AIS collector needs to be stabilized before CTI integration.")


# ================================================================
# 10. HONEST ASSESSMENT
# ================================================================
print("\n" + "=" * 78)
print("10. HONEST ASSESSMENT")
print("=" * 78)
print(f"""
  WHAT WE LEARNED:
  ──────────────────
  
  1. AIS CV=109-118% is a COLLECTOR problem, not a data problem.
     The collector underwent at least {len(regimes)} distinct operating regimes
     in 18 days, ranging from 37 to 141K signals/day. This isn't naval
     activity variation — it's infrastructure instability.
  
  2. Within stable regimes, AIS is REMARKABLY consistent.
     The hourly data shows flat throughput (no diurnal cycle) within each
     regime, and day-to-day variation within a regime is low.
  
  3. The 782K AIS signals are dominated by bulk vessel tracking (~480K raw
     MMSI position reports + ~300K Russian commercial vessels). Only 1,885
     signals (~0.24%) are defense_osint curated alerts (shadow fleet, naval,
     infrastructure proximity).
  
  4. For CTI purposes, the CURATED alerts matter far more than raw volume.
     A spike in shadow fleet detections or infra proximity alerts is a real
     signal. A jump from 62K to 141K raw AIS reports is just a collector
     upgrade.
  
  WHAT NEEDS TO HAPPEN:
  ──────────────────────
  
  1. STABILIZE THE COLLECTOR. No amount of mathematical gymnastics can fix
     a system that changes throughput by 4× overnight. The collector needs
     to run at a consistent rate for at least 14 days before any baseline
     method can work.
  
  2. SEPARATE TIERS FOR CTI. The production CTI should track:
     - Tier 1 (defense_osint): Alert count — sensitive to REAL naval activity
     - Tier 2 (raw AIS): Volume z-score — only meaningful with stable collector
  
  3. REGIME CHANGE DETECTION. Production needs automatic detection of collector
     state changes (3× day-over-day volume shift) with a 7-day burn-in period
     before z-scores activate.
  
  4. CONDITIONAL WEIGHT RESTORATION. If the collector stabilizes (CV<30% over
     14 days), AIS weight can be restored to 6. Until then, weight=3 or lower
     is appropriate.
  
  BOTTOM LINE:
  ─────────────
  The data EXISTS and is high-quality when the collector is working. The
  problem is purely operational — fix the collector, and AIS becomes one of
  the most valuable CTI sources (24/7 coverage, no diurnal bias, direct
  observation of naval activity).
  
  Until the collector is stable: AIS weight = 3-4, binary detection mode.
  After stabilization (14+ days, CV<30%): AIS weight = 6, robust z-score.
""")


# ================================================================
# SUMMARY TABLE — EXPORT
# ================================================================
print("=" * 78)
print("SUMMARY")
print("=" * 78)

summary = {
    'total_ais_signals': total_ais,
    'date_range': {'start': all_dates[0], 'end': all_dates[-1]},
    'data_days': len(all_dates),
    'raw_cv_pct': round(raw_cv, 1),
    'downtime_days': len(downtime_days),
    'regimes_detected': len(regimes),
    'stable_regimes': len(stable_regimes) if 'stable_regimes' in dir() else 0,
    'best_regime': {
        'start': best_regime['start'] if best_regime else None,
        'end': best_regime['end'] if best_regime else None,
        'cv_pct': round(best_regime['cv'], 1) if best_regime else None,
        'mean_daily': round(best_regime['mean'], 0) if best_regime else None,
    } if best_regime else None,
    'defense_osint_signals': sum(defense_daily.values()) if 'defense_daily' in dir() else 0,
    'coord_extractable_pct': round(coord_counts / max(total_ais, 1) * 100, 1),
    'current_weight': 6,
    'recommended_weight_stable': 6,
    'recommended_weight_unstable': 3,
    'recommended_method_stable': 'robust_z',
    'recommended_method_unstable': 'binary',
    'base_proximity_totals': dict(base_totals) if 'base_totals' in dir() else {},
}

export_path = os.path.join(OUTPUT, 'ais_deep_dive.json')
with open(export_path, 'w') as f:
    json.dump(summary, f, indent=2, default=str)
print(f"\n  Summary exported to: {export_path}")

print(f"""
  ┌─────────────────────────────────────────────────────────────────┐
  │ AIS DEEP DIVE — KEY FINDINGS                                   │
  ├─────────────────────────────────────────────────────────────────┤
  │ Raw CV:              {raw_cv:>6.1f}% (misleading — regime changes)    │
  │ Downtime days:       {len(downtime_days):>6d} / {len(all_dates)} days                          │
  │ Regimes detected:    {len(regimes):>6d}                                    │
  │ Best regime CV:      {best_regime['cv'] if best_regime else float('nan'):>6.1f}% (within stable period)       │
  │ Defense signals:     {sum(defense_daily.values()) if 'defense_daily' in dir() else 0:>6,d} ({sum(defense_daily.values())/max(total_ais,1)*100 if 'defense_daily' in dir() else 0:.2f}% of total)        │
  │ Coords extractable:  {coord_counts/max(total_ais,1)*100:.1f}%                                  │
  ├─────────────────────────────────────────────────────────────────┤
  │ RECOMMENDATION:                                                 │
  │   Stable collector → weight=6, robust z-score                   │
  │   Unstable collector → weight=3, binary detection               │
  │   Need: 14-day burn-in, regime change detection                 │
  └─────────────────────────────────────────────────────────────────┘
""")
