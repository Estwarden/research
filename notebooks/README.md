# Notebooks

Jupyter notebooks for analyzing the [EstWarden Baltic Security Dataset](https://github.com/Estwarden/dataset).

## Setup

```bash
# Clone the dataset
git clone https://github.com/Estwarden/dataset.git ../data

# Install dependencies
pip install jupyter matplotlib pandas

# Run
jupyter notebook
```

## Notebooks

| Notebook | What it does |
|----------|-------------|
| **[dataset_explorer.ipynb](dataset_explorer.ipynb)** | Load all datasets, explore source distribution, temporal coverage, geographic data |
| **[cti_backtest.ipynb](cti_backtest.ipynb)** | Visualize 90-day threat history, level distribution, score volatility |
| **[narrative_analysis.ipynb](narrative_analysis.ipynb)** | Narrative classification breakdown (N1-N5), campaign activity |
| **[campaign_detection.ipynb](campaign_detection.ipynb)** | Signal volume spikes, z-score anomaly detection, cross-source coordination |
| **[source_correlation.ipynb](source_correlation.ipynb)** | Score distribution, CTI weight validation |

## Data

Notebooks expect the dataset at `../data/` (clone [Estwarden/dataset](https://github.com/Estwarden/dataset)).

Alternative: use the public API at `https://estwarden.eu/api/` for live data.
