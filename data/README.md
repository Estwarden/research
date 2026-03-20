# Dataset

This directory contains the EstWarden signals dataset (gitignored).

## Download

```bash
# From the live API (latest 90 days, ~15MB compressed)
python3 data/download.py

# Or manually:
curl -s -H "User-Agent: EstWarden" https://estwarden.eu/api/threat-index/history > data/daily_reports.jsonl
```

## Files

| File | Records | What |
|------|---------|------|
| `signals.jsonl` | ~335K | All collected signals (RSS, ADS-B, AIS, FIRMS, etc.) |
| `narrative_tags.jsonl` | ~1.1K | LLM narrative classifications (N1-N5) |
| `daily_reports.jsonl` | ~41 | Daily threat reports with CTI scores |
| `campaigns.jsonl` | ~31 | Detected influence campaigns |
| `indicators.jsonl` | ~500 | Per-report threat indicators |

## Schema

Each signal:
```json
{"id": 123, "source_type": "rss", "title": "...", "published_at": "2026-...", "severity": null, "latitude": null, "longitude": null, "metadata": {...}}
```

## Privacy

- No user data, no credentials, no internal IPs
- Signal content is truncated to 200 chars (titles only)
- Metadata contains source handles and categories (all public)
