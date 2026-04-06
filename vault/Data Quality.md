---
status: evergreen
tags: [data-quality, collectors, infrastructure]
---

# Data Quality

The primary blocker for all other research tracks. 76% of study days have inadequate sensor coverage. Fix this before optimizing anything else.

## The Core Problem

Only **24% of days** have adequate sensor coverage. The CTI formula is being tuned on degraded data, making all weight/threshold calibrations unreliable.

## Collector Health (nb09, nb32)

| Collector | Status | Data Rate | Problem |
|-----------|--------|-----------|---------|
| AIS | Working | 782K signals/90d | 4x throughput swings — collector instability, not naval activity |
| RSS | Working | 34K/90d | Stable. Primary text source. |
| ADS-B | Degraded | 14K/90d | 76% military aircraft misclassification |
| Radiation | Working | 5K/90d | Stable |
| Telegram channels | Partial | 4K/90d | Channel collector works; legacy telegram mostly dead (20%) |
| FIRMS | Working | 1.7K/90d | Noisy but has real per-site signal |
| GDELT | Degraded | 1K/90d | Worked until Mar 20, then gaps |
| GPS jamming | Strongest | 171/90d | Only 15 of 88 days have data — sparse but highest signal quality |
| ACLED | Dead | 0 | Zero data since study start |
| IODA | Dead | 0 | Zero data since study start |
| Sentinel-2 | Dead | 89/90d | Collector died Mar 14 |

12+ collector types went dead between Mar 15–20.

## AIS Deep Dive (nb33)

AIS dominates signal volume (92%) but has fundamental problems:

- **4x throughput swings** from collector instability — looks like naval activity surges but isn't
- **Binary mode recommended:** treat AIS as "present/absent" rather than count-based
- **Baseline method:** robust z-score (median+MAD) with binary fallback

## Embedding Quality (nb34)

Multilingual embeddings have quality gaps across Baltic languages:

| Language | Quality | Coverage |
|----------|---------|----------|
| English | Best | Full |
| Russian | Good (3-5% below EN) | Full |
| Lithuanian | Adequate | Sparse |
| Estonian | Too sparse to validate | Need more feeds (F-03) |
| Latvian | Too sparse to validate | Need more feeds (F-03) |

**Fix:** Add ERR.ee, LSM.lv, 15min.lt RSS feeds (F-03 in roadmap) to get ≥50 clustered signals per language.

## What's Deployed

| Fix | Impact |
|-----|--------|
| DEGRADED flag | Days with missing collectors are marked, not scored normally |
| Dead collector weight = 0 | ACLED, IODA removed from formula |
| AIS binary mode | Throughput swings no longer spike CTI |
| Robust z-scores | median+MAD for all sources |

## Experiments

| # | Notebook | Focus |
|---|----------|-------|
| 09 | `09_system_health_audit` | Collector health check |
| 10 | `10_baseline_stability` | Per-source CV analysis |
| 11 | `11_signal_value_analysis` | Information content per source |
| 32 | `32_collector_health` | Deep collector monitoring |
| 33 | `33_ais_deep_dive` | AIS-specific analysis |
| 34 | `34_embedding_quality` | Cross-lingual embedding gaps |
| 39 | `39_ais_tiers` | AIS source tiering |

## Next Steps

1. **Fix dead collectors** (F-01) — ACLED, IODA, Telegram, ADS-B, Sentinel-2
2. **Add Baltic media feeds** (F-03) — ERR.ee, LSM.lv, 15min.lt
3. **Fix category metadata** (F-04) — 20K signals missing `category` field
4. **Monitor for 90+ stable days** before recalibrating weights/thresholds
