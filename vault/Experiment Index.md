---
status: evergreen
tags: [index, experiments, notebooks]
---

# Experiment Index

All 43 experiment notebooks mapped by domain. Each is a standalone `.py` file in `../notebooks/`.

```bash
cd notebooks && python3 01_regional_cti_calibration.py
```

Shared config: `../notebooks/cti_constants.py` (regions, colors, paths).

## By Domain

### Foundation (nb01–13)

Early exploration and diagnostics. Established the research questions.

| # | Script | What | Key Finding |
|---|--------|------|-------------|
| 01 | `01_regional_cti_calibration` | Per-region thresholds | Uniform YELLOW causes permanent alerts in FI/PL |
| 02 | `02_campaign_labeling` | Interactive campaign review | Tool, no finding |
| 03 | `03_claim_drift_detection` | Fabrication in amplification | Fabrication adds specificity not in source |
| 04 | `04_cascade_topology_classifier` | Graph features for manipulation | AUC 0.83 in literature, NOT VALIDATED here |
| 05 | `05_coordination_detection` | Burstiness of state media | NOT validated (p>0.05 at current N) |
| 06 | `06_cti_decomposition` | CTI component breakdown | FIMI alone exceeds YELLOW threshold |
| 07 | `07_cti_false_positive_audit` | False positive catalogue | Laundering catches NHL, Soyuz, irrelevant events |
| 08 | `08_threshold_recalibration` | First threshold analysis | Structural FIMI problem diagnosed |
| 09 | `09_system_health_audit` | Collector health check | 12+ dead collectors since Mar 15–20 |
| 10 | `10_baseline_stability` | Per-source CV analysis | ADS-B CV=134%, AIS CV=109%, RSS CV=206% |
| 11 | `11_signal_value_analysis` | Information content per source | Per-source baseline recommendations |
| 12 | `12_honest_cti_assessment` | End-to-end CTI critique | FIMI strongest, most sources broken |
| 13 | `13_campaign_verification` | Campaign detection audit | 30 experiments documented |

### CTI Formula Fixes (nb14–19) → [[CTI Formula]]

The core diagnostic chain. Each notebook builds on the previous.

| # | Script | What | Key Finding |
|---|--------|------|-------------|
| 14 | `14_fimi_floor_decomposition` | FIMI sub-components per region | Campaigns 43% + laundering 19% drive YELLOW |
| 15 | `15_laundering_audit` | Classify laundering as real/noise | 73% noise; filter reduces score 80% |
| 16 | `16_campaign_scoring_audit` | Tier campaigns by evidence | 70% evidence-free → 73% phantom severity |
| 17 | `17_robust_baselines` | Per-source baseline methods | Median+MAD superior; binary for high-CV |
| 18 | `18_weight_recalibration` | Recalibrate CTI weights | 72→24 TOO AGGRESSIVE |
| 19 | `19_threshold_final` | Final thresholds | Y=7.9 — DO NOT DEPLOY |

### Satellite Analysis (nb20–23) → [[Satellite Monitoring]]

| # | Script | What | Key Finding |
|---|--------|------|-------------|
| 20 | `20_sentinel2_seasonal_baselines` | 3-year NDVI/BSI profiles | Year-over-year same-month is correct baseline |
| 21 | `21_iforest_satellite_baselines` | Isolation Forest anomaly | Proxy detector, not direct military detection |
| 22 | `22_ccdc_breakpoints` | CCDC change detection | 6 breakpoints, 1 ISW match (Luga, -2d) |
| 23 | `23_s2_temporal_change` | Year-over-year change maps | 14 heatmaps, snowmelt false positives eliminated |

### Campaign Detection (nb24–31) → [[Campaign Detection]]

| # | Script | What | Key Finding |
|---|--------|------|-------------|
| 24 | `24_hawkes_coordination` | Hawkes branching ratio | BR=0.53 state vs 0.22 clean (p=0.04) |
| 25 | `25_fisher_revalidation` | Fisher discriminant retest | F1=0.615, NOT 0.92 |
| 26 | `26_cluster_quality` | Clustering parameters | Cosine 0.75 + two-pass optimal |
| 27 | `27_narrative_velocity` | Weaponization speed | F1=1.00 on N=8 — meaningless |
| 28 | `28_ibi_prompt_test` | Intent vs factual prompting | Intent over-triggers; keep factual |
| 29 | `29_fimi_regex` | Regex FIMI pre-screen | 80% catch rate without LLM |
| 30 | `30_cocoverage_network` | Source coordination | State Jaccard=0.26 vs trusted=0.16 |
| 31 | `31_fabrication_stability` | Fabrication score validity | Conflates topic drift with fabrication |

### Data Quality (nb32–34) → [[Data Quality]]

| # | Script | What | Key Finding |
|---|--------|------|-------------|
| 32 | `32_collector_health` | Collector monitoring | 76% days DEGRADED |
| 33 | `33_ais_deep_dive` | AIS analysis | 4x throughput swings = collector, not naval |
| 34 | `34_embedding_quality` | Cross-lingual embeddings | EN > RU > LT; ET/LV too sparse |

### Roadmap Research (nb35–43)

Newer experiments from the phased research plan.

| # | Script | What | Status |
|---|--------|------|--------|
| 35 | `35_moderate_weights` | Weight total ~45 path | Phase 1 |
| 36 | `36_plmse_cascade` | PLMSE cascade analysis | Phase 1 |
| 37 | `37_fabrication_gate` | same_event gate for fabrication | Phase 1 |
| 38 | `38_labeled_dataset` | Build hostile label dataset | Phase 1 — CRITICAL |
| 39 | `39_ais_tiers` | AIS source tiering | Phase 1 |
| 40 | `40_fisher_hawkes` | Combined Fisher+Hawkes | Phase 2 |
| 41 | `41_origin_agnostic_velocity` | Velocity without source labels | Phase 2 |
| 43 | `43_community_structure` | Network community detection | Phase 2 |

**Note:** nb42 does not exist (skipped in sequence).

## Planned but Not Yet Created

From `../ROADMAP.md`: notebooks 44–55 are proposed but not yet implemented. See roadmap for descriptions.
