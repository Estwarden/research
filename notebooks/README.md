# Notebooks

Six research notebooks. Run in order — each builds on the previous.

## Setup

```bash
git clone https://github.com/Estwarden/dataset.git data
cd research
pip install -r requirements.txt
jupyter notebook notebooks/
```

## Sequence

| # | Notebook | Question | Key output |
|---|----------|----------|------------|
| 01 | [Data Profile](01_data_profile.ipynb) | What shape is the data? | `daily_matrix.parquet` — signals aligned with indicator labels |
| 02 | [Lead Indicators](02_lead_indicators.ipynb) | Which sources predict YELLOW first? | Lagged correlations, Random Forest importance, data-driven weights |
| 03 | [Anomaly Thresholds](03_anomaly_thresholds.ipynb) | What z-score = real anomaly? | Per-source ROC curves, Youden's J optimal thresholds, bootstrap stability |
| 04 | [Narrative Velocity](04_narrative_velocity.ipynb) | How fast do narratives spread? | Velocity formula, amplification ratio, campaign prediction score |
| 05 | [Source Independence](05_source_independence.ipynb) | Are any sources redundant? | Correlation matrix, mutual information, PCA, independence-adjusted weights |
| 06 | [CTI Rebuild](06_cti_rebuild.ipynb) | Can we beat hand-tuned weights? | 3 models (hand-tuned / logistic / gradient boosted), time-series CV, deployable formula |

## Dependencies

```
numpy, pandas, scikit-learn, matplotlib, seaborn, scipy
```

See `requirements.txt`.
