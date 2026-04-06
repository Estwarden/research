---
status: evergreen
tags: [campaigns, detection, fimi, nlp]
---

# Campaign Detection

Detecting hostile disinformation campaigns across languages and platforms. The architecture is deployed, but statistical validation is insufficient — primarily because we only have **6 labeled hostile clusters**.

## Methods

Five detection approaches tested, each catching different signals:

### Fisher Pre-Screen (nb25)

Linear discriminant: `score = 0.670 * state_ratio + 0.742 * fimi_score`

- **Claimed:** F1 = 0.92
- **Actual:** F1 = 0.615 (LOO at N=30, bootstrap CI [0.333, 1.000])
- **Why it failed:** Only 6 hostile samples. The original F1=0.92 used a different dataset split.
- **Status:** LOW confidence. May recover with Hawkes BR as third feature (R-40).

### Hawkes Coordination (nb24)

Models information cascades as self-exciting point processes. Measures how much one signal triggers another.

- **Finding:** State-heavy clusters BR=0.53 vs clean clusters BR=0.22 (p=0.04, N=281)
- **Interpretation:** Hostile clusters show 2.4x more coordination
- **Status:** MEDIUM confidence. Most promising single metric. Directional, needs more hostile labels.

### Narrative Velocity (nb27)

Tracks week-over-week change in state media ratio within a narrative.

- **Claimed:** F1 = 1.00
- **Actual:** Meaningless — fitted 2 parameters on 8 data points
- **Status:** LOW. Concept is sound (weaponization shows velocity spike), but needs 30+ narratives.

### FIMI Regex (nb29)

Pattern-based pre-screen: hedging language ("allegedly", "so-called") and amplification markers.

- **Finding:** Catches 80% of hostile clusters without LLM, tested on N=30
- **Limitation:** RU/EN only. Needs extension to ET/LV/LT.
- **Status:** MEDIUM confidence. Cost-effective first filter.

### Co-Coverage Network (nb30)

Measures how often sources cover the same stories (Jaccard similarity).

- **Finding:** State media Jaccard = 0.26 vs trusted = 0.16 (63% coordination premium)
- **Status:** MEDIUM. Structural and stable. Measures editorial coordination, not content hostility.

## What's Deployed

| Component | Status |
|-----------|--------|
| Cosine 0.75 clustering + two-pass | Deployed (nb26, D-001) |
| Keep current IBI prompt (not intent-based) | Deployed (nb28, D-007) |
| Fisher / Hawkes / Velocity / Regex | NOT deployed — insufficient validation |

## The Labeled Data Problem

All detection methods are blocked on the same thing: **not enough hostile examples**.

| Current | Needed | Gap |
|---------|--------|-----|
| 6 hostile clusters | 33+ for p<0.01 | R-38 labeled dataset task |
| 8 labeled narratives | 30+ for velocity thresholds | R-38 |
| 0 cascade labels | 100+ for topology classifier | R-38 |

R-38 (`38_labeled_dataset.py`) is the single most important roadmap item for this track.

## Experiments

| # | Notebook | Method |
|---|----------|--------|
| 03 | `03_claim_drift_detection` | Fabrication per amplification hop |
| 04 | `04_cascade_topology_classifier` | Graph structure for manipulation |
| 05 | `05_coordination_detection` | Burstiness analysis |
| 13 | `13_campaign_verification` | Campaign detection audit |
| 24 | `24_hawkes_coordination` | Hawkes branching ratio |
| 25 | `25_fisher_revalidation` | Fisher discriminant retest |
| 26 | `26_cluster_quality` | Clustering parameter tuning |
| 27 | `27_narrative_velocity` | Weaponization speed metric |
| 28 | `28_ibi_prompt_test` | Intent-based vs factual prompting |
| 29 | `29_fimi_regex` | Regex-based FIMI pre-screen |
| 30 | `30_cocoverage_network` | Source coordination patterns |
| 31 | `31_fabrication_stability` | Fabrication score stability |
| 40 | `40_fisher_hawkes` | Combined Fisher + Hawkes |
| 41 | `41_origin_agnostic_velocity` | Velocity without source labels |
| 43 | `43_community_structure` | Network community detection |

## Deep Dives

- `../methodology/FINDINGS.md` — Part 2 (Campaign Detection)
- `../methodology/FINDINGS.campaign-detection.md` — Detection method details
- `../methodology/FINDINGS.hawkes-coordination.md` — Hawkes process analysis
- `../methodology/FINDINGS.narrative-velocity.md` — Velocity metric design

## Next Steps

1. **Build labeled dataset** (R-38) — 33+ hostile clusters minimum
2. **Combine Fisher + Hawkes** (R-40) — test if BR as 3rd feature recovers F1
3. **Extend FIMI regex** to ET/LV/LT languages
4. **Origin-agnostic detection** — methods that work without knowing the source category
