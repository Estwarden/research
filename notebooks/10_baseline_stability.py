#!/usr/bin/env python3
"""
10. Baseline Stability — which sources are usable for z-scores?
================================================================

The CTI computes z-scores per source: z = (current_24h - mean_7d) / stddev_7d
If the baseline itself is noisy (high CV), z-scores are meaningless.

This notebook measures baseline stability at daily and hourly granularity,
identifies collector downtime, and recommends which sources should use
z-scores vs simpler presence/absence signals.
"""
import csv
import os
import math
from collections import defaultdict
from datetime import datetime, timedelta

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

from cti_constants import SIGNAL_WEIGHTS as CTI_WEIGHTS

# ================================================================
# 1. DAILY BASELINE STABILITY
# ================================================================
print("=" * 70)
print("1. DAILY BASELINE STABILITY (30 days)")
print("=" * 70)

daily = defaultdict(dict)
with open(f"{DATA}/signal_daily_counts.csv") as f:
    for row in csv.DictReader(f):
        daily[row['source_type']][row['date']] = int(row['signal_count'])

def stats(values):
    n = len(values)
    if n < 2:
        return 0, 0, 0, 0
    mean = sum(values) / n
    var = sum((v - mean)**2 for v in values) / (n - 1)
    std = var ** 0.5
    cv = std / mean * 100 if mean > 0 else 0
    median = sorted(values)[n // 2]
    return mean, std, cv, median

print(f"\n  {'Source':20s} {'Days':>4s} {'Mean':>8s} {'Median':>8s} {'Std':>8s} {'CV%':>5s} {'CTI_w':>5s}  Assessment")
print("  " + "-" * 85)

assessments = {}
for st in sorted(daily.keys()):
    counts = list(daily[st].values())
    days = len(counts)
    mean, std, cv, median = stats(counts)
    w = CTI_WEIGHTS.get(st, 0)
    
    # Count zero-days (collector downtime)
    zero_days = sum(1 for c in counts if c == 0)
    
    # Assessment
    if cv < 30:
        assessment = "✅ STABLE — z-scores reliable"
    elif cv < 60:
        assessment = "⚠️  MODERATE — z-scores usable with caution"
    elif cv < 100:
        assessment = "🟡 NOISY — use median baseline"
    else:
        assessment = "❌ UNUSABLE — z-scores meaningless"
    
    if zero_days > 0:
        assessment += f" ({zero_days} zero-days)"
    
    assessments[st] = (cv, assessment, zero_days, mean, median)
    
    if w > 0 or days >= 5:
        print(f"  {st:20s} {days:>4d} {mean:>8.0f} {median:>8.0f} {std:>8.0f} {cv:>5.0f} {w:>5d}  {assessment}")

# ================================================================
# 2. HOURLY PATTERNS — is variance from real signal or downtime?
# ================================================================
print("\n" + "=" * 70)
print("2. HOURLY PATTERNS (14 days)")
print("=" * 70)

hourly = defaultdict(dict)
with open(f"{DATA}/signal_hourly_counts.csv") as f:
    for row in csv.DictReader(f):
        hourly[row['source_type']][row['hour']] = int(row['count'])

for st in sorted(hourly.keys()):
    hours = sorted(hourly[st].items())
    if len(hours) < 24:
        continue
    
    values = [c for _, c in hours]
    mean, std, cv, median = stats(values)
    
    # Check for gaps (missing hours = collector downtime)
    all_hours = set()
    for h_str, _ in hours:
        all_hours.add(h_str)
    
    # Expected hours in 14 days = 336
    expected = 14 * 24
    actual = len(hours)
    gap_pct = (expected - actual) / expected * 100
    
    # Hour-of-day pattern (is there a daily cycle?)
    by_hour = defaultdict(list)
    for h_str, c in hours:
        try:
            hh = int(h_str.split(' ')[1].split(':')[0]) if ' ' in h_str else int(h_str[11:13])
        except (ValueError, IndexError):
            continue
        by_hour[hh].append(c)
    
    hour_means = {h: sum(v)/len(v) for h, v in by_hour.items() if v}
    if hour_means:
        peak_hour = max(hour_means, key=hour_means.get)
        trough_hour = min(hour_means, key=hour_means.get)
        cycle_ratio = hour_means[peak_hour] / max(hour_means[trough_hour], 1)
    else:
        cycle_ratio = 1
    
    print(f"\n  {st}:")
    print(f"    Hourly: mean={mean:.1f}, median={median:.0f}, CV={cv:.0f}%")
    print(f"    Coverage: {actual}/{expected} hours ({gap_pct:.0f}% gaps)")
    print(f"    Daily cycle: peak={peak_hour}:00 ({hour_means.get(peak_hour,0):.0f}/h), "
          f"trough={trough_hour}:00 ({hour_means.get(trough_hour,0):.0f}/h), ratio={cycle_ratio:.1f}x")
    
    if gap_pct > 10:
        print(f"    ⚠️  {gap_pct:.0f}% of hours missing — collector has downtime gaps")
    
    # Show which days have the biggest deviation
    daily_totals = defaultdict(int)
    for h_str, c in hours:
        day = h_str[:10]
        daily_totals[day] += c
    
    dtv = list(daily_totals.values())
    d_mean, d_std, d_cv, d_median = stats(dtv)
    
    # Find outlier days
    outliers = [(d, t) for d, t in sorted(daily_totals.items()) 
                if d_std > 0 and abs((t - d_mean) / d_std) > 2]
    if outliers:
        print(f"    Outlier days (|z|>2):")
        for day, total in outliers:
            z = (total - d_mean) / d_std
            print(f"      {day}: {total:>8d} (z={z:+.1f}, {'spike' if z > 0 else 'drop'})")

# ================================================================
# 3. AIS DEEP DIVE — the biggest offender
# ================================================================
print("\n" + "=" * 70)
print("3. AIS DEEP DIVE")
print("=" * 70)

if 'ais' in hourly:
    ais_hours = sorted(hourly['ais'].items())
    ais_values = [c for _, c in ais_hours]
    mean, std, cv, median = stats(ais_values)
    
    # Group by day
    ais_daily = defaultdict(list)
    for h_str, c in ais_hours:
        day = h_str[:10]
        ais_daily[day].append(c)
    
    print(f"\n  Hourly stats: mean={mean:.0f}, median={median:.0f}, std={std:.0f}, CV={cv:.0f}%")
    print(f"\n  Daily breakdown:")
    print(f"  {'Date':12s} {'Hours':>5s} {'Total':>8s} {'Mean/h':>7s} {'Pattern'}")
    print("  " + "-" * 50)
    
    for day in sorted(ais_daily.keys()):
        vals = ais_daily[day]
        total = sum(vals)
        h_count = len(vals)
        h_mean = total / h_count if h_count else 0
        
        pattern = ""
        if h_count < 20:
            pattern = f"⚠️  PARTIAL ({h_count}h)"
        elif total < median * 0.3 * 24:
            pattern = "📉 LOW"
        elif total > median * 2 * 24:
            pattern = "📈 HIGH"
        else:
            pattern = "✅"
        
        print(f"  {day:12s} {h_count:>5d} {total:>8d} {h_mean:>7.0f} {pattern}")
    
    # What does this mean for z-scores?
    daily_totals = [sum(v) for v in ais_daily.values()]
    d_mean, d_std, d_cv, d_median = stats(daily_totals)
    
    print(f"\n  Daily totals: mean={d_mean:.0f}, median={d_median:.0f}, std={d_std:.0f}, CV={d_cv:.0f}%")
    print(f"  If we use MEDIAN as baseline: {d_median:.0f}")
    print(f"  If we use MEAN as baseline: {d_mean:.0f}")
    print(f"  Difference: {abs(d_mean - d_median):.0f} ({abs(d_mean - d_median)/d_mean*100:.0f}%)")
    
    if d_cv > 50:
        print(f"\n  PROBLEM: AIS daily CV is {d_cv:.0f}%.")
        print(f"  A z-score of 2.0 could be normal variance, not a real anomaly.")
        print(f"  RECOMMENDATION: Use median + MAD instead of mean + stddev,")
        print(f"  or switch to binary presence signal (above/below median).")

# ================================================================
# 4. RECOMMENDATIONS FOR CTI BASELINE METHOD
# ================================================================
print("\n" + "=" * 70)
print("4. RECOMMENDED BASELINE METHODS PER SOURCE")
print("=" * 70)

print(f"\n  {'Source':20s} {'CV%':>5s} {'CTI_w':>5s}  Recommended method")
print("  " + "-" * 70)

for st in sorted(CTI_WEIGHTS.keys(), key=lambda x: -CTI_WEIGHTS[x]):
    w = CTI_WEIGHTS[st]
    cv, assessment, zeros, mean, median = assessments.get(st, (999, "NO DATA", 0, 0, 0))
    
    if cv < 30:
        method = "z-score (mean ± std) — reliable"
    elif cv < 60:
        method = "z-score with median baseline — reduces outlier sensitivity"
    elif cv < 100:
        method = "robust z-score: (x - median) / MAD — handles collector gaps"
    else:
        if mean > 1000:
            method = "log-transform + robust z: log(x) baseline — compresses range"
        else:
            method = "binary: above/below median — z-score not meaningful"
    
    if zeros > 2:
        method += f" + exclude {zeros} zero-days from baseline"
    
    print(f"  {st:20s} {cv:>5.0f} {w:>5d}  {method}")

print("""
KEY INSIGHT:
  The 3 highest-weight CTI sources (gpsjam=12, adsb=10, firms=8)
  have very different stability profiles:
  
  - gpsjam: STABLE (CV ~13%) — z-scores work perfectly
  - adsb: UNUSABLE (CV ~140%) — z-scores are noise
  - firms: NOISY (CV ~100%) — marginal, needs robust baseline
  
  The CTI's accuracy is dominated by whether gpsjam detects something.
  adsb and firms contribute mostly random noise to the score.
""")
