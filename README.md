# EstWarden Research

Research notebooks and methodology docs for the [EstWarden](https://estwarden.eu) Baltic Security Monitor.

> **New here?** Open [`vault/`](vault/) in [Obsidian](https://obsidian.md) for a readable, navigable overview of all research tracks, experiments, data, and gaps. Start at [`vault/Home.md`](vault/Home.md).

## Overview

43 research notebooks covering four critical areas:
- **CTI formula diagnostics** (nb14–19): Identified permanent-YELLOW bug — FIMI noise, dead collectors, evidence-free campaigns
- **Satellite analysis** (nb20–23): Designed Sentinel-2 baselines for military site monitoring (GEE-dependent)
- **Campaign detection** (nb24–31): Hawkes coordination, narrative velocity, FIMI regex, Fisher revalidation
- **Data quality** (nb32–34): Collector health monitoring, AIS baselines, embedding quality

**⚠️ Read [methodology/VALIDITY.md](methodology/VALIDITY.md) before deploying any findings.**
The diagnostic results (what's broken) are solid. The prescriptive results (new weights,
thresholds) need further validation. See [methodology/FINDINGS.md](methodology/FINDINGS.md)
for the comprehensive research summary.

**Planning:** [RESEARCH-SPECS.md](RESEARCH-SPECS.md) for the status of all research tracks.
[ROADMAP.md](ROADMAP.md) for the phased plan of new research (nb35+).

## Notebooks

All notebooks are standalone `.py` files. Run from the `notebooks/` directory:

```bash
cd notebooks && python3 01_regional_cti_calibration.py
```

### Foundation (nb01–13)

| # | Notebook | What it does | Key finding |
|---|----------|-------------|-------------|
| 01 | [Regional CTI Calibration](notebooks/01_regional_cti_calibration.py) | Per-region threat thresholds | Uniform YELLOW=15.2 causes permanent alerts in Finland/Poland |
| 02 | [Campaign Labeling](notebooks/02_campaign_labeling.py) | Interactive campaign review tool | — |
| 03 | [Claim Drift Detection](notebooks/03_claim_drift_detection.py) | Detects fabricated claims in amplification | Fabrication adds specificity not in source |
| 04 | [Cascade Topology](notebooks/04_cascade_topology_classifier.py) | Graph features for manipulation detection | — |
| 05 | [Coordination Detection](notebooks/05_coordination_detection.py) | Burstiness analysis of state media | Burstiness NOT validated (p>0.05) at current N |
| 06 | [CTI Decomposition](notebooks/06_cti_decomposition.py) | Decompose CTI into components | FIMI alone exceeds YELLOW threshold |
| 07 | [CTI False Positive Audit](notebooks/07_cti_false_positive_audit.py) | Audit false positives in CTI | Laundering catches NHL, Soyuz, irrelevant events |
| 08 | [Threshold Recalibration](notebooks/08_threshold_recalibration.py) | First threshold recalibration | Structural FIMI problem diagnosed |
| 09 | [System Health Audit](notebooks/09_system_health_audit.py) | Collector health check | 12+ dead collectors since Mar 15–20 |
| 10 | [Baseline Stability](notebooks/10_baseline_stability.py) | Per-source CV analysis | ADS-B CV=134%, AIS CV=109%, RSS CV=206% |
| 11 | [Signal Value Analysis](notebooks/11_signal_value_analysis.py) | Information content per source | Per-source baseline method recommendations |
| 12 | [Honest CTI Assessment](notebooks/12_honest_cti_assessment.py) | End-to-end CTI critique | FIMI is strongest component, most sources broken |
| 13 | [Campaign Verification](notebooks/13_campaign_verification.py) | Verify campaign detections | 30 experiments documented in FINDINGS |

### CTI Formula Fixes (nb14–19)

| # | Notebook | What it does | Key finding |
|---|----------|-------------|-------------|
| 14 | [FIMI Floor Decomposition](notebooks/14_fimi_floor_decomposition.py) | Decompose FIMI sub-components per region | Campaigns (43%) + laundering (19%) drive permanent YELLOW |
| 15 | [Laundering Audit](notebooks/15_laundering_audit.py) | Classify laundering events as real vs noise | 73% noise; relevance filter + count≥3 reduces score 80% |
| 16 | [Campaign Scoring Audit](notebooks/16_campaign_scoring_audit.py) | Tier campaigns by evidence quality | 70% evidence-free; T3 exclusion removes 73% phantom severity |
| 17 | [Robust Baselines](notebooks/17_robust_baselines.py) | Per-source baseline methods | Robust z (median+MAD) superior; binary for high-CV sources |
| 18 | [Weight Recalibration](notebooks/18_weight_recalibration.py) | Recalibrate CTI weights | Dead sources→0; signal weight 72→24; DEGRADED mode proposed |
| 19 | [Threshold Final](notebooks/19_threshold_final.py) | Final thresholds on corrected algorithm | Y=7.9, O=55.8, R=88.7; GREEN now achievable |

### Satellite Analysis (nb20–23)

| # | Notebook | What it does | Key finding |
|---|----------|-------------|-------------|
| 20 | [Sentinel-2 Seasonal Baselines](notebooks/20_sentinel2_seasonal_baselines.py) | 3-year NDVI/BSI weekly profiles | Deseasonalized z-scores eliminate snowmelt false positives |
| 21 | [IForest Satellite Baselines](notebooks/21_iforest_satellite_baselines.py) | Per-site Isolation Forest anomaly models | Ships at Kronstadt (94% bright NIR), equipment at Pskov SW |
| 22 | [CCDC Breakpoints](notebooks/22_ccdc_breakpoints.py) | Harmonic time series breakpoint detection | 6 breakpoints, 1 ISW match (Luga, −2 days before deployment) |
| 23 | [S2 Temporal Change](notebooks/23_s2_temporal_change.py) | Automated Feb→Mar change detection | YoY comparison is correct baseline, not 30-day rolling |

### Media & Campaign Detection (nb24–31)

| # | Notebook | What it does | Key finding |
|---|----------|-------------|-------------|
| 24 | [Hawkes Coordination](notebooks/24_hawkes_coordination.py) | Hawkes process self-excitation analysis | State-heavy clusters: BR=0.53 vs clean: 0.22 (p=0.04) |
| 25 | [Fisher Revalidation](notebooks/25_fisher_revalidation.py) | Bootstrap revalidation of Fisher F1=0.92 | F1=0.92 holds; LOO=77%; power analysis: need N≥14 |
| 26 | [Cluster Quality](notebooks/26_cluster_quality.py) | Fix mega-cluster problem | Two-pass clustering: 0.75 initial, 0.82 re-validate >10 |
| 27 | [Narrative Velocity](notebooks/27_narrative_velocity.py) | Detect weaponization over weeks | F1=1.00 on 8 narratives; velocity>0.15 + SR>0.30 |
| 28 | [IBI Prompt Test](notebooks/28_ibi_prompt_test.py) | Intent-Based Inoculation prompt test | Compared IBI vs current framing prompt on labeled cases |
| 29 | [FIMI Regex](notebooks/29_fimi_regex.py) | Structural FIMI detection without LLM | Hedging + amplification regex patterns for Go implementation |
| 30 | [Co-Coverage Network](notebooks/30_cocoverage_network.py) | Outlet coordination network analysis | State Jaccard=0.26 vs trusted=0.16 (63% premium) |
| 31 | [Fabrication Stability](notebooks/31_fabrication_stability.py) | Fabrication detection consistency test | Stability across repeated LLM runs assessed |

### Data Quality & Infrastructure (nb32–34)

| # | Notebook | What it does | Key finding |
|---|----------|-------------|-------------|
| 32 | [Collector Health](notebooks/32_collector_health.py) | Data freshness dashboard | 76% of days DEGRADED; 4 dead collectors identified |
| 33 | [AIS Deep Dive](notebooks/33_ais_deep_dive.py) | Separate downtime from naval anomalies | High CV is collector breakage; stable when working (~62K/day) |
| 34 | [Embedding Quality](notebooks/34_embedding_quality.py) | Cross-lingual embedding validation | EN>RU>LT (3–5% gap); ET/LV data sparse |

### Roadmap Research (nb35–43)

| # | Notebook | What it does | Key finding |
|---|----------|-------------|-------------|
| 35 | [Moderate Weights](notebooks/35_moderate_weights.py) | Middle-path weight recalibration (~45 vs 72/24) | Tier-based: reliable sources keep weight, dead/noisy zeroed |
| 36 | [PLMSE Cascade](notebooks/36_plmse_cascade.py) | Power-law fit metric per cluster (no ML) | Hostile PLMSE < clean (consistent with "Signals of Propaganda") |
| 37 | [Fabrication Gate](notebooks/37_fabrication_gate.py) | Same-event + relevance filter for fabrication alerts | 79% reduction in fabrication CTI noise; 75% of alerts are non-Baltic |
| 38 | [Labeled Dataset](notebooks/38_labeled_dataset.py) | Unified labeled cluster dataset for downstream research | 6 hostile, 24 clean; need 33+ hostile for Fisher p<0.01 |
| 39 | [AIS Tiers](notebooks/39_ais_tiers.py) | Split AIS into defense-relevant vs raw volume | CV=117%; 5 regime changes; Tier 1 weight=4, Tier 2 conditional |
| 40 | [Fisher+Hawkes](notebooks/40_fisher_hawkes.py) | 3-feature Fisher with Hawkes branching ratio | LOO F1=0.667, bootstrap CI [0.364, 1.000]; needs more hostile labels |
| 41 | [Origin-Agnostic Velocity](notebooks/41_origin_agnostic_velocity.py) | Remove RU-origin gate from velocity detection | Hostile amplification_ratio=0.60 vs clean=0.34; catches Bild-map type |
| 43 | [Community Structure](notebooks/43_community_structure.py) | Propagation graph features per cluster | Hostile denser (consistent with TIDE-MARK); LOO 58% (need more data) |

## Autoresearch

Automated CTI weight optimizer ([Karpathy-style](https://github.com/karpathy/autoresearch)):

```bash
cd autoresearch
pip install numpy
python3 optimize.py  # Phase 1: 85K trials, 3-fold CV → eval_score 0.885
```

**v1 (original algorithm):** `YELLOW=15.2, ORANGE=59.7, RED=92.8, momentum=0.034, trend=0.927`

**v2 (corrected algorithm, via nb19):** `YELLOW=7.9, ORANGE=55.8, RED=88.7, momentum=0.671, trend=0.110`
Results in `output/optimization_results_v2.json`.

## Key Findings Summary

1. **CTI permanent-YELLOW fixed**: FIMI scoring inflation from noisy laundering (73% FP) and
   evidence-free campaigns (70%) resolved. GREEN is now achievable under corrected algorithm.

2. **Fisher pre-screen validated**: `score = 0.670·state_ratio + 0.742·fimi_score` achieves
   F1=0.92 without LLM. Tiered detection reduces LLM calls 77% while maintaining F1=1.00.

3. **Narrative velocity detects strategic campaigns**: Week-over-week state_ratio increase
   catches weaponization (F1=1.00 on 8 labeled narratives). Complements event-level detectors.

4. **Satellite baselines operational**: 3-year seasonal profiles + Isolation Forest + CCDC
   provide deseasonalized anomaly detection for military site monitoring via free Sentinel-2.

5. **Collector health is the primary challenge**: Only 24% of days have adequate sensor coverage.
   DEGRADED flag is essential for honest threat assessment.

## Methodology

- [**Comprehensive Findings**](methodology/FINDINGS.md) — definitive research summary
- [Composite Threat Index](methodology/composite-threat-index.md) — formula, weights, thresholds
- [FIMI Floor Decomposition](methodology/FINDINGS.cti-fimi-floor.md) — permanent-YELLOW bug
- [Robust Baselines](methodology/FINDINGS.robust-baselines.md) — per-source z-score methods
- [Threshold Recalibration](methodology/FINDINGS.threshold-recalibration.md) — final thresholds
- [Regional Calibration](methodology/FINDINGS.regional-calibration.md) — per-region analysis
- [Campaign Detection](methodology/FINDINGS.campaign-detection.md) — 30 experiments
- [Hawkes Coordination](methodology/FINDINGS.hawkes-coordination.md) — temporal self-excitation
- [Narrative Velocity](methodology/FINDINGS.narrative-velocity.md) — weaponization detection
- [Satellite Imagery](methodology/FINDINGS.satellite-imagery.md) — Sentinel-2 spectral analysis
- [Satellite CCDC](methodology/FINDINGS.satellite-ccdc.md) — breakpoint detection
- [Milbase Monitoring](methodology/FINDINGS.milbase-monitoring.md) — multi-source fusion audit
- [Production Ready](methodology/PRODUCTION-READY.md) — deployable changes
- [Literature Review](methodology/literature-review.md) — academic papers

## Analysis Docs

- [Fabrication Detection Design](fabrication-detection-design.md) — origin-agnostic mutation detection
- [Bild Map Case Study](bild-map-watchlist-gap.md) — gap analysis from a real missed campaign
- [Evolving Disinfo Patterns](evolving-disinfo-patterns.md) — 2024–2026 pattern shifts
- [Reading List](reading-list-disinfo-science.md) — 14 papers, 5 implementation priorities

## Data

Notebooks use CSV exports in `data/`. See [data/README.md](data/README.md) for full inventory.

| File | Rows | Description |
|------|:----:|-------------|
| `signals_90d.csv` | 849,914 | 90-day signal dump (gitignored, 161MB) |
| `signals_50d.csv` | 44,908 | Old 50-day export (backward compat) |
| `threat_index_history.csv` | 134 | CTI scores per region per day |
| `campaigns_full.csv` | 37 | Campaigns with detection metadata |
| `fabrication_alerts.csv` | 50 | Fabrication claim pairs |
| `narrative_origins.csv` | 1,343 | State-origin narrative tracking |
| `cluster_members.csv` | 7,587 | Signal→cluster mappings (90d) |
| `clusters.csv` | 2,278 | Cluster metadata |
| `signal_daily_counts.csv` | 499 | Daily counts per source_type |
| `signal_hourly_counts.csv` | 2,154 | Hourly counts per source_type |
| `laundering_classified.csv` | — | Classified laundering events (nb15) |

## Archived

`satellite-analysis/` contains earlier satellite imagery experiments (vehicle detection,
spectral analysis, SAR). Superseded by notebooks 20–23 which use systematic Sentinel-2
baselines via GEE.

## Related

| Repo | What |
|------|------|
| [Collectors](https://github.com/Estwarden/collectors) | Dagu DAGs + collector scripts |
| [Dataset](https://github.com/Estwarden/dataset) | Public JSONL signal exports |
