---
status: evergreen
tags: [reference, glossary]
---

# Glossary

Key terms used across the research. Organized by domain.

## Threat Index

| Term | Definition |
|------|-----------|
| **CTI** | Composite Threat Index — single numeric score per region per day combining all signal sources |
| **YELLOW / ORANGE / RED** | Threat levels. Thresholds: YELLOW=15.2, ORANGE=59.7, RED=92.8 (production values) |
| **DEGRADED** | Flag indicating insufficient sensor coverage for reliable scoring |
| **Signal weight** | How much each source type contributes to CTI. Currently totals 72 (signal) + 38 (FIMI) = 110 |
| **Robust z-score** | `(value - median) / MAD` — outlier-resistant alternative to standard z-scores |

## Disinformation & FIMI

| Term | Definition |
|------|-----------|
| **FIMI** | Foreign Information Manipulation and Interference — EU framework for hostile information operations |
| **Laundering** | Amplification of disinformation through seemingly independent intermediaries |
| **State ratio** | Proportion of signals in a cluster originating from state-controlled media |
| **FIMI score** | Automated assessment of manipulation indicators in a narrative cluster |
| **IBI** | Intent-Based Intelligence — prompting approach that assesses intent (rejected in nb28; factual approach retained) |

## Campaign Detection

| Term | Definition |
|------|-----------|
| **Fisher discriminant** | Linear classifier separating hostile vs benign clusters using state_ratio + fimi_score |
| **Hawkes process** | Self-exciting point process — models how one event triggers subsequent events |
| **Branching ratio (BR)** | Hawkes parameter measuring cascade intensity. BR=0.53 (state) vs 0.22 (clean) |
| **Narrative velocity** | Week-over-week change in state media ratio within a narrative |
| **Co-coverage** | Jaccard similarity between source pairs covering the same stories |
| **Mega-cluster** | Pathologically large cluster from single-pass cosine similarity. Fixed by two-pass clustering. |

## Satellite & GEOINT

| Term | Definition |
|------|-----------|
| **NDVI** | Normalized Difference Vegetation Index — measures vegetation health from satellite imagery |
| **BSI** | Bare Soil Index — measures exposed ground from satellite imagery |
| **CCDC** | Continuous Change Detection and Classification — detects abrupt spectral shifts in time series |
| **Isolation Forest** | Unsupervised anomaly detection on multivariate spectral features |
| **GEE** | Google Earth Engine — cloud platform for satellite imagery analysis |
| **FIRMS** | Fire Information for Resource Management System (NASA) — thermal/fire alerts |
| **Sentinel-2** | ESA free optical satellite (10m resolution, 5-day revisit) |
| **Sentinel-1** | ESA free SAR satellite (cloud-penetrating radar imagery) |
| **ISW** | Institute for the Study of War — source for Russian military activity ground truth |

## Data Sources

| Term | Definition |
|------|-----------|
| **AIS** | Automatic Identification System — ship tracking. 92% of signal volume. |
| **ADS-B** | Automatic Dependent Surveillance-Broadcast — aircraft tracking |
| **GDELT** | Global Database of Events, Language, and Tone — event data from news |
| **ACLED** | Armed Conflict Location & Event Data — conflict event database (currently dead) |
| **IODA** | Internet Outage Detection and Analysis (currently dead) |
| **GPS jamming** | GPS interference events. Strongest signal source, but sparse (15 of 88 days). |

## Statistical

| Term | Definition |
|------|-----------|
| **LOO** | Leave-One-Out cross-validation |
| **MAD** | Median Absolute Deviation — robust spread measure |
| **CV** | Coefficient of Variation — std/mean, measures relative variability |
| **Dempster-Shafer** | Evidence theory for combining uncertain multi-sensor inputs (planned, not implemented) |
