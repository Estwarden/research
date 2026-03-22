# EstWarden Research

Research notebooks and optimization tools for the [EstWarden](https://estwarden.eu) Baltic Security Monitor. All analysis runs against the public [dataset](https://github.com/Estwarden/dataset).

## Quick start

```bash
git clone https://github.com/Estwarden/research.git
git clone https://github.com/Estwarden/dataset.git data
cd research
pip install -r requirements.txt
jupyter notebook notebooks/
```

## Notebooks

Run in order — notebook 01 produces `daily_matrix.parquet` that all others load.

| # | Notebook | Question | Method |
|---|----------|----------|--------|
| 01 | [Data Profile](notebooks/01_data_profile.ipynb) | What shape is the data? | Align 20K signals with 497 indicator labels, build daily matrix |
| 02 | [Lead Indicators](notebooks/02_lead_indicators.ipynb) | Which sources spike before YELLOW? | Point-biserial correlation at lag 0-3, Random Forest importance |
| 03 | [Anomaly Thresholds](notebooks/03_anomaly_thresholds.ipynb) | What z-score = real anomaly? | Per-source ROC, Youden's J, bootstrap stability |
| 04 | [Narrative Velocity](notebooks/04_narrative_velocity.ipynb) | How fast do narratives spread? | Velocity, amplification ratio, campaign predictor |
| 05 | [Source Independence](notebooks/05_source_independence.ipynb) | Are sources redundant? | Correlation matrix, mutual information, PCA decomposition |
| 06 | [CTI Rebuild](notebooks/06_cti_rebuild.ipynb) | Can we beat hand-tuned weights? | Logistic regression vs gradient boosting, time-series CV |
| 07 | [Campaign Detection](notebooks/07_campaign_detection.py) | How to detect real info ops? | Event clustering, framing analysis, Fisher pre-screen |
| 08 | [Satellite Imagery](notebooks/08_satellite_imagery_analysis.py) | What can we see at 10m? | Spectral indices, GLCM, edge density, Isolation Forest |
| 09 | [Server-Side Analysis](notebooks/09_server_side_analysis.py) | What can GEE compute? | Linear trend, temporal variability, YoY baselines |

## Satellite Imagery Research (NEW — Experiments 08–15)

Validated techniques for monitoring 35 Russian/Belarusian military installations using Sentinel-2 10m imagery via Google Earth Engine.

### Quick Start (satellite experiments)

```bash
pip install opencv-python-headless scikit-image scikit-learn tifffile scipy

# Download sample data from public GCS bucket
for site in Pskov-76th-VDV Kronstadt-naval Kaliningrad-Chkalovsk; do
  curl -O "https://storage.googleapis.com/estwarden-satellite/thumbnails/$site/2026-03-15.jpg"
done

# Run local CV experiments
python3 notebooks/08_satellite_imagery_analysis.py
```

For GEE server-side experiments, you need a [Google Earth Engine account](https://earthengine.google.com/signup/) (free for research).

### Key Findings

| Technique | Works? | Finding |
|-----------|--------|---------|
| BSI + NDBI segmentation | ✅ YES | 91% active pixels at airbase, 15% at naval — quantitative footprint |
| Material band ratios | ✅ YES | Fuel 6.1%, metal 7.6%, concrete 29.2% at naval site |
| Isolation Forest anomalies | ✅ YES | 94% bright-NIR anomalies at naval = de facto ship detector |
| Year-over-year baseline | ✅ YES | Eliminates seasonal false positives (snow melt artifacts) |
| 2048px EE thumbnails | ✅ YES | 4000–9000% more edge info than bicubic upsampling |
| GLCM texture | ❌ NO | All sites identical at 10m — needs <3m resolution |
| FFT spatial regularity | ❌ NO | All military sites are geometric — no contrast |
| 30-day rolling baseline | ❌ NO | Seasonal artifacts dominate (use YoY instead) |

### Trainable Algorithms (need data accumulation)

| Algorithm | Data Needed | Labels? | When Ready |
|-----------|-------------|---------|------------|
| Seasonal NDVI/BSI profiles | 12 months/site | No | Now (EE archive) |
| Per-site Isolation Forest | 20 acquisitions/site | No | ~3 months |
| Random Forest land cover | 50 pixels/class | Yes | ~2h manual work |
| CCDC change detection | 3+ years | No | Now (have 2023-2026) |
| Siamese change network | OSCD dataset | Yes | GPU ~4h training |
| SeCo self-supervised | Unlabeled S2 series | No | GPU ~4h training |

Full details: [FINDINGS.satellite-imagery.md](methodology/FINDINGS.satellite-imagery.md)

## Key formulas

From notebook 03 — **per-source anomaly score**:
$$\text{AnomalyScore}(t) = \sum_i \text{AUC}_i \cdot \max(0,\; z_i(t) - \tau_i^*)$$

From notebook 04 — **campaign prediction**:
$$CS(t) = \sum_k \max(0,\; v_k(t)) \cdot s_k(t)$$

From notebook 06 — **logistic CTI** (deployable):
$$P(\text{YELLOW}) = \sigma\!\left(w_0 + \sum_i w_i \cdot z_i + \sum_i w'_i \cdot v_i\right)$$

## Autoresearch

Automated CTI optimization ([Karpathy pattern](https://github.com/karpathy/autoresearch)):

```bash
cd autoresearch
python3 optimize.py      # Phase 1: 85K trials, 3-fold CV
./run.sh                 # Phase 2: LLM structural improvements
```

## Methodology

- [Composite Threat Index](methodology/composite-threat-index.md) — formula, weights, thresholds
- [Campaign Detection](methodology/FINDINGS.campaign-detection.md) — 30 experiments on disinformation detection
- [Satellite Imagery](methodology/FINDINGS.satellite-imagery.md) — 15 experiments on Sentinel-2 military monitoring
- [Milbase Monitoring](methodology/FINDINGS.milbase-monitoring.md) — multi-source military base fusion audit
- [Findings](methodology/FINDINGS.md) — what changed in production

## Related

| Repo | What |
|------|------|
| [Dataset](https://github.com/Estwarden/dataset) | 27K signals, 20 sources, indicators, campaigns |
| [Collectors](https://github.com/Estwarden/collectors) | Data collection pipelines (Dagu DAGs) |
| [Integrations](https://github.com/Estwarden/integrations) | MCP server, Home Assistant, CLI |
| [estwarden.eu](https://estwarden.eu) | Live dashboard |

## License

MIT


