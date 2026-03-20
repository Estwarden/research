# EstWarden Research

Mathematical methodology, optimization tools, and analysis notebooks for the [EstWarden](https://estwarden.eu) Composite Threat Index.

## Contents

### [Methodology](methodology/)
- **[Composite Threat Index](methodology/composite-threat-index.md)** — scoring formula, source weights, threat levels, anomaly detection, narrative taxonomy, campaign detection, milbase fusion

### [Notebooks](notebooks/)
Jupyter notebooks for analyzing the [Baltic Security Dataset](https://github.com/Estwarden/dataset):

| Notebook | What |
|----------|------|
| [dataset_explorer](notebooks/dataset_explorer.ipynb) | Load and explore 27K signals across 20 source types |
| [cti_backtest](notebooks/cti_backtest.ipynb) | Threat history visualization and score analysis |
| [narrative_analysis](notebooks/narrative_analysis.ipynb) | N1-N5 narrative classification patterns |
| [campaign_detection](notebooks/campaign_detection.ipynb) | Influence campaign detection via signal anomalies |
| [source_correlation](notebooks/source_correlation.ipynb) | CTI weight validation and source analysis |

### [Autoresearch](autoresearch/)
Automated CTI optimization inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch):

- **Phase 1** (`optimize.py`): NumPy brute-force — 85K parameter combos in seconds, no LLM
- **Phase 2** (`program.md` + `run.sh`): LLM agent proposes structural scoring improvements

Current best: **eval_score 0.8708** (accuracy 87.5%, lead time 83%)

## Quick Start

```bash
# Clone this repo + dataset
git clone https://github.com/Estwarden/research.git
git clone https://github.com/Estwarden/dataset.git data

# Run notebooks
pip install jupyter matplotlib
cd research/notebooks
jupyter notebook

# Run autoresearch optimizer
cd research/autoresearch
pip install numpy
python3 optimize.py
```

## Related

- **[Dataset](https://github.com/Estwarden/dataset)** — 27K+ signals from 20 OSINT sources
- **[Collectors](https://github.com/Estwarden/collectors)** — Data collection pipelines
- **[Integrations](https://github.com/Estwarden/integrations)** — MCP server, Home Assistant, CLI
- **[estwarden.eu](https://estwarden.eu)** — Live dashboard

## License

MIT
