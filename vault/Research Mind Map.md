---
status: evergreen
tags: [overview, mind-map, patterns]
---

# Research Mind Map

Six patterns that explain why this research looks the way it does — and where it goes next.

## 1. The System Is Eating Its Own Noise

When Latvia's defense ministry [accused Russia of spreading false claims](https://therecord.media/latvia-accuses-russia-of-disinformation-campaign-ukraine-war) that Baltic states opened airspace to Ukrainian drones, EstWarden's campaign detection should have flagged it. Instead, the Composite Threat Index was already at YELLOW because of NHL game summaries and Soyuz launch coverage that the "laundering detector" misidentified as narrative amplification.

This is the foundational problem. 73% of laundering events are noise. 70% of campaigns have zero detection evidence behind them. The FIMI score — meant to measure foreign information manipulation — was dominated by irrelevant content that happened to flow through Russian-language channels.

The fix was surgical: a relevance filter that cut laundering noise by 80%, and an evidence gate that stopped scoring campaigns without detection methods. Both deployed. The CTI immediately became more meaningful. But the lesson is broader: **any fused-intelligence system will amplify noise unless every input is independently validated.**

## 2. Six Hostile Labels Is Not Enough

Every detection method crashes into the same wall: we only have 6 labeled hostile clusters.

When the Fisher discriminant claimed F1=0.92, it looked like a breakthrough. But that score came from testing on the same tiny dataset used for training. Proper leave-one-out cross-validation on 30 samples gave F1=0.615 — barely better than a coin flip. Narrative velocity claimed F1=1.00, but on 8 examples — you could fit almost any model to 8 data points and get perfect accuracy.

The Hawkes branching ratio is the exception: tested on 281 clusters, it shows state-heavy clusters have 2.4x more coordination than clean ones (p=0.04). It works because it measures a structural property (temporal self-excitation) rather than trying to classify with tiny labeled sets.

The fix is R-38: build a proper labeled dataset by cross-referencing against [EUvsDisinfo's database](https://euvsdisinfo.eu/disinformation-cases/) of 1,000+ documented cases. Until then, treat all detection thresholds as provisional.

## 3. Diagnostics Work, Prescriptions Don't (Yet)

Finding that laundering is 73% noise required only counting. Fixing it required a relevance filter — straightforward. Finding that 12 collectors are dead required only checking uptime. Fixing them is ops work.

But when the research tried to prescribe *new* values — weight total 24, YELLOW threshold 7.9 — it went wrong. The weight cut killed the algorithm (30 of 50 days scored near zero). The threshold was calibrated against the broken algorithm's own labels — circular validation.

The pattern: **diagnostic findings from nb14-17 are the strongest work in this repo. Prescriptive findings from nb18-19 are the weakest.** The moderate-weights path (nb35, target ~45) respects this distinction.

## 4. Production Has Outrun the Research

The research notebooks (nb20-23) used Sentinel-2 with 3 spectral indices and no sensor fusion. Meanwhile, [production shipped a 7-source pipeline](https://blog.estwarden.eu/investigations/multi-source-geoint/) with:

- **Camouflage detection** via NDRE — real vegetation has a red-edge reflectance spike (700-783nm) that no paint replicates. High NDVI + low NDRE = camouflage suspect.
- **EMCON detection** — when a base shows satellite activity but AIS/ADS-B transponders go silent, someone turned their tracking off deliberately. Silence is the signal.
- **Dual-pol SAR** — VH/VV polarization ratio distinguishes metal (low) from vegetation (high), through clouds, at night.
- **Multi-source confidence** — one sensor is a lead, three sensors is intelligence.
- **Alternative hypotheses** — every observation gets exercise/deployment/routine ranked by likelihood, borrowed from ACH methodology.

This means several research gaps are already closed in production but lack the formal validation that notebooks provide. Research needs to catch up: validate the NDRE camouflage detector against known concealment, test EMCON correlation against ISW timelines, and benchmark the multi-source confidence scoring.

## 5. The Bild Map Showed What's Missing

In early 2025, German tabloid Bild published a map of a potential Russian invasion of the Baltic states. Ukrainian Telegram channels — not Russian ones — amplified it with fabricated timelines ("1-2 months"), invented legal claims ("laws passed"), and escalating certainty. The system missed it completely because:

- The amplifiers weren't Russian-origin, so velocity detection didn't fire
- 8 of 10 amplifying channels weren't in the watchlist
- No mutation detection existed to catch claims being *added* to the original story
- The channels fell between categories — not state media, not anonymous, not mainstream

This single case study exposed the detection architecture's blind spots better than any statistical test. It's why the [[Improvement Plan]] starts with watchlist expansion and origin-agnostic detection, and why [[Research Directions]] proposes mutation detection (R-53) and actor network analysis (R-51).

## 6. The Critical Path Is Sequential

```
Fix collectors → stable 90 days → recalibrate weights
    → validate thresholds → validate detection → deploy
```

Can't parallelize. But there's independent work that *can* run in parallel: actor network analysis, frequency-domain analysis, bot detection, stylometry, and the EUvsDisinfo labeling effort all use existing data and don't depend on the critical path.

The [[Improvement Plan]] maps what goes where. The [[Research Directions]] lists what can start now.
