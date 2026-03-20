# Notebooks

Jupyter notebooks for CTI analysis and model development.

## Planned

- `cti-backtest.ipynb` — Backtest threat index against known events (2022-2026)
- `weight-optimization.ipynb` — Optimize source weights using historical data
- `narrative-accuracy.ipynb` — Measure LLM classifier precision/recall
- `campaign-detection-tuning.ipynb` — Tune z-score thresholds for campaign detection
- `baseline-stability.ipynb` — Analyze 7-day vs 14-day vs 30-day baseline windows
- `source-correlation.ipynb` — Cross-correlation matrix between all signal sources

## Setup

```bash
pip install jupyter pandas matplotlib seaborn requests
jupyter notebook
```

All notebooks use the public API: `https://estwarden.eu/api/`
