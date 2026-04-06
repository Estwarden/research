---
status: evergreen
tags: [data, catalog, infrastructure]
---

# Data Catalog

All datasets in the research repository. Data lives in `../data/` (CSV exports from production) and `../output/` (computed results).

## Primary Data (`../data/`)

### Signal Exports

| File | Rows | Size | Current | Notes |
|------|------|------|---------|-------|
| `signals_90d.csv` | 849,914 | 161M | Yes | 90-day dump, all sources. **Gitignored** — regenerate from prod DB. |
| `signals_50d.csv` | 44,908 | 18M | No | Old 50-day export. Kept for backward compat. |

Signal data covers 30+ source types. AIS dominates (92% of volume). For non-AIS analysis, filter by `source_type`.

Columns: `source_type, title, content, url, published_at, region, feed_handle, channel, category`

### Threat Index

| File | Rows | Description |
|------|------|-------------|
| `threat_index_history.csv` | 134 | CTI scores per region per day (all time) |

### Campaigns

| File | Rows | Current | Notes |
|------|------|---------|-------|
| `campaigns_full.csv` | 37 | **Yes — use this one** | All campaigns with full detection metadata |
| `all_campaigns.csv` | 30 | No | Legacy export, fewer columns |
| `campaigns.csv` | 26 | No | Legacy active-only export |

### Clusters & Signals

| File | Rows | Description |
|------|------|-------------|
| `clusters.csv` | 2,278 | Cluster metadata (title, summary, signal count, narrative tag) |
| `cluster_members.csv` | 7,587 | Signal-to-cluster mappings with similarity scores |
| `framing_campaigns_signals.csv` | ~3K | Pre-joined framing + campaigns + signals (older research) |

### Detection Outputs

| File | Rows | Description |
|------|------|-------------|
| `fabrication_alerts.csv` | 50 | Fabrication claim pairs (root → downstream) |
| `narrative_origins.csv` | 1,343 | State-origin narrative tracking |

### Time Series

| File | Rows | Description |
|------|------|-------------|
| `signal_daily_counts.csv` | 499 | Daily counts per source_type (90-day window) |
| `signal_hourly_counts.csv` | 2,154 | Hourly counts per source_type (14-day window) |

### Satellite

| File | Description |
|------|-------------|
| `satellite/seasonal_profiles.csv` | 3-year NDVI/BSI weekly profiles per site |
| `satellite/temporal_change_classes.csv` | Change classification per site |
| `satellite/temporal_change_stats.csv` | Change statistics per site |

**Note:** `per_image_spectral.csv` and `.parquet` files are gitignored (large).

## Computed Results (`../output/`)

30+ CSV/JSON result files from notebook runs. Key outputs:

| File Pattern | Source | Content |
|--------------|--------|---------|
| `change_heatmaps/*.png` | nb23 | 14 satellite change maps (Luga + Pskov-76VDV) |
| `optimization_results*.json` | autoresearch | Weight optimization results |
| Various `.csv` | nb14–34 | Per-notebook analysis results |

## Data Freshness

| Dataset | Last Refreshed | Window |
|---------|---------------|--------|
| signals_90d | 2026-03-25 | Dec 25 2025 → Mar 25 2026 |
| threat_index_history | 2026-03-25 | All time |
| campaigns_full | 2026-03-25 | All time |
| clusters / cluster_members | 2026-03-25 | 90-day |

## Regenerating Data

Data is exported from the production Postgres container via SSH. Connection details are in `.ralph/prompt.md` (gitignored, not public).

```bash
# Pattern — do NOT run blindly, see .ralph/ for exact queries
# ssh to prod → docker exec postgres → COPY TO STDOUT
# Tables: signals, threat_index_cache, campaigns, fabrication_alerts,
#         narrative_origins, cluster_signals, event_clusters
```

**Production DB is READ-ONLY** — never INSERT/UPDATE/DELETE.

## Known Issues

1. **Multiple campaign CSVs** — use `campaigns_full.csv` (37 rows), ignore the others
2. **signals_90d is gitignored** — must regenerate locally (161MB)
3. **12+ collectors dead Mar 15–20** — data after that date has gaps
4. **AIS dominates volume** (92%) — filter by source_type for non-AIS analysis
5. **Satellite parquet files** are gitignored — regenerate via nb20–23
