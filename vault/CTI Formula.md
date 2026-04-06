---
status: evergreen
tags: [cti, formula, diagnostics]
---

# CTI Formula

The Composite Threat Index combines 30+ data sources into a single threat level (GREEN / YELLOW / ORANGE / RED) per region. This track diagnosed why it's **stuck at YELLOW 80% of the time** and proposed fixes.

## The Bug: Permanent YELLOW

On 80% of active days (Mar 7–25), CTI ≥ 15.2 (YELLOW threshold) regardless of actual threat conditions. Root causes:

1. **FIMI scoring inflated** — campaigns + laundering alone produce 76% of the YELLOW threshold
2. **Evidence-free campaigns** — 70% of campaigns lack detection evidence but contribute 73% of max severity
3. **Laundering noise** — 73% of laundering events are irrelevant (sports, domestic RU news)
4. **Dead collectors** — 12+ sources died Mar 15–20, still weighted in formula

## Diagnostic Chain (nb14 → 15 → 16 → 17)

Each notebook peels back one layer:

| Notebook | Question | Answer |
|----------|----------|--------|
| `14_fimi_floor_decomposition` | What drives the FIMI floor? | Campaigns (43%) + laundering (19%) |
| `15_laundering_audit` | How much laundering is noise? | 73% — relevance filter cuts score 80% |
| `16_campaign_scoring_audit` | Do campaigns have evidence? | 70% don't — evidence tiers remove phantom severity |
| `17_robust_baselines` | Are baselines stable? | No — median+MAD beats mean+std for all sources |

This diagnostic chain is **reproducible and solid**. The findings are safe to act on.

## What's Deployed

| Fix | Source | Impact |
|-----|--------|--------|
| Laundering relevance filter | nb15 | 80% noise reduction in laundering score |
| Campaign evidence gate | nb16 | Evidence-free campaigns scored lower |
| Robust baselines (median+MAD) | nb17 | Stable z-scores for all sources |
| DEGRADED flag | nb18 | Days with missing collectors marked |
| Dead collector weight = 0 | nb18 | ACLED, IODA zeroed out |

## What's NOT Deployed (and Why)

| Proposal | Source | Problem |
|----------|--------|---------|
| Weight total 72 → 24 | nb18 | Too aggressive — algorithm produces near-zero scores 30 of 50 days |
| YELLOW = 7.9 | nb19 | Calibrated on the broken algorithm — circular validation |
| Per-region thresholds | nb01 | <10 data points per region |

**The moderate path** (from `../methodology/VALIDITY.md`): weight total ~45, keeping FIMI share at ~46%. Requires 90+ days of stable collector data first (R-35 in roadmap).

## Key Numbers

| Metric | Value | Source |
|--------|-------|--------|
| Days stuck at YELLOW | 80% of active period | nb06, nb12 |
| FIMI contribution to YELLOW | 76% of threshold | nb14 |
| Laundering false positive rate | 73% | nb15 |
| Campaigns without evidence | 70% (26 of 37) | nb16 |
| Dead collectors | 12+ since Mar 15–20 | nb09 |
| Current weight total | 72 (signal) + 38 (FIMI) = 110 | algorithm spec |
| Proposed moderate total | ~45 (signal) + 38 (FIMI) = ~83 | VALIDITY.md |

## Experiments

| # | Notebook | Domain |
|---|----------|--------|
| 01 | `01_regional_cti_calibration` | Per-region thresholds |
| 06 | `06_cti_decomposition` | CTI component breakdown |
| 07 | `07_cti_false_positive_audit` | False positive catalogue |
| 08 | `08_threshold_recalibration` | Initial threshold analysis |
| 12 | `12_honest_cti_assessment` | End-to-end critique |
| 14 | `14_fimi_floor_decomposition` | FIMI sub-component analysis |
| 15 | `15_laundering_audit` | Laundering noise classification |
| 16 | `16_campaign_scoring_audit` | Campaign evidence tiers |
| 17 | `17_robust_baselines` | Per-source baseline methods |
| 18 | `18_weight_recalibration` | Weight optimization |
| 19 | `19_threshold_final` | Final threshold calibration |
| 35 | `35_moderate_weights` | Moderate weight path |

## Deep Dives

- `../methodology/FINDINGS.md` — Part 1 (CTI Formula Fixes)
- `../methodology/FINDINGS.cti-fimi-floor.md` — FIMI floor decomposition detail
- `../methodology/FINDINGS.robust-baselines.md` — Baseline method comparison
- `../methodology/FINDINGS.threshold-recalibration.md` — Threshold analysis detail
- `../methodology/FINDINGS.regional-calibration.md` — Per-region calibration
- `../methodology/VALIDITY.md` — Why proposed fixes are too aggressive

## Next Steps

1. **Fix collectors** (F-01) — prerequisite for everything
2. **Accumulate 90 days** of stable data under corrected algorithm
3. **Moderate weight recalibration** (R-35) — target ~45 total
4. **Re-derive thresholds** on clean data with external ground truth
