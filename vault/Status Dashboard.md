---
status: evergreen
tags: [status, tracking, deployment]
---

# Status Dashboard

Current state of all research tracks. Updated from `../RESEARCH-SPECS.md` (2026-03-29).

## Deployment Status

### Safe to Deploy

| Finding | Source | Confidence | Notes |
|---------|--------|------------|-------|
| Laundering relevance filter | nb15 (R-003) | HIGH | 80% noise reduction. Already deployed. |
| Campaign evidence gate | nb16 (R-004) | HIGH | Evidence-free campaigns scored lower. Already deployed. |
| Robust baselines (median+MAD) | nb17 (R-005) | MEDIUM | Outperforms standard z-scores. Already deployed. |
| DEGRADED flag | nb18 | HIGH | Marks days with missing collectors. Already deployed. |
| Dead collector weight = 0 | nb18 | HIGH | ACLED, IODA zeroed. Already deployed. |
| Two-pass clustering | nb26 (D-001) | HIGH | Fixes mega-cluster problem. Already deployed. |
| Keep factual IBI prompt | nb28 (D-007) | HIGH | Intent-based over-triggers. Already deployed. |
| AIS binary mode | nb33 | HIGH | Removes throughput-swing noise. Already deployed. |

### DO NOT Deploy

| Proposal | Source | Problem |
|----------|--------|---------|
| Weight total 72 → 24 | nb18 (R-006) | Algorithm produces near-zero scores. Too aggressive. |
| YELLOW = 7.9 | nb19 (R-007) | Calibrated on broken algorithm. Circular validation. |
| Narrative velocity alerts | nb27 (D-003) | F1=1.00 on N=8 is meaningless. Need 30+ narratives. |
| Fisher pre-screen alone | nb25 (D-002) | F1=0.615 at N=30. Did NOT replicate F1=0.92. |

### Needs More Data

| Proposal | Source | What's Needed |
|----------|--------|---------------|
| Moderate weights ~45 | R-35 | 90+ days stable collector data |
| Fisher + Hawkes combo | R-40 | 33+ labeled hostile clusters |
| FIMI regex for ET/LV/LT | D-005 | Language samples + linguist review |
| Per-region thresholds | R-001 | 10+ data points per region (currently <10) |
| CCDC operational alerts | S-003 | 10+ confirmed ISW matches (currently 1) |

## Track Status Summary

| Track | Diagnostics | Prescriptions | Blocker |
|-------|-------------|---------------|---------|
| [[CTI Formula]] | COMPLETE | PARTIAL | Need 90 days stable data |
| [[Campaign Detection]] | COMPLETE | INSUFFICIENT | Need 33+ hostile labels |
| [[Satellite Monitoring]] | VALIDATED | BROKEN | Sentinel-2 collector dead |
| [[Data Quality]] | IDENTIFIED | IN PROGRESS | Ops work, not research |

## Critical Path

```
F-01: Fix collectors ← YOU ARE HERE
  ↓
F-02: Expand watchlist
F-03: Add Baltic feeds
F-04: Fix category metadata
  ↓
R-35: Moderate weight recalibration (weeks 2-6)
  ↓
R-38: Build labeled dataset (weeks 4-8)
  ↓
R-40: Fisher + Hawkes validation (weeks 6-10)
  ↓
Deploy origin-agnostic detection
```

## Confidence Levels

| Level | Meaning | Count |
|-------|---------|-------|
| HIGH | Reproducible, sufficient N, safe to act on | 8 findings |
| MEDIUM | Directional, needs more data | 5 findings |
| LOW | Insufficient validation, do not deploy | 4 findings |
| NOT VALIDATED | Prototype only, no labeled data | 2 findings |

Full details: `../RESEARCH-SPECS.md`
Validity assessment: `../methodology/VALIDITY.md`
