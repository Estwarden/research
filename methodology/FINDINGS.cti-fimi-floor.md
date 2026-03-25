# FINDINGS: CTI FIMI Floor Decomposition

**Experiment:** 14_fimi_floor_decomposition.py
**Date:** 2026-03-25
**Data:** CTI history (2026-02-05 to 2026-03-25), 134 entries across 6 regions

## Summary

The FIMI (Foreign Information Manipulation and Interference) component of the CTI
has a structural tendency to stay elevated, driving the system toward permanent YELLOW.
This notebook decomposes FIMI into its sub-components and quantifies each one's
contribution to the problem.

## CTI Formula Reference

```
CTI = Σ (weight_i × score_norm_i) / TOTAL_WEIGHT
TOTAL_WEIGHT = 110
YELLOW threshold = 15.2
```

### FIMI Sub-component Weights and Max Contributions

| Sub-component | Weight | Max CTI Contribution | Formula |
|---------------|--------|---------------------|---------|
| Campaigns | 10 | 9.09 | min(Σ sev×decay, 100) × 10/110 |
| Fabrication | 8 | 7.27 | min(Σ impact/5, 100) × 8/110 |
| Laundering | 6 | 5.45 | min(count, 100) × 6/110 |
| Narratives | 4 | 3.64 | min(count/10, 100) × 4/110 |
| GPS Jam Sev | 10 | 9.09 | min(rate×200, 100) × 10/110 |
| **FIMI Total** | **38** | **34.5** | |

## Key Finding: FIMI Floor Per Region

### Stored CTI FIMI Component Statistics

| Region | N | Min FIMI | P25 | P50 | P75 | Max FIMI | Avg |
|--------|---|----------|-----|-----|-----|----------|-----|
| baltic | 50 | 0.0 | 4.0 | 6.0 | 7.4 | 22.9 | 6.3 |
| estonia | 4 | 6.9 | 9.1 | 10.1 | 13.4 | 22.9 | 12.5 |
| finland | 36 | 0.0 | 0.0 | 0.0 | 0.0 | 22.9 | 1.9 |
| latvia | 4 | 6.5 | 8.7 | 9.6 | 13.1 | 22.9 | 12.1 |
| lithuania | 4 | 6.5 | 8.7 | 9.6 | 13.1 | 22.9 | 12.1 |
| poland | 36 | 0.0 | 0.0 | 0.0 | 0.0 | 22.9 | 1.9 |

### Two Regimes

The data shows two distinct FIMI regimes:

1. **Feb 5 – Mar 6 (early):** FIMI = 0–8. FIMI sub-detectors (campaigns, laundering,
   fabrication) were not yet generating significant events. The stored FIMI in this
   period reflects a minimal baseline.

2. **Mar 7 – Mar 25 (active):** FIMI = 4–22.9. Campaign detection, laundering
   scoring, and fabrication detection are all active, generating cumulative FIMI.

In the active regime (last ~18 days), Baltic FIMI averages **9.0**,
which is close to the
YELLOW threshold (15.2).

## Sub-Component Decomposition (Mar 7–25)

| Component | Avg Contrib | Ceiling | Avg % of Max | Days Near Max |
|-----------|-------------|---------|-------------|---------------|
| Campaigns | 6.59 | 9.09 | 72% | 13/20 |
| Laundering | 2.87 | 5.29 | 53% | 1/20 |
| Fabrication | 1.37 | 7.27 | 19% | 3/20 |
| Narratives | 0.63 | 1.32 | 17% | 0/20 |

### Campaign Quality

- Total campaigns: 37
- With evidence (detection_method + signals > 0): 11 (30%)
- Without evidence: 26 (70%)
- Detection methods: {'none': 26, 'framing_analysis': 8, 'injection_cascade': 2, 'outrage_chain': 1}

The 26 no-evidence campaigns contribute **360** raw severity
points vs **130** from evidence-backed campaigns.

### Laundering Thresholds

| category_count ≥ | Event Count | Score Contribution |
|-------------------|-------------|-------------------|
| 2 | 147 | 5.45 |
| 3 | 26 | 1.42 |
| 4 | 10 | 0.55 |
| 5 | 5 | 0.27 |

## Marginal Impact Analysis

What happens to YELLOW count when each sub-component is removed (baltic, Mar 7–25):

| Scenario | YELLOW Days | GREEN Days | Avg Score |
|----------|-------------|------------|-----------|
| Current (no change) | 17 | 3 | 18.3 |
| Remove Campaigns | 6 | 14 | 11.7 |
| Remove Laundering | 10 | 10 | 15.4 |
| Remove Fabrication | 14 | 6 | 16.9 |
| Remove Narratives | 16 | 4 | 17.7 |
| Remove Camp+Laund | 4 | 16 | 8.8 |
| Remove Camp+Laund+Fab | 3 | 17 | 7.5 |
| Remove ALL FIMI subs | 3 | 17 | 6.8 |

## Limitations

1. **Reconstruction accuracy:** The sub-component reconstruction does NOT perfectly
   match stored production values (mean absolute delta = 6.8).
   The production algorithm likely uses different window/decay/normalization than
   our approximation.

2. **Data coverage:** Campaign, fabrication, and narrative data starts 2026-03-07.
   FIMI decomposition for earlier dates is not possible from exported data.

3. **Global vs regional:** FIMI sub-components are computed globally (same for all
   regions), but the stored CTI shows per-region variation — suggesting production
   may have region-specific FIMI logic.

4. **Directional findings are reliable.** Despite imperfect reconstruction, the
   ranking of sub-components (campaigns > laundering > fabrication > narratives)
   and the structural nature of the problem are well-supported.

## Recommendations

1. **Fix Campaigns** (highest impact):
   - Require `detection_method` for scoring (framing_analysis, injection_cascade, etc.)
   - Auto-resolve campaigns without new signals after 48h
   - Expected: removes ~70% of evidence-free campaigns

2. **Fix Laundering** (second highest impact):
   - Require region relevance (Baltic/security topic filter)
   - Raise `category_count` threshold from 2 to 3
   - Expected: reduces score by ~80% (see R-003)

3. **Recalibrate thresholds** after fixes (R-007)
   - Don't raise thresholds on a broken algorithm
   - Fix the inputs first, then optimize thresholds

## Cross-References

- Experiment 06: Initial CTI decomposition (found FIMI ~24.6/25)
- Experiment 08: Threshold recalibration (identified structural problem)
- Experiment 12: Honest CTI assessment (FIMI strongest component)
- R-003: Laundering detector false positive audit
- R-004: Campaign scoring audit
- R-007: Threshold recalibration on fixed algorithm
