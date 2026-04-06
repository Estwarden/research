---
status: evergreen
tags: [satellite, geoint, sentinel, milbase]
---

# Satellite Monitoring

Detecting military activity changes at Russian bases near the Baltic using free satellite imagery (primarily Sentinel-2). Methods are validated but the **pipeline is broken** — Sentinel-2 collector dead since Mar 14.

## Approaches

### Seasonal Baselines (nb20)

Build 3-year NDVI/BSI weekly profiles per military site. Deseasonalized z-scores detect anomalies against the seasonal norm.

- **Key insight:** Year-over-year same-month comparison is the correct baseline, not 30-day rolling (which triggers on snowmelt)
- **Status:** HIGH confidence. GEE-validated.

### Isolation Forest Anomaly (nb21)

Per-site multivariate anomaly detection on spectral indices.

- **Finding:** Acts as proxy detector — catches surface changes but can't distinguish military vs civilian
- **Status:** MEDIUM. Useful as pre-filter, needs domain interpretation layer.

### CCDC Breakpoint Detection (nb22)

Continuous Change Detection and Classification — finds abrupt spectral shifts in multi-year time series.

- **Finding:** 6 breakpoints detected in 3 years across monitored sites. 1 confirmed match with ISW timeline (Luga base, -2 days before reported activity).
- **Status:** MEDIUM (N=6, 1 confirmed). Promising but small sample.

### Temporal Change Maps (nb23)

Automated year-over-year change heatmaps for military sites.

- **Output:** 14 change maps in `../output/change_heatmaps/` (Luga + Pskov-76VDV, 7 variants each)
- **Status:** HIGH. Correct methodology, eliminates snowmelt false positives.

## Earlier Work (satellite-analysis/)

The `../satellite-analysis/` directory contains earlier Jupyter notebook experiments (now superseded):

| Notebook | What | Result |
|----------|------|--------|
| 01-vehicle-detection.ipynb | YOLO vehicle detection on SkySat/WorldView | **Zero military vehicles** detected at Russian bases. Positive control: detected 10+ aircraft at Tallinn Airport. |
| 02-spectral-analysis.ipynb | WorldView-3 spectral clustering | Spectral signatures identified but no ground truth. |
| 03-sar-analysis.ipynb | Sentinel-1 SAR backscatter | Temporal comparison worked but interpretation ambiguous. |

These are superseded by nb20–23 which use more systematic Sentinel-2 baselines.

## What's Broken

| Problem | Impact |
|---------|--------|
| Sentinel-2 collector dead since Mar 14 | No new imagery ingestion |
| FIRMS is only working satellite source | Fire/thermal only, no optical |
| Dempster-Shafer fusion engine deleted | No multi-sensor combination |
| No SAR integration in new pipeline | Missing cloud-penetrating capability |

## Experiments

| # | Notebook | Method |
|---|----------|--------|
| 20 | `20_sentinel2_seasonal_baselines` | 3-year seasonal profiles |
| 21 | `21_iforest_satellite_baselines` | Isolation Forest anomaly |
| 22 | `22_ccdc_breakpoints` | CCDC breakpoint detection |
| 23 | `23_s2_temporal_change` | Year-over-year change maps |

Plus 3 Jupyter notebooks in `../satellite-analysis/notebooks/`.

## Deep Dives

- `../methodology/FINDINGS.md` — Part 3 (Satellite & Milbase Monitoring)
- `../methodology/FINDINGS.satellite-imagery.md` — Sentinel-2 analysis details
- `../methodology/FINDINGS.satellite-ccdc.md` — CCDC breakpoint methodology
- `../methodology/FINDINGS.milbase-monitoring.md` — Military site monitoring design

## Next Steps

1. **Fix Sentinel-2 collector** (F-01) — prerequisite
2. **Integrate SAR** (Sentinel-1) into the new pipeline — cloud-penetrating backup
3. **Rebuild fusion engine** — combine satellite + FIRMS + AIS for maritime sites
4. **Accumulate detections** for statistical validation (need 10+ confirmed ISW matches)
