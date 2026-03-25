# Data

CSV exports from EstWarden production database (858K+ signals).
Last refreshed: **2026-03-25** (90-day window: 2025-12-25 → 2026-03-25).

## Signal Exports

| File | Rows | Size | Description |
|------|------|------|-------------|
| `signals_90d.csv` | 849,914 | 161M | 90-day signal dump, all source types. **Gitignored** — regenerate with command below. |
| `signals_50d.csv` | 44,908 | 18M | Old 50-day export (stale, kept for backward compat) |

### signals_90d.csv breakdown by source_type

| source_type | count | notes |
|-------------|-------|-------|
| ais | 782,288 | Marine traffic — dominates volume |
| rss | 34,760 | News feeds (RU state, Baltic, independent) |
| adsb | 13,976 | Aircraft tracking |
| radiation | 5,262 | Radiation monitoring |
| telegram_channel | 4,002 | Telegram channels (w/ metadata: channel, views, category) |
| balloon | 2,128 | Balloon sighting reports |
| firms | 1,679 | NASA FIRMS fire/thermal alerts |
| rss_security | 1,161 | Security-focused RSS feeds |
| telegram | 1,049 | Telegram social (non-channel) |
| gdelt | 1,025 | GDELT event data |
| milwatch | 956 | Military tracking |
| energy | 422 | Energy infrastructure monitoring |
| defense_rss | 233 | Defense publication feeds |
| gpsjam | 171 | GPS jamming/spoofing events |
| osint_perplexity | 141 | AI-generated OSINT research |
| business | 135 | Business/economic signals |
| youtube | 113 | YouTube video tracking |
| deepstate | 109 | DeepState frontline data |
| sentinel | 89 | Satellite imagery analysis |
| satellite_analysis | 48 | Satellite analysis results |
| space_weather | 44 | Space weather events |
| osint_milbase | 28 | Military base monitoring |
| youtube_transcript | 22 | YouTube transcript analysis |
| notam | 17 | NOTAMs (airspace notices) |
| ru_legislation | 15 | Russian legislation tracking |
| embassy | 11 | Embassy/diplomatic signals |
| stats | 11 | Statistical data sources |
| mastodon | 9 | Mastodon social signals |
| conflict | 4 | Conflict event data |
| breaking | 4 | Breaking news alerts |
| seismic | 1 | Seismic monitoring |
| railway | 1 | Railway tracking |

Columns: `source_type, title, content, url, published_at, region, feed_handle, channel, category`

- `feed_handle`: RSS feed identifier (e.g. `err_en`, `tass_ru`). Derived from `source_id`.
- `channel`: Telegram channel handle (e.g. `rybar`, `nexta_live`). From signal metadata.
- `category`: Source classification (e.g. `ru_state`, `trusted`, `baltic_media`). From metadata or source_category.

## Auxiliary Data

| File | Rows | Description |
|------|------|-------------|
| `threat_index_history.csv` | 134 | CTI scores per region per day (all time). Cols: date, region, score, level, trend, components, computed_at |
| `campaigns_full.csv` | 37 | All campaigns with detection metadata. Cols: id, name, detected_at, start_time, end_time, confidence, severity, summary, trigger_event, detection_method, event_fact, state_framing, trusted_framing, framing_delta, status, target_regions, narrative_id, cluster_id, review_status, confidence_raw |
| `fabrication_alerts.csv` | 50 | Fabrication claim pairs. Cols: id, cluster_id, root_signal_id, down_signal_id, root_source, root_category, down_source, down_category, root_title, down_title, fabrication_score, added_claims, certainty_escalation, emotional_amplification, summary, down_views, detected_at |
| `narrative_origins.csv` | 1,343 | State-origin narrative tracking. Cols: id, cluster_id, first_signal_id, first_source, first_category, first_title, first_published, signal_count, category_count, categories, is_state_origin, created_at |
| `signal_daily_counts.csv` | 499 | Daily signal counts per source_type (90-day window). Cols: date, source_type, signal_count |
| `signal_hourly_counts.csv` | 2,154 | Hourly signal counts per source_type (14-day window). Cols: hour, source_type, signal_count |
| `cluster_members.csv` | 7,587 | Signal→cluster mappings (90-day window). Cols: cluster_id, signal_id, similarity, source_type, title, published_at, region, source_category, feed_handle, channel |
| `clusters.csv` | 2,278 | Cluster metadata (all). Cols: id, title, summary, region, first_seen, last_seen, signal_count, source_count, category_breakdown, is_active, created_at, updated_at, narrative_tag |
| `all_campaigns.csv` | 30 | Legacy campaign export (kept for backward compat) |
| `campaigns.csv` | 26 | Legacy active campaigns (kept for backward compat) |
| `framing_campaigns_signals.csv` | ~3K | Pre-joined framing+campaigns+signals (from earlier research) |

## Regenerating from Production

Data is exported from the production Postgres container via SSH.
See internal infrastructure docs for connection details — not stored in this repo.

```bash
# Pattern: ssh to prod host, docker exec into postgres, COPY TO STDOUT
# Tables: signals, threat_index_cache, campaigns, fabrication_alerts,
#         narrative_origins, cluster_signals, event_clusters

# Main signal dump (90 days, ~160MB, ~3 min)
# SELECT source_type, title, content, url, published_at, region, feed_handle, channel, category
# FROM signals WHERE published_at >= now()-interval '90 days'

# See .ralph/prompt.md for exact queries (gitignored, not public)
```

## Notes
- **Production DB is READ-ONLY** — never INSERT/UPDATE/DELETE
- `signals_90d.csv` is gitignored due to size (161MB). Regenerate locally using the command above.
- AIS signals dominate (92% of total). For non-AIS analysis, filter by source_type.
- 12+ collector types went dead Mar 15-20 (see notebook 09). Data after that date has gaps.
