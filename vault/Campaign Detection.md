---
status: evergreen
tags: [campaigns, detection, fimi, disinformation]
---

# Campaign Detection

In March 2026, social media accounts began promoting a ["Narva People's Republic"](https://www.euronews.com/2026/03/19/a-peoples-republic-on-natos-edge-the-narva-narrative-testing-europes-defences) — complete with a flag, coat of arms, and rhetoric echoing the Donetsk/Luhansk playbook. The campaign mixed calls for armed resistance with claims of Estonian "genocide" against Russian speakers. Estonia's security services [called it cheap disinformation](https://www.dw.com/en/estonian-city-targeted-by-russian-language-separatist-campaign/video-76570228), but it reached significant audiences and coincided with airspace violations and border provocations.

This is what EstWarden's campaign detection is meant to catch automatically. Five methods have been tested. All are bottlenecked on the same thing: not enough labeled examples.

## The Labeled Data Wall

Every detection method hits this wall:

- **6 labeled hostile clusters** out of 2,278 total
- Fisher needs 33+ for statistical significance (p<0.01)
- Velocity needs 30+ labeled narratives (has 8)
- Cascade topology needs 100+ events (has 0)

There's no way around it. You cannot validate a binary classifier on 6 positive examples. The [EUvsDisinfo database](https://euvsdisinfo.eu/disinformation-cases/) has 1,000+ documented cases — cross-referencing against our clusters (R-52 in [[Research Directions]]) is the fastest path to enough labels.

## What's Been Tested

### Hawkes Branching Ratio (nb24) — the most promising

Models information cascades as self-exciting point processes: each signal can trigger subsequent signals, and the branching ratio measures how much triggering happens. State-heavy clusters show **BR=0.53** vs clean clusters at **0.22** — 2.4x more self-excitation (p=0.04 on N=281 clusters).

This works because it measures a *structural property* of how information spreads, not content features that can be gamed. Coordination produces temporal clustering regardless of what the content says.

### Fisher Discriminant (nb25) — honest failure

The original claim of F1=0.92 was wrong. Proper leave-one-out cross-validation gave **F1=0.615** (bootstrap CI [0.333, 1.000]). The model is: `score = 0.670 * state_ratio + 0.742 * fimi_score`. With only 2 features and 6 hostile examples, this is what you'd expect. nb40 proposes adding Hawkes BR as a third feature, but it's blocked on labels.

### FIMI Regex (nb29) — cost-effective pre-filter

Pattern matching for hedging language ("allegedly", "so-called") and amplification markers. Catches 80% of hostile clusters without any LLM call. Limited to Russian and English — extending to Estonian/Latvian/Lithuanian requires linguistic work.

### Narrative Velocity (nb27) — good idea, no validation

Tracks week-over-week change in state media ratio within a narrative. The concept is sound: when a narrative gets weaponized, state media ratio spikes. But F1=1.00 on 8 examples is statistically meaningless — any reasonable parameters would score well on data that small.

### Co-Coverage Network (nb30) — structural but indirect

Measures editorial coordination: how often sources cover the same stories. State media Jaccard=0.26 vs trusted=0.16 (63% premium). Stable and structural, but measures coordination, not hostility. Two sources can coordinate without being hostile.

## The Bild Map Lesson

The case that exposed the architecture's blind spots. Bild.de published a potential Russian invasion scenario for the Baltics. Ukrainian Telegram channels amplified it — not Russian channels. Key fabrications were *added* during amplification:

- @smolii_ukraine (392K subscribers) added "1-2 months" timeline — not in the original
- @channel5UA fabricated "laws passed" claim — entirely invented
- @Tsaplienko escalated certainty from "scenario" to imminent threat

The system missed everything because:
1. **Velocity detection required Russian origin** — Ukrainian channels didn't trigger it
2. **8 of 10 amplifiers weren't monitored** — 40% watchlist coverage
3. **No mutation detection** — nobody checked if amplifiers were adding claims
4. **Category gap** — named Ukrainian commentators fell between existing categories

This single case drove the [[Improvement Plan]]'s Phase 0 (watchlist expansion, RU-origin gate removal) and [[Research Directions]] R-53 (mutation detection).

## What's Deployed

- Two-pass clustering (cosine 0.75 → 0.82 revalidation for large clusters)
- Factual IBI prompt (intent-based prompting over-triggered on geopolitical coverage)
- Laundering relevance filter
- Campaign evidence gate

Everything else is waiting on more labeled data.

## Deep Dives

The methodology docs have the full experimental details — 30 experiments documented across 742 lines in `../methodology/FINDINGS.md`. Topic-specific: `../methodology/FINDINGS.campaign-detection.md`, `../methodology/FINDINGS.hawkes-coordination.md`, `../methodology/FINDINGS.narrative-velocity.md`.
