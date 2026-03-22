# Regional CTI Threshold Calibration Findings

**Generated:** 2026-03-22T10:19:50.739749

## Executive Summary

The current uniform CTI threshold (YELLOW=15.2) is **not appropriate for all regions**.

Analysis of 50 days of signal data shows significant variation in baseline threat levels:

- **Estonia**: YELLOW 28.9% of days (current threshold)
- **Latvia**: YELLOW 31.2% of days (current threshold)
- **Lithuania**: YELLOW 22.2% of days (current threshold)
- **Finland**: YELLOW 21.4% of days (current threshold)
- **Poland**: YELLOW 13.3% of days (current threshold)


## Problem

Using a single global threshold causes:
1. **High false positive rate** in high-baseline regions (Finland, Poland)
2. **Alert fatigue** — analysts see constant YELLOW, ignore real threats
3. **Reduced sensitivity** to genuine spikes in each region's context

## Methodology

1. Loaded 26,157 signals from `data/signals_50d.csv`
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
| Estonia    | 45   |  13.0 |   18.7 |  5.7 | 19.2 | 33.8 |   28.9% |
| Latvia     | 16   |  15.2 |   25.2 |  3.7 | 20.9 | 47.4 |   31.2% |
| Lithuania  | 18   |  24.4 |   34.7 |  9.7 | 29.4 | 100.0 |   22.2% |
| Finland    | 14   |  18.1 |   25.5 |  9.7 | 18.5 | 74.5 |   21.4% |
| Poland     | 15   |  13.8 |   22.9 |  3.4 | 11.4 | 55.3 |   13.3% |


### Recommended Region-Specific Thresholds

Using **P75 (75th percentile)** as the YELLOW threshold ensures alerts fire on genuinely elevated days (top 25%) while avoiding constant noise.

| Region | Current YELLOW | Recommended YELLOW | Recommended ORANGE | Recommended RED |
|--------|----------------|--------------------|--------------------|-----------------|
| Estonia    | 15.2 | **19.2** | 38.3 | 57.5 |
| Latvia     | 15.2 | **20.9** | 47.4 | 97.1 |
| Lithuania  | 15.2 | **29.4** | 100.0 | 150.0 |
| Finland    | 15.2 | **18.5** | 74.5 | 111.7 |
| Poland     | 15.2 | **11.4** | 55.3 | 83.0 |


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
const THRESHOLDS_BY_REGION = {
  "estonia": { yellow: 19.2, orange: 38.3, red: 57.5 },
  "latvia": { yellow: 20.9, orange: 47.4, red: 97.1 },
  "lithuania": { yellow: 29.4, orange: 100.0, red: 150.0 },
  "finland": { yellow: 18.5, orange: 74.5, red: 111.7 },
  "poland": { yellow: 11.4, orange: 55.3, red: 83.0 },
}

function getThreshold(region: string): Thresholds {
  return THRESHOLDS_BY_REGION[region] || DEFAULT_THRESHOLDS;
}
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
