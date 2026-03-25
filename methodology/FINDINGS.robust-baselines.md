# FINDINGS: Robust Baseline Methods Per Source

**Notebook:** `17_robust_baselines.py`
**Date:** 2026-03-25
**Builds on:** Experiments 10 (baseline stability), 11 (signal value analysis)

## Summary

Standard z-scores (`z = (x - mean_7d) / std_7d`) fail for most CTI sources because:
1. High coefficient of variation (CV > 100%) makes normal variance indistinguishable from anomalies
2. Collector downtime creates extreme outliers in the baseline window
3. Collector regime changes (upgrades, new feeds) cause false anomaly spikes

**Key finding:** Robust z-scores using median + MAD are strictly superior to mean + std
in all tested cases. For sources with CV > 100% even after downtime exclusion, only
binary detection (above/below median) is reliable.

## Method Definitions

### Method 1: Standard Z-Score (current production)
```
z = (x - mean_7d) / max(std_7d, 1)
```
- Works for stable sources (CV < 30%)
- Sensitive to outliers: one downtime day in the 7-day window distorts both mean and std

### Method 2: Robust Z-Score (RECOMMENDED DEFAULT)
```
z = (x - median_7d) / max(MAD_7d × 1.4826, 1)
MAD = median(|xᵢ - median|)
```
- The 1.4826 scaling factor makes MAD a consistent estimator of σ for Gaussian data
- Resistant to up to 50% outliers in the window (breakdown point = 0.5)
- Works for sources with CV < 60% after downtime exclusion

### Method 3: Log-Transformed Z-Score
```
z = (log(x+1) - mean_log_7d) / max(std_log_7d, 0.5)
```
- Compresses dynamic range for sources with 10×-100× volume swings
- Useful when counts range from single digits to thousands (e.g., RSS, GDELT)
- log(0+1) = 0 handles zero-count days naturally

### Method 4: Binary Detection
```
score = 1 if x > median_7d else 0
```
- No z-score at all — just "above or below recent normal"
- For sources where magnitude is meaningless or too volatile
- Contributes a fixed weight fraction to CTI when active, zero when not

## Downtime Exclusion Rule

**Before computing any baseline, exclude downtime days:**
```
A day is DOWNTIME if:
  1. The source has zero signals AND
  2. The source has reported data in the previous 3 days AND
  3. The source will report data again within 3 days
```

Days before the first observation or after the last are NOT downtime.
This prevents collector gaps from poisoning the rolling baseline window.

## Recommendations Per Source

| Source | Weight | Method | Clean CV% | Formula | Zero-Day Handling |
|--------|--------|--------|-----------|---------|-------------------|
| gpsjam | 12→12 | standard_z | 13 | `z = (x - mean_7d) / max(std_7d, 1)` | Exclude 3 downtime days from baseline window. |
| adsb | 10→5 | binary | 134 | `score = 1 if x > median_7d else 0` | Exclude downtime from median computation. |
| acled | 8→0 | DISABLED | — | `contribution = 0` | N/A |
| firms | 8→6 | robust_z | 97 | `z = (x - median_7d) / max(MAD_7d × 1.4826, 1)` | Exclude downtime days. |
| ais | 6→3 | binary | 118 | `score = 1 if x > median_7d else 0` | Exclude downtime from median computation. |
| telegram | 6→4 | robust_z | 64 | `z = (x - median_7d) / max(MAD_7d × 1.4826, 1)` | Exclude downtime days. |
| energy | 6→3 | binary | 166 | `score = 1 if x > median_7d else 0` | Exclude downtime from median computation. |
| rss | 4→2 | binary | 206 | `score = 1 if x > median_7d else 0` | Exclude downtime from median computation. |
| gdelt | 4→2 | binary | 258 | `score = 1 if x > median_7d else 0` | Exclude downtime from median computation. |
| business | 4→2 | binary | 73 | `score = 1 if x > median_7d else 0` | Missing day = 0 (not firing). |
| ioda | 4→0 | DISABLED | — | `contribution = 0` | N/A |

## Collector Health Summary

| Source | Data Days | Downtime Days | Availability % | Status |
|--------|-----------|---------------|----------------|--------|
| gpsjam | 14 | 3 | 82% | ✅ |
| adsb | 13 | 4 | 76% | ⚠️ |
| acled | 0 | — | 0% | ❌ DEAD |
| firms | 17 | 3 | 85% | ✅ |
| ais | 18 | 0 | 100% | ✅ |
| telegram | 17 | 69 | 20% | ❌ |
| energy | 20 | 0 | 100% | ✅ |
| rss | 75 | 12 | 86% | ✅ |
| gdelt | 58 | 25 | 70% | ⚠️ |
| business | 17 | 3 | 85% | ✅ |
| ioda | 0 | — | 0% | ❌ DEAD |

## DEGRADED Mode Proposal

When the sum of weights for sources that reported data in the last 24 hours
falls below 70% of the total CTI weight, the score should be flagged as DEGRADED:

```go
liveWeight := sumWeightsForActiveSources(last24h)
totalWeight := 110  // sum of all source weights
if float64(liveWeight) / float64(totalWeight) < 0.70 {
    cti.Status = "DEGRADED"
    cti.Reliability = float64(liveWeight) / float64(totalWeight)
}
```

Display: `CTI score 18.5 (DEGRADED: 45% of sensors reporting)`

This prevents false confidence in CTI scores when most collectors are down.

## Honest Limitations

1. **Weak ground truth:** CTI YELLOW days are mostly FIMI-driven, not sensor-driven.
   Method evaluation is based on statistical properties, not validated against labeled
   military events.

2. **Small sample sizes:** GPSjam has only 14 data points. ADS-B and FIRMS have
   meaningful data for only ~2 weeks. Statistical conclusions are tentative.

3. **Collector instability is the real problem:** No mathematical method can fix
   broken data collection. AIS going from 37 to 141K signals/day is a collector
   issue, not a baseline method issue.

4. **Regime changes:** When collectors are fixed/upgraded, there's a step change
   in volume that any z-score method will flag. Need a 7-day burn-in period after
   regime changes to prevent false anomalies.

## Production Implementation Checklist

- [ ] Switch default z-score to robust (median + MAD × 1.4826)
- [ ] Add downtime exclusion to baseline window computation
- [ ] Set weight=0 for sources with no data (acled, ioda)
- [ ] Add DEGRADED flag when live weight < 70%
- [ ] Add 7-day burn-in after collector regime change detection
- [ ] Log which baseline method is used per source per computation
