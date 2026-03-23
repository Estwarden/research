# Data

CSV exports from EstWarden production database.

| File | Rows | Description |
|------|------|-------------|
| `signals_50d.csv` | 44,908 | 50 days of signals (all source types) |
| `all_campaigns.csv` | 30 | Full campaign archive |
| `campaigns.csv` | 26 | Active campaigns |
| `cluster_members.csv` | 3,362 | Signal-to-cluster mappings |
| `clusters.csv` | 180 | Narrative event clusters |

To refresh from production:

```bash
ssh root@server "docker exec estwarden-postgres psql -U estwarden -d estwarden \
  -c \"COPY (SELECT source_type,title,content,url,published_at,region,feed_handle,channel,category FROM signals WHERE published_at >= now()-interval '50 days') TO STDOUT CSV HEADER\"" \
  > signals_50d.csv
```
