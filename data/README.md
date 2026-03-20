# Data

Clone the [EstWarden dataset](https://github.com/Estwarden/dataset) here:

```bash
git clone https://github.com/Estwarden/dataset.git ../data
```

Notebooks expect these files:
- `media_signals.jsonl` — 17K RSS, Telegram, YouTube, GDELT signals
- `military_signals.jsonl` — 2.7K ADS-B, FIRMS, GPS jamming signals
- `economic_signals.jsonl` — 6.5K sanctions, energy, business signals
- `environmental_signals.jsonl` — 765 balloon, space weather signals
- `narrative_tags.jsonl` — 1.1K N1-N5 classifications
- `daily_reports.jsonl` — 41 daily threat reports
- `campaigns.jsonl` — 31 detected influence campaigns
- `indicators.jsonl` — 497 per-category threat indicators (GREEN/YELLOW/ORANGE)
- `ais_signals.jsonl.gz` — 300K vessel positions (notebook 06 optional)

The `indicators.jsonl` file is the key ground truth — it tells you which
threat categories were elevated on which days, and why.
