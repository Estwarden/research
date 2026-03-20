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
