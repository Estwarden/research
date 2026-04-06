---
status: evergreen
tags: [index, overview]
---

# EstWarden Research

[EstWarden](https://estwarden.eu) watches the Baltic. It fuses 30+ data sources — ship tracking, satellite imagery, Telegram channels, GPS jamming reports, radiation monitors, news feeds across five languages — into a daily threat picture for Estonia, Latvia, Lithuania, Finland, and Poland.

The threats are real and current. Russia operates military bases 100km from NATO borders — the 76th Guards Airborne at Pskov, naval facilities at Kronstadt, training grounds near Luga. In March 2026, NASA FIRMS detected a [massive fire at the Pskov-76VDV training ground](https://www.threads.com/@l._domenico/post/DV-25t0lbst), 32km from Estonian territory. Russian GPS jamming from Kaliningrad, Leningrad, and Pskov districts [disrupts commercial aviation daily](https://www.defensenews.com/global/europe/2025/07/02/researchers-home-in-on-origins-of-russias-baltic-gps-jamming/) across the Baltic. A [coordinated "Narva Republic" campaign](https://www.euronews.com/2026/03/19/a-peoples-republic-on-natos-edge-the-narva-narrative-testing-europes-defences) pushes separatist narratives targeting Estonia's Russian-speaking population, echoing the Donbas playbook. Russia's [shadow fleet switches off AIS](https://www.ftm.eu/articles/switching-ais-off-shadow-fleet-going-even-darker) to evade sanctions — with six times more tracking gaps than European ships.

This research diagnosed critical problems in how EstWarden processes all of this, and proposed fixes. Some worked. Some didn't. This vault is the honest accounting.

> **This is an [Obsidian](https://obsidian.md) vault.** Open `vault/` in Obsidian for linked navigation and graph view. See [[Using This Vault]].

## The Core Problem

EstWarden's Composite Threat Index — a single number summarizing regional security — was stuck at YELLOW (elevated) **80% of the time**, regardless of what was actually happening. The research found three root causes:

1. **The algorithm was eating its own noise.** 73% of "narrative laundering" events were actually sports scores and domestic Russian news. 70% of detected "campaigns" had zero evidence behind them. The system was alarming on garbage.

2. **The sensors were broken.** 12+ data collectors died in mid-March. 76% of days had degraded coverage. The algorithm was being tuned on data with massive holes in it.

3. **The validation was circular.** New thresholds were calibrated against the broken algorithm's own labels. Fisher discriminant claimed F1=0.92 but actually scored 0.615 when properly tested. You can't validate a system against itself.

The diagnostic findings (what's broken) are solid and mostly deployed. The prescriptive findings (what to change) need more work. Read [[Research Mind Map]] for the patterns, or jump to a track:

## Research Tracks

**[[CTI Formula]]** — Why the threat index is stuck at YELLOW, and what actually fixed it. The diagnostic chain (nb14→15→16→17) is the strongest work here.

**[[Campaign Detection]]** — Detecting hostile campaigns like the Narva Republic narrative or the Bild invasion map fabrication. Five methods tested; all are bottlenecked on having only 6 labeled hostile examples.

**[[Satellite Monitoring]]** — From single-camera analysis to a [7-source fusion pipeline](https://blog.estwarden.eu/investigations/multi-source-geoint/) with camouflage detection, EMCON alerts, and dual-pol radar. Production is now ahead of the research.

**[[Data Quality]]** — The primary blocker. 76% of days are degraded. Fix this before optimizing anything else.

## What's New (not yet in research)

The [multi-source GEOINT blog post](https://blog.estwarden.eu/investigations/multi-source-geoint/) (April 2026) describes production capabilities that supersede several research findings:

- **7-source fusion** with confidence scoring (research said fusion was "deleted in migration")
- **Camouflage detection** via NDRE red-edge spectral analysis (not in any notebook)
- **EMCON detection** — satellite activity + silent transponders = concealment (not in research)
- **Dual-pol SAR** (VV + VH polarization) — the SAR integration the research called for
- **Alternative hypotheses** per observation (exercise vs deployment vs routine)

These need to be back-ported into the research as validated methods.

## Action Plans

**[[Improvement Plan]]** — What to deploy this week, this month, and this quarter. Five items are ready now.

**[[Research Directions]]** — 11 new experiments (R-50 to R-60) covering NLP, actor networks, adversarial robustness, and the gaps identified against our [[Gaps Analysis|Education course material]].

## Reference

| What | Where |
|------|-------|
| Experiment notebooks (43 scripts) | [[Experiment Index]] |
| Datasets and freshness | [[Data Catalog]] |
| Terminology | [[Glossary]] |
| Deployment status | [[Status Dashboard]] |
| Deep findings | `../methodology/FINDINGS.md` (742 lines) |
| What's broken | `../methodology/VALIDITY.md` |
| Phased roadmap | `../ROADMAP.md` |
