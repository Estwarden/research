# Research: Watchlist Coverage Gap — Bild Baltic Map Campaign

**Date:** 2026-03-22
**Case:** Bild Baltic Map Panic (March 16-21, 2026)
**Researcher:** EstWarden automated analysis + manual verification

## Executive Summary

The Bild Baltic Map campaign (1.5M views, 17 channels, 0 verifiable sources) was not detected by EstWarden's automated systems. Root cause: 8 of 10 amplifying channels were not in the monitoring watchlist. This document analyzes the gap and recommends additions.

## Current Watchlist Coverage

| Metric | Value |
|--------|-------|
| Total channels monitored | 73 |
| Ukrainian language | 40 |
| Russian language | 26 |
| Categories: ru_state/ru_proxy | 31 (42%) |
| Categories: unverified_* | 27 (37%) |
| Categories: trusted | 15 (21%) |

## Bild Map Campaign — Channel Coverage

| Channel | In watchlist | Handle in YAML | Subscribers (TGStat) | Category |
|---------|-------------|----------------|---------------------|----------|
| @insiderUKR | ✅ | insider_ua | 2.16M | unverified_anonymous |
| @uniannet | ✅ | uniannet | 765K | unverified_media |
| @pravda_gerashchenko | ✅ | gerashchenko | ~400K | unverified_commentator |
| @smolii_ukraine | ❌ | — | 392K | — |
| @Tsaplienko | ❌ | — | 336K | — |
| @BerezaJuice | ❌ | — | ~100K | — |
| @TSN_ua | ✅ (as TCH_channel) | TCH_channel | 795K | trusted |
| @channel5UA | ❌ | — | ~50K | — |
| @portnikov | ❌ | — | ~200K | — |
| Babchenko/gordonua | ❌ | — | web only | — |

**Corrected coverage: 4 of 10 channels were monitored (40%)**
- @insiderUKR ✅ (but as `insider_ua`)
- @uniannet ✅
- @pravda_gerashchenko ✅ (as `gerashchenko`)
- @TSN_ua ✅ (as `TCH_channel`)

**Still missing: 6 channels**
- @smolii_ukraine — 392K subs, #80 on Telemetr.io, politics category, **KEY FABRICATOR**
- @Tsaplienko — 336K subs, #94 on Telemetr.io, war correspondent, 1+1 journalist
- @BerezaJuice — ~100K subs, ex-MP, YouTube clickbait crosspost
- @channel5UA — ~50K subs, TV channel's Telegram
- @portnikov — ~200K subs, opinion leader/commentator
- Babchenko/gordonua — web-only, opinion blog

## Why These Channels Were Missing

### Design Assumption
The watchlist was designed with two goals:
1. Monitor **Russian state/proxy channels** for narrative origin detection
2. Monitor **Ukrainian anonymous/sensationalist channels** for amplification detection

Channels like Tsaplienko and Smolii fall in a gap — they are:
- Not Russian (so not in ru_state/ru_proxy)
- Not anonymous (so not in unverified_anonymous)
- Not mainstream media (so not in trusted)
- They are **named commentators/journalists** who sometimes fabricate

### Category Gap
The current categories don't have a good fit for "named Ukrainian commentators who sensationalize":
- `unverified_commentator` — closest match, but only 6 channels in this category
- `unverified_media` — for news outlets, not individuals
- `trusted` — would give them too much credibility

## Recommended Additions

### Priority 1: Channels involved in Bild map fabrication

