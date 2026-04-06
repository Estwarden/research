---
status: evergreen
tags: [data-quality, collectors, infrastructure]
---

# Data Quality

The primary blocker for everything else. 76% of study days had inadequate sensor coverage. You can't tune an algorithm on data that isn't there.

## What's Broken

12+ data collectors died between March 15-20. Some were never reliable:

**Dead:** ACLED (conflict events, zero data), IODA (internet outages, zero data). These are meant to provide ground truth for threat assessment — without them, the CTI is blind to physical-world events.

**Crippled:** Sentinel-2 satellite collector died March 14 — but [production has since rebuilt it](https://blog.estwarden.eu/investigations/multi-source-geoint/) into a 7-source pipeline. Legacy Telegram collector at 20% uptime (the newer telegram_channel collector works fine).

**Unreliable:** ADS-B aircraft tracking has **76% military aircraft misclassification** — Russian civilian airlines tagged as military because the ICAO hex-range matching is wrong. AIS ship tracking has **4x throughput swings** that look like naval activity surges but are actually collector restarts. GPS jamming data is the strongest signal source (Russia [jams Baltic GPS daily](https://www.military.com/daily-news/2025/09/02/what-know-about-russias-gps-jamming-operation-europe.html) from Kaliningrad, Pskov, and Leningrad districts) but only has data on 15 of 88 days.

## Why It Matters Practically

Every research finding is qualified by data quality:

- **Weight recalibration** (nb18, nb35) — can't determine correct weights when 12 sources report zero. The "consensus" that cut weights from 72→24 was really measuring "which collectors happen to be alive?"
- **Threshold calibration** (nb19) — YELLOW=7.9 was fit to 50 days of data with 13 transitions and massive collector gaps. Meaningless.
- **Fisher pre-screen** (nb25) — depends on `state_ratio`, which requires the `category` field. 20K signals are missing this field.
- **Narrative velocity** (nb27) — same category dependency.
- **Satellite baselines** (nb20-23) — Sentinel-2 was dead, making seasonal profiles incomplete. Production has since fixed this.

## The AIS Problem

AIS deserves special mention because it's 92% of signal volume. Russia's shadow fleet [switches off AIS six times more often](https://www.ftm.eu/articles/switching-ais-off-shadow-fleet-going-even-darker) than European vessels. In November 2024, hundreds of ghost ships appeared on AIS in the Baltic when a Finnish ground receiver was likely hacked and fed false position data. The Swedish Navy has linked shadow fleet vessels to [Russian military protection operations](https://balticsentinel.eu/8397115/western-sanctions-failed-to-curb-russia-s-shadow-fleet-in-2025-instead-it-grew-in-size) in the Baltic.

For the CTI, nb33 found that AIS throughput swings are collector artifacts, not naval intelligence. Binary mode (present/absent per vessel type per day) is more reliable than count-based scoring.

## Embedding Quality Across Languages

Baltic security requires monitoring in 5+ languages. nb34 found embedding quality drops as you move from English to Russian to Lithuanian, with Estonian and Latvian too sparse to validate. The [EU's FIMI-ISAC framework](https://www.eeas.europa.eu/eeas/information-integrity-and-countering-foreign-information-manipulation-interference-fimi_en) explicitly calls for cross-lingual detection — we can't do that until Baltic-language signal volume increases.

Adding ERR.ee, LSM.lv, and 15min.lt RSS feeds (F-03 in roadmap) would double Baltic-language signals within two weeks.

## What's Deployed

- DEGRADED flag for days with missing collectors
- Dead collector weight=0 (ACLED, IODA)
- AIS binary mode
- Robust z-scores (median+MAD) for all sources

## What's Needed

1. **Fix remaining collectors** (F-01) — primarily ADS-B military classification and GPS jamming coverage gaps
2. **Backfill category metadata** (F-04) — 20K signals missing category, blocking Fisher and velocity detection
3. **Add Baltic feeds** (F-03) — ERR.ee, LSM.lv, 15min.lt
4. **Run stable for 90 days** — then and only then can weights and thresholds be recalibrated
