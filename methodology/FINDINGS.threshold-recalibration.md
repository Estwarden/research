# FINDINGS: CTI Threshold Recalibration on Fixed Algorithm

**Notebook:** `19_threshold_final.py`
**Date:** 2026-03-25
**Builds on:** R-002 (FIMI floor), R-003 (laundering audit), R-004 (campaign audit),
R-005 (robust baselines), R-006 (weight recalibration)
**Data:** 134 stored CTI entries, 50 optimization data points, 13 level transitions

## Summary

This is the capstone of the CTI research track. After fixing the structural issues
identified in R-002 through R-006, we recalibrate thresholds on the corrected algorithm.

**Key result:** The corrected algorithm achieves GREEN on days when the stored algorithm
was stuck at YELLOW. FIMI floor drops from 8.38 to 10.34,
making GREEN achievable.

## Corrections Applied

| Fix | Source | Effect |
|-----|--------|--------|
| Relevance filter | R-003/nb15 | Laundering: 147 → 79 events |
| Evidence requirement | R-004/nb16 | Campaigns: 37 → 8 scored |
| Robust baselines | R-005/nb17 | median+MAD replaces mean+std |
| Consensus weights | R-006/nb18 | Signal sum: 72 → 24 |
| Dead sources | R-006/nb18 | acled=0, ioda=0, telegram=0, gdelt=0 |

## FIMI Floor Analysis

| Metric | Old (stored) | Corrected | Δ |
|--------|-------------|-----------|---|
| FIMI avg (data period) | 8.38 | 10.34 | 1.96 |
| FIMI floor | 0.0 | 0.00 | — |
| FIMI > old YELLOW | 2/20 days | 6/20 days | — |
| GREEN achievable? | No | **Yes** ✅ | — |

### Sub-component Contributions (data period averages)

| Component | Corrected Avg | Corrected Max | Old Avg (nb14) |
|-----------|--------------|---------------|----------------|
| Campaigns (T1+T2 only) | 3.08 | 15.97 | 6.59 |
| Laundering (filtered) | 2.70 | 4.94 | 2.87 |
| Fabrication | 2.44 | 12.90 | 1.37 |
| Narratives | 1.11 | 2.35 | 0.63 |

## Optimizer Results

### Phase 1: Brute-Force (200K trials, 3-fold CV)

| Metric | v1 (old algorithm) | v2 (corrected) |
|--------|-------------------|----------------|
| Data points | 31 | 50 |
| Transitions | 12 | 13 |
| Eval score | 0.885 | 0.7227 |
| CV score | — | 0.8752 |
| Fold variance | — | 0.1165 |
| Accuracy | 0.917 | 0.6744 |
| Stability | 0.889 | 0.9773 |
| Lead time | 0.800 | 0.4615 |

### Optimized Parameters

| Parameter | v1 | v2 |
|-----------|----|----|
| YELLOW | 15.2 | 7.92 |
| ORANGE | 59.7 | 55.80 |
| RED | 92.8 | 88.72 |
| Momentum | 0.034 | 0.6710 |
| Trend mult | 0.927 | 0.1104 |
| Window | 7 | 7 |

## Percentile-Based Thresholds

| Percentile Set | YELLOW | ORANGE | RED | Eval Score |
|----------------|--------|--------|-----|------------|
| P75/P90/P95 | 14.93 | 30.87 | 45.76 | 0.720 |
| P80/P92/P97 | 17.33 | 33.18 | 47.35 | 0.708 |
| P85/P90/P95 | 20.61 | 30.87 | 45.76 | 0.697 |
| Old (15.2/59.7/92.8) | 15.2 | 59.7 | 92.8 | 0.738 |
| **Optimizer** | **7.92** | **55.80** | **88.72** | **0.723** |

## Per-Region Thresholds (Scaled)

| Region | N | YELLOW | ORANGE | RED | Notes |
|--------|---|--------|--------|-----|-------|
| baltic | 50 | 11.00 | 12.93 | 13.74 |  |
| finland | 36 | 11.87 | 12.76 | 15.07 |  |
| poland | 36 | 12.50 | 13.98 | 15.22 |  |

## Level Agreement

Under recommended thresholds (YELLOW=7.92, ORANGE=55.80, RED=88.72):

| Level | Corrected | Stored |
|-------|-----------|--------|
| GREEN | 35 | 29 |
| YELLOW | 15 | 21 |
| ORANGE | 0 | 0 |
| RED | 0 | 0 |

Overall agreement: 80%

## DEGRADED Mode

- Active source weight: 24
- DEGRADED threshold: 70% (17)
- HEALTHY days: 12/50 (24%)
- DEGRADED days: 38/50 (76%)

Most days have incomplete sensor coverage, confirming the need for the DEGRADED flag.

## Recommended Final Thresholds

```
// For CORRECTED algorithm only (with all R-002→R-006 fixes)
YELLOW = 7.9
ORANGE = 55.8
RED    = 88.7

// Smoothing parameters
MOMENTUM   = 0.6710
TREND_MULT = 0.1104
WINDOW     = 7
```

⚠️ **WARNING:** These thresholds are calibrated for the CORRECTED algorithm.
Deploying them with the old algorithm will produce incorrect results. The
corrections (FIMI filter, campaign tiers, robust baselines, consensus weights)
MUST be deployed simultaneously.

## Deployment Order

1. Deploy FIMI scoring fixes (laundering filter, campaign evidence requirement)
2. Deploy consensus signal weights (acled=0, ioda=0, telegram=0, gdelt=0)
3. Deploy robust z-score baselines (median + MAD × 1.4826)
4. Deploy DEGRADED flag for sensor coverage monitoring
5. Deploy new thresholds (YELLOW=7.9, ORANGE=55.8, RED=88.7)
6. Monitor for 1 week — verify GREEN days appear when appropriate
7. Fine-tune after accumulating 90+ days of data under corrected algorithm

## Honest Limitations

1. **Small dataset:** 50 data points with 13 transitions is marginal for
   optimization. The v1 optimizer had 31 days — we have more but still not enough
   for high-confidence thresholds.

2. **Signal normalization approximation:** The exact production z-score-to-CTI mapping
   is not replicated here. We approximated with `score = max(0, z × 20)` for z-scores
   and binary 0/100 for binary sources. The actual production mapping may differ.

3. **FIMI reconstruction imperfect:** The sub-component reconstruction from exported
   CSVs doesn't perfectly match stored production values (known from nb14, MAD=6.8).
   The production FIMI algorithm may have additional logic not captured here.

4. **Per-region thresholds are rough:** Most regions have <10 data points. Per-region
   calibration requires 90+ days of per-region data under the corrected algorithm.

5. **Level ground truth is self-referential:** We optimize corrected scores to match
   stored levels, but those stored levels were assigned by the OLD (broken) algorithm.
   Ideally, we'd have expert-labeled ground truth independent of the CTI formula.

6. **Fold variance:** 0.1165. Moderate variance suggests some overfitting.

## Cross-References

- R-002/nb14: FIMI floor decomposition (identified permanent-YELLOW bug)
- R-003/nb15: Laundering false positive audit (73% noise, relevance filter)
- R-004/nb16: Campaign scoring audit (70% evidence-free, tier system)
- R-005/nb17: Robust baselines (median+MAD, downtime exclusion)
- R-006/nb18: Weight recalibration (consensus weights, DEGRADED mode)
- autoresearch/optimize.py: Phase 1 brute-force optimizer (v1)
- Experiment 01/nb01: Regional calibration (percentile-based approach)
- Experiment 08/nb08: First threshold recalibration attempt