```yaml
- handle: smolii_ukraine
  name: Андрій Смолій
  url: https://t.me/s/smolii_ukraine
  lang: uk
  category: unverified_commentator
  tier: T1
  notes: "392K subs. Named commentator. FABRICATED timeline claims in Bild map case (March 2026). Adds urgency not in source material."
  rationality:
    calibration: low
    updating: low
    evidence: low
    uncertainty: low
    independence: medium
  region:
  - global

- handle: Tsaplienko
  name: ЦАПЛІЄНКО_UKRAINE FIGHTS
  url: https://t.me/s/Tsaplienko
  lang: uk
  category: unverified_commentator
  tier: T1
  notes: "336K subs. 1+1 journalist. Amplifies without fabrication but adds dramatic framing. High reach."
  rationality:
    calibration: medium
    updating: medium
    evidence: medium
    uncertainty: low
    independence: medium
  region:
  - global

- handle: BerezaJuice
  name: Борислав Береза
  url: https://t.me/s/BerezaJuice
  lang: uk
  category: unverified_commentator
  tier: T2
  notes: "~100K subs. Ex-MP. YouTube clickbait crossposter. Uses sensational thumbnails. Engagement farming."
  rationality:
    calibration: low
    updating: low
    evidence: low
    uncertainty: low
    independence: medium
  region:
  - global

- handle: channel5UA
  name: 5 канал
  url: https://t.me/s/channel5UA
  lang: uk
  category: unverified_media
  tier: T2
  notes: "~50K subs. TV channel Telegram. FABRICATED 'laws passed for invasion' in Bild map case."
  rationality:
    calibration: low
    updating: low
    evidence: low
    uncertainty: low
    independence: medium
  region:
  - global

- handle: portnikov
  name: Віталій Портников
  url: https://t.me/s/portnikov
  lang: uk
  category: unverified_commentator
  tier: T2
  notes: "~200K subs. Opinion leader. Narrative seed — plants fear framework without direct fabrication."
  rationality:
    calibration: medium
    updating: medium
    evidence: medium
    uncertainty: low
    independence: high
  region:
  - global
```

### Priority 2: Other high-reach UA channels not yet monitored

Based on TGStat/Telemetr.io rankings, these channels have >300K subscribers and are not in the watchlist:

| Channel | Subscribers | Category suggestion |
|---------|------------|-------------------|
| @nikolaevskiy_vanek | 2.7M | unverified_anonymous |
| @ukraina_segodnya | 1.5M | unverified_anonymous |
| @monitor_ua | 872K | unverified_anonymous |
| @gordondmitry | 300K | unverified_commentator |
| @arestovichofficial | 288K | unverified_commentator |
| @goncharenko | 227K | unverified_commentator |

## Detection Algorithm Gaps

### Gap 1: Origin blindspot
**Current:** Narrative velocity and amplification detection require Russian origin.
**Needed:** Origin-agnostic detection — any narrative spreading across multiple watched channels within a time window.

### Gap 2: No fabrication detection
**Current:** System detects amplification (same narrative appearing in multiple channels).
**Needed:** Detect when channels ADD claims not in the source material (embedding comparison).

### Gap 3: No velocity alerting
**Current:** No threshold for cumulative views/forwards.
**Needed:** Alert when total views across channels on same topic exceeds threshold (e.g., 500K in 24h).

### Gap 4: Narrative taxonomy
**Current:** "Baltic invasion panic" as fabricated by UA channels not in keyword taxonomy.
**Needed:** Add keywords: "нападение на Эстонию", "вторжение в Прибалтику", "атака на НАТО", "final stage", "1-2 months", "законы приняты".

## Data for Backfill

### Campaign: Bild Baltic Map Panic
- **Name:** Bild Baltic Map Panic — Ukrainian Channel Fabrication
- **Severity:** HIGH
- **Confidence:** 0.95
- **Start:** 2026-03-16T05:57:00Z
- **End:** 2026-03-21T12:18:00Z
- **Target regions:** baltic, estonia
- **Trigger:** Bild article "Bereitet Putin einen Angriff auf Estland vor?"
- **Fabricated claims:** Timeline (1-2 months), Laws passed, "beschlossene Sache"

### Signals to link (if available in DB)
Search for signals containing: "Bild", "Estland", "Angriff", "Прибалтика", "Эстония", "нападение" between 2026-03-16 and 2026-03-22.

## References
- [TGStat Ukraine ratings](https://uk.tgstat.com/en)
- [Telemetr.io Ukraine catalog](https://telemetr.io/en/catalog/ukraine)
- [Detector Media: Top UA Telegram channels](https://en.detector.media/post/from-trukha-to-gordon-the-most-popular-channels-of-the-ukrainian-telegram)
- [JTA: Non-institutionalized news channels 2023](https://www.jta.com.ua/wp-content/uploads/2023/03/Telegram-Channels-2023_EN.pdf)
- Case study: https://estwarden.eu/case-studies/bild-map/
