---
status: evergreen
tags: [overview, mind-map, patterns]
---

# Research Mind Map

Six core patterns that repeat across every research track. Understand these and the rest is detail.

## 1. Garbage In, Garbage Out

The CTI fuses 30+ data sources into one threat score. When sources break, the score breaks.

- 12+ collectors died Mar 15–20
- 76% of study days are DEGRADED
- AIS has 4x throughput swings from collector instability (not naval activity)
- ADS-B has 76% military aircraft misclassification

**No formula fix matters until inputs stabilize.** This is why [[Data Quality]] is the primary blocker for everything.

## 2. Small N Kills Claims

Every detection method hits the same wall: not enough labeled hostile data.

| Method | Claimed | Actual | Why | N needed |
|--------|---------|--------|-----|----------|
| Fisher discriminant | F1=0.92 | F1=0.615 | 6 hostile clusters | 33+ |
| Narrative velocity | F1=1.00 | meaningless | 8 labeled narratives | 30+ |
| Hawkes branching ratio | — | p=0.04 | 281 clusters, directional | solid for now |
| FIMI regex | — | 80% pre-screen | 30 samples, RU/EN only | extend to ET/LV/LT |

The fix is a labeled dataset expansion (R-38 in `../ROADMAP.md`). Until then, treat all detection thresholds as provisional.

## 3. Diagnostics Are Easy, Prescriptions Are Hard

Finding bugs is straightforward. Fixing them requires stable data over time.

| Type | Example | Status |
|------|---------|--------|
| Diagnostic | Laundering is 73% noise | SOLID — deployed |
| Diagnostic | 70% of campaigns lack evidence | SOLID — deployed |
| Diagnostic | 12 collectors are dead | SOLID — confirmed |
| Prescription | New weight total = 24 | TOO AGGRESSIVE — do not deploy |
| Prescription | YELLOW threshold = 7.9 | CALIBRATED ON BROKEN DATA — do not deploy |
| Prescription | Moderate weights ~45 | PROPOSED — needs 90 days validation |

**Rule:** deploy diagnostic fixes (remove known noise). Defer prescriptive fixes (new thresholds) until 90+ days of stable data exist.

## 4. Multi-Sensor Fusion Is the Goal

The vision: satellite + SIGINT + media + maritime AIS → one coherent threat picture.
The reality: each sensor has its own validation crisis.

| Sensor | State | Blocker |
|--------|-------|---------|
| Media / FIMI | Architecture deployed | Only 6 hostile labels |
| Satellite | Methods validated | Collector dead since Mar 14 |
| Maritime (AIS) | Data flowing | 4x throughput swings |
| Aviation (ADS-B) | Data flowing | 76% misclassification |
| GPS jamming | Strongest signal source | Data on only 15 of 88 days |

The Dempster-Shafer fusion engine was deleted in a migration. Rebuilding requires each sensor to work individually first.

## 5. Self-Referential Ground Truth

The system optimizes against its own (broken) labels:

- CTI thresholds optimized against historical CTI levels from the broken algorithm
- Campaign labels created by the broken detection system
- Cluster hostility rated by the broken FIMI scorer

**External ground truth needed:** ISW timeline, ACLED conflict events, EU DisinfoLab reports, labeled hostile examples from domain experts.

## 6. Critical Path Is Sequential

```
Fix collectors (F-01)
    ↓ stable for 2+ weeks
Accumulate 90 days of clean data
    ↓ enough data
Recalibrate weights (~45 total)
    ↓ validated weights
Recalibrate thresholds (YELLOW / ORANGE / RED)
    ↓ validated thresholds
Validate detection methods (Fisher + Hawkes combo)
    ↓ labeled dataset ≥33 hostile
Deploy origin-agnostic detection
```

Cannot parallelize. Each step depends on the previous one producing stable output.

## How the Tracks Connect

```
[[Data Quality]]  ──blocks──→  [[CTI Formula]]  ──blocks──→  [[Campaign Detection]]
       ↑                                                              ↓
[[Satellite Monitoring]]  ←──────── fusion requires all ─────────────┘
```

Everything bottlenecks on [[Data Quality]]. Fix collectors first, then formula, then detection, then fusion.
