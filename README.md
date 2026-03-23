# EstWarden Research

Research notebooks and methodology docs for the [EstWarden](https://estwarden.eu) Baltic Security Monitor.

## Notebooks

5 validated notebooks that actually run and produce real results.

| # | Notebook | What it does | Data needed |
|---|----------|-------------|-------------|
| 01 | [Regional CTI Calibration](notebooks/01_regional_cti_calibration.py) | Per-region threat thresholds (Baltic/Finland/Poland) | `data/signals_50d.csv` |
| 02 | [Campaign Labeling](notebooks/02_campaign_labeling.py) | Interactive tool for analyst campaign review | `data/all_campaigns.csv` |
| 03 | [Claim Drift Detection](notebooks/03_claim_drift_detection.py) | Detects fabricated claims added during amplification | Embedded test data |
| 04 | [Cascade Topology](notebooks/04_cascade_topology_classifier.py) | Graph features for manipulated vs organic cascades | Embedded test data |
| 05 | [Coordination Detection](notebooks/05_coordination_detection.py) | Burstiness analysis of state media coordination | `data/cluster_members.csv` |

Run from the `notebooks/` directory:

```bash
cd notebooks && python3 01_regional_cti_calibration.py
```

### Key findings

- **Regional thresholds matter**: uniform YELLOW=15.2 causes permanent alerts in Finland/Poland. Per-region calibration needed.
- **Burstiness is NOT validated** (p>0.05) as a standalone coordination signal at current sample size. Needs more data.
- **Claim drift detection works**: fabrication adds specificity (dates, laws, certainty) that doesn't exist in the source material.
- **Russian state media presence ≠ hostile operation**: organic news also has high state media overlap.

## Autoresearch

Automated CTI weight optimizer ([Karpathy-style](https://github.com/karpathy/autoresearch)):

```bash
cd autoresearch
pip install numpy
python3 optimize.py  # 85K trials, 3-fold CV → eval_score 0.885
```

Best parameters: `YELLOW=15.2, ORANGE=59.7, RED=92.8, momentum=0.034, trend=0.927`

## Methodology

- [Composite Threat Index](methodology/composite-threat-index.md) — formula, weights, thresholds
- [Campaign Detection](methodology/FINDINGS.campaign-detection.md) — 30 experiments, honest results
- [Regional Calibration](methodology/FINDINGS.regional-calibration.md) — per-region threshold analysis
- [Satellite Imagery](methodology/FINDINGS.satellite-imagery.md) — Sentinel-2 military monitoring
- [Milbase Monitoring](methodology/FINDINGS.milbase-monitoring.md) — multi-source fusion audit
- [Production Ready](methodology/PRODUCTION-READY.md) — what's actually deployable
- [Literature Review](methodology/literature-review.md) — academic papers with implementable methods

## Analysis docs

- [Fabrication Detection Design](fabrication-detection-design.md) — origin-agnostic mutation detection
- [Bild Map Case Study](bild-map-watchlist-gap.md) — gap analysis from a real missed campaign
- [Evolving Disinfo Patterns](evolving-disinfo-patterns.md) — 2024-2026 pattern shifts
- [Reading List](reading-list-disinfo-science.md) — 14 papers, 5 implementation priorities

## Data

Notebooks use CSV exports in `data/`. See [data/README.md](data/README.md).

| File | Rows | Used by |
|------|------|---------|
| `signals_50d.csv` | 44,908 | nb01 |
| `all_campaigns.csv` | 30 | nb02 |
| `cluster_members.csv` | 3,362 | nb05 |
| `campaigns.csv` | 26 | reference |
| `clusters.csv` | 180 | reference |

## Related

| Repo | What |
|------|------|
| [Collectors](https://github.com/Estwarden/collectors) | Dagu DAGs + collector scripts |
| [Dataset](https://github.com/Estwarden/dataset) | Public JSONL signal exports |
