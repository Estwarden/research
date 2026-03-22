#!/usr/bin/env python3
"""
Notebook 10: Multi-Region CTI Threshold Calibration

CRITICAL: The current system uses uniform thresholds (YELLOW=15.2) across all regions.
Finland is YELLOW 65% of the time, Poland 71%. This is broken.

This notebook computes region-specific CTI scores and recommends optimal thresholds
per region based on actual score distributions.

Methodology:
1. Load signals_50d.csv and parse region information from content/title
2. Group signals by date and source_type per region
3. Compute daily z-scores per region using 7-day rolling baseline
4. Apply CTI formula (weighted sum + trend) per region
5. Analyze score distributions per region
6. Recommend YELLOW threshold per region using percentile-based calibration
"""

import csv
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from math import sqrt

# Configuration
DATA_DIR = "../data"
OUTPUT_DIR = "../output"
METHODOLOGY_DIR = "../methodology"

# Regions to analyze
REGIONS = ["estonia", "latvia", "lithuania", "finland", "poland"]

# Source weights from composite-threat-index.md
SOURCE_WEIGHTS = {
    "gps_jamming": 20,
    "adsb_military": 15,
    "acled": 15,
    "firms": 15,
    "ais_naval": 10,
    "telegram": 10,
    "rss": 5,
    "gdelt": 5,
    "ioda": 5,
    "osint_perplexity": 5,  # treat as similar to RSS
}

# CTI formula parameters
ALPHA = 0.034  # momentum (minimal smoothing)
BETA = 0.927   # trend multiplier

print("=" * 80)
print("Multi-Region CTI Threshold Calibration")
print("=" * 80)

# ============================================================================
# 1. Load and Parse Signals
# ============================================================================
print("\n[1/5] Loading signals data...")

def detect_region(title, content, url):
    """Detect region from signal content."""
    text = f"{title} {content} {url}".lower()
    
    # Check for explicit mentions
    for region in REGIONS:
        if region in text:
            return region
    
    # Check for country-specific domains
    if ".ee/" in text or "estonia" in text:
        return "estonia"
    if ".lv/" in text or "latvia" in text:
        return "latvia"
    if ".lt/" in text or "lithuania" in text:
        return "lithuania"
    if ".fi/" in text or "finland" in text or "suomi" in text:
        return "finland"
    if ".pl/" in text or "poland" in text or "polska" in text:
        return "poland"
    
    return None

signals_by_region = {region: [] for region in REGIONS}
total_signals = 0

with open(f"{DATA_DIR}/signals_50d.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        total_signals += 1
        
        # Parse date
        try:
            pub_date = datetime.fromisoformat(row["published_at"].replace("+00", ""))
            date_key = pub_date.date()
        except:
            continue
        
        # Detect region
        region = detect_region(row["title"], row["content"], row["url"])
        if region:
            signals_by_region[region].append({
                "date": date_key,
                "source_type": row["source_type"],
            })

print(f"Total signals loaded: {total_signals:,}")
for region in REGIONS:
    print(f"  {region.capitalize()}: {len(signals_by_region[region]):,} signals")

# ============================================================================
# 2. Build Daily Signal Counts per Region
# ============================================================================
print("\n[2/5] Computing daily signal volumes per region...")

def build_daily_matrix(signals):
    """Build daily counts per source_type."""
    daily = defaultdict(lambda: defaultdict(int))
    
    for sig in signals:
        daily[sig["date"]][sig["source_type"]] += 1
    
    return daily

daily_by_region = {}
for region in REGIONS:
    daily_by_region[region] = build_daily_matrix(signals_by_region[region])
    num_days = len(daily_by_region[region])
    print(f"  {region.capitalize()}: {num_days} days of data")

# ============================================================================
# 3. Compute Z-Scores and CTI per Region
# ============================================================================
print("\n[3/5] Computing CTI scores per region...")

def compute_mean_std(values):
    """Compute mean and stddev."""
    if not values:
        return 0.0, 1.0
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    std = sqrt(variance) if variance > 0 else 1.0
    return mean, max(std, 1.0)

def compute_zscore(current, baseline_values):
    """Compute z-score for current value vs baseline."""
    if not baseline_values:
        return 0.0
    mean, std = compute_mean_std(baseline_values)
    return (current - mean) / std

def compute_cti(daily_matrix, dates):
    """Compute CTI scores for a sequence of dates."""
    cti_scores = {}
    prev_cti = 0.0
    
    # Sort dates
    sorted_dates = sorted(dates)
    
    for i, date in enumerate(sorted_dates):
        # Get baseline window (7 days before current)
        baseline_start = i - 7 if i >= 7 else 0
        baseline_dates = sorted_dates[baseline_start:i] if i > 0 else []
        
        # Compute z-scores per source
        z_scores = []
        weights = []
        
        for source_type, count in daily_matrix[date].items():
            # Get baseline values for this source
            baseline_values = [
                daily_matrix[d].get(source_type, 0) 
                for d in baseline_dates
            ]
            
            # Compute z-score
            z = compute_zscore(count, baseline_values)
            
            # Normalize to 0-100
            z_norm = min(z * 10, 100)
            
            # Get weight
            weight = SOURCE_WEIGHTS.get(source_type, 5)
            
            z_scores.append(z_norm)
            weights.append(weight)
        
        # Weighted average
        if sum(weights) > 0:
            raw_score = sum(z * w for z, w in zip(z_scores, weights)) / sum(weights)
        else:
            raw_score = 0.0
        
        # Add trend component
        trend = 0.0
        if i >= 7:
            past_date = sorted_dates[i - 7]
            if past_date in cti_scores:
                trend = raw_score - cti_scores[past_date]
        
        raw_with_trend = raw_score + BETA * trend
        
        # Apply momentum smoothing
        cti = (1 - ALPHA) * raw_with_trend + ALPHA * prev_cti
        
        cti_scores[date] = max(0.0, min(100.0, cti))
        prev_cti = cti
    
    return cti_scores

cti_by_region = {}
for region in REGIONS:
    dates = list(daily_by_region[region].keys())
    if dates:
        cti_by_region[region] = compute_cti(daily_by_region[region], dates)
        print(f"  {region.capitalize()}: {len(cti_by_region[region])} CTI scores computed")
    else:
        cti_by_region[region] = {}

# ============================================================================
# 4. Analyze Score Distributions
# ============================================================================
print("\n[4/5] Analyzing score distributions per region...")

def compute_percentiles(values, percentiles=[25, 50, 75, 90, 95]):
    """Compute percentiles of a list."""
    if not values:
        return {p: 0.0 for p in percentiles}
    
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    result = {}
    
    for p in percentiles:
        idx = int(n * p / 100)
        if idx >= n:
            idx = n - 1
        result[p] = sorted_vals[idx]
    
    return result

region_stats = {}
for region in REGIONS:
    scores = list(cti_by_region[region].values())
    if not scores:
        continue
    
    mean, std = compute_mean_std(scores)
    percentiles = compute_percentiles(scores, [25, 50, 75, 85, 90, 95])
    
    # Count days in each threshold band (using current thresholds)
    yellow_days = sum(1 for s in scores if 15.2 <= s < 59.7)
    orange_days = sum(1 for s in scores if 59.7 <= s < 92.8)
    red_days = sum(1 for s in scores if s >= 92.8)
    
    yellow_pct = (yellow_days / len(scores) * 100) if scores else 0
    
    region_stats[region] = {
        "n_days": len(scores),
        "mean": mean,
        "std": std,
        "p25": percentiles[25],
        "p50": percentiles[50],
        "p75": percentiles[75],
        "p85": percentiles[85],
        "p90": percentiles[90],
        "p95": percentiles[95],
        "yellow_days": yellow_days,
        "yellow_pct": yellow_pct,
        "max": max(scores),
    }

print("\nScore Distribution Summary:")
print("-" * 80)
print(f"{'Region':<12} {'Days':<6} {'Mean':<8} {'StdDev':<8} {'P50':<8} {'P75':<8} {'P90':<8} {'YELLOW%':<8}")
print("-" * 80)

for region in REGIONS:
    if region in region_stats:
        s = region_stats[region]
        print(f"{region.capitalize():<12} {s['n_days']:<6} {s['mean']:>7.2f} {s['std']:>7.2f} "
              f"{s['p50']:>7.2f} {s['p75']:>7.2f} {s['p90']:>7.2f} {s['yellow_pct']:>7.1f}%")

# ============================================================================
# 5. Recommend Region-Specific Thresholds
# ============================================================================
print("\n[5/5] Computing recommended thresholds per region...")

# Strategy: Use P75 as YELLOW threshold (catches elevated activity while avoiding constant alerts)
# Use P90 as ORANGE threshold
# Use P95 as RED threshold

recommended_thresholds = {}
for region in REGIONS:
    if region not in region_stats:
        continue
    
    s = region_stats[region]
    
    # Recommended: P75 for YELLOW (top 25% of days)
    # This ensures YELLOW fires on genuinely elevated days, not baseline noise
    yellow = max(s["p75"], 10.0)  # floor at 10.0
    orange = max(s["p90"], yellow * 2)  # at least 2x YELLOW
    red = max(s["p95"], orange * 1.5)  # at least 1.5x ORANGE
    
    recommended_thresholds[region] = {
        "yellow": round(yellow, 1),
        "orange": round(orange, 1),
        "red": round(red, 1),
    }
    
    print(f"\n{region.upper()}:")
    print(f"  Current YELLOW threshold: 15.2 → {s['yellow_pct']:.1f}% of days YELLOW")
    print(f"  Recommended YELLOW: {recommended_thresholds[region]['yellow']} (P75 of distribution)")
    print(f"  Recommended ORANGE: {recommended_thresholds[region]['orange']} (P90)")
    print(f"  Recommended RED: {recommended_thresholds[region]['red']} (P95)")

# ============================================================================
# 6. Write Findings
# ============================================================================
print("\n[6/6] Writing findings to methodology/...")

os.makedirs(METHODOLOGY_DIR, exist_ok=True)

findings = f"""# Regional CTI Threshold Calibration Findings

**Generated:** {datetime.now().isoformat()}

## Executive Summary

The current uniform CTI threshold (YELLOW=15.2) is **not appropriate for all regions**.

Analysis of 50 days of signal data shows significant variation in baseline threat levels:

"""

for region in REGIONS:
    if region not in region_stats:
        continue
    s = region_stats[region]
    findings += f"- **{region.capitalize()}**: YELLOW {s['yellow_pct']:.1f}% of days (current threshold)\n"

findings += f"""

## Problem

Using a single global threshold causes:
1. **High false positive rate** in high-baseline regions (Finland, Poland)
2. **Alert fatigue** — analysts see constant YELLOW, ignore real threats
3. **Reduced sensitivity** to genuine spikes in each region's context

## Methodology

1. Loaded {total_signals:,} signals from `data/signals_50d.csv`
2. Detected region from signal content (title/content/URL)
3. Computed daily signal volumes per source_type per region
4. Applied CTI formula per region:
   - 7-day rolling baseline for z-scores
   - Source-weighted aggregation (GPS jamming=20, ADS-B=15, etc.)
   - Trend component (β=0.927) and momentum smoothing (α=0.034)
5. Analyzed score distributions per region

## Findings

### Score Distributions by Region

| Region | Days | Mean | StdDev | P50 | P75 | P90 | Current YELLOW% |
|--------|------|------|--------|-----|-----|-----|-----------------|
"""

for region in REGIONS:
    if region not in region_stats:
        continue
    s = region_stats[region]
    findings += f"| {region.capitalize():<10} | {s['n_days']:<4} | {s['mean']:>5.1f} | {s['std']:>6.1f} | {s['p50']:>4.1f} | {s['p75']:>4.1f} | {s['p90']:>4.1f} | {s['yellow_pct']:>6.1f}% |\n"

findings += f"""

### Recommended Region-Specific Thresholds

Using **P75 (75th percentile)** as the YELLOW threshold ensures alerts fire on genuinely elevated days (top 25%) while avoiding constant noise.

| Region | Current YELLOW | Recommended YELLOW | Recommended ORANGE | Recommended RED |
|--------|----------------|--------------------|--------------------|-----------------|
"""

for region in REGIONS:
    if region not in recommended_thresholds:
        continue
    t = recommended_thresholds[region]
    findings += f"| {region.capitalize():<10} | 15.2 | **{t['yellow']}** | {t['orange']} | {t['red']} |\n"

findings += f"""

## Rationale

**P75 (75th percentile) for YELLOW:**
- Captures top 25% of days in each region's distribution
- Adapts to regional baseline threat levels
- Reduces false positives while maintaining sensitivity

**P90 for ORANGE, P95 for RED:**
- ORANGE = top 10% (significant multi-domain activity)
- RED = top 5% (critical threat level)

## Implementation

Update `web/lib/cti.ts` to use region-specific thresholds:

```typescript
const THRESHOLDS_BY_REGION = {{
"""

for region in REGIONS:
    if region not in recommended_thresholds:
        continue
    t = recommended_thresholds[region]
    findings += f'  "{region}": {{ yellow: {t["yellow"]}, orange: {t["orange"]}, red: {t["red"]} }},\n'

findings += f"""}}

function getThreshold(region: string): Thresholds {{
  return THRESHOLDS_BY_REGION[region] || DEFAULT_THRESHOLDS;
}}
```

## Next Steps

1. **Validate with ground truth:** Manual review of 20-30 days per region to confirm thresholds catch real threats
2. **Monitor for 7 days:** Track alert frequency and analyst feedback
3. **Iterate:** Adjust percentiles if needed (e.g., P70 vs P75 for YELLOW)

## Appendix: Raw Data

Full score distributions saved to:
- `output/10_cti_scores_by_region.csv`
- `output/10_recommended_thresholds.csv`

---

**Notebook:** `notebooks/10_multi_region_cti_calibration.py`
"""

with open(f"{METHODOLOGY_DIR}/FINDINGS.regional-calibration.md", "w") as f:
    f.write(findings)

print(f"\n✅ Findings written to: {METHODOLOGY_DIR}/FINDINGS.regional-calibration.md")

# Save thresholds as CSV
os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(f"{OUTPUT_DIR}/10_recommended_thresholds.csv", "w") as f:
    f.write("region,yellow,orange,red\n")
    for region in REGIONS:
        if region in recommended_thresholds:
            t = recommended_thresholds[region]
            f.write(f"{region},{t['yellow']},{t['orange']},{t['red']}\n")

print(f"✅ Thresholds saved to: {OUTPUT_DIR}/10_recommended_thresholds.csv")

# Save raw scores
with open(f"{OUTPUT_DIR}/10_cti_scores_by_region.csv", "w") as f:
    f.write("date,region,cti_score\n")
    for region in REGIONS:
        for date, score in cti_by_region[region].items():
            f.write(f"{date},{region},{score:.2f}\n")

print(f"✅ CTI scores saved to: {OUTPUT_DIR}/10_cti_scores_by_region.csv")

print("\n" + "=" * 80)
print("✅ ANALYSIS COMPLETE")
print("=" * 80)
print("\nKey Takeaways:")
for region in REGIONS:
    if region not in region_stats:
        continue
    s = region_stats[region]
    t = recommended_thresholds.get(region, {})
    if t:
        reduction = ((s['yellow_pct'] - 25.0) / s['yellow_pct'] * 100) if s['yellow_pct'] > 0 else 0
        print(f"  {region.capitalize()}: Reduce YELLOW alerts by ~{reduction:.0f}% (15.2 → {t['yellow']})")
