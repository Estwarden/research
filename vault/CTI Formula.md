---
status: evergreen
tags: [cti, formula, diagnostics]
---

# CTI Formula

The Composite Threat Index combines 30+ data sources into a single threat level per region per day: GREEN, YELLOW, ORANGE, RED. It's meant to answer "how worried should we be about Baltic security right now?"

For most of the study period, the answer was YELLOW — 80% of the time. That's not useful. A threat level that's always elevated is the same as no threat level at all.

## Why It Was Stuck

The research ran a diagnostic chain (nb14 → 15 → 16 → 17) that peeled back the problem layer by layer. This is the strongest work in the repository.

**Layer 1 — FIMI dominates everything (nb14).** The FIMI (Foreign Information Manipulation and Interference) sub-score alone pushed CTI past the YELLOW threshold. Campaigns contributed 43% and narrative laundering 19%. Even if every other sensor read zero — no ships, no aircraft, no radiation, no GPS jamming — the FIMI score kept the system at YELLOW.

**Layer 2 — Laundering is mostly garbage (nb15).** 73% of detected "laundering" events were irrelevant: NHL hockey scores flowing through Russian sports channels, Soyuz launch coverage, domestic Russian politics. The laundering detector matched on structural patterns (content moving between source categories) without checking if the content was actually threat-relevant. A relevance filter cut the noise by 80%.

**Layer 3 — Campaigns without evidence (nb16).** 70% of campaigns (26 of 37) had no detection method — no Fisher score, no Hawkes analysis, no FIMI indicators. They existed because someone manually created them or an early heuristic fired. These evidence-free campaigns contributed 73% of the campaign severity score. An evidence gate stopped scoring campaigns that couldn't explain why they were campaigns.

**Layer 4 — Baselines were wrong (nb17).** Standard z-scores (mean + standard deviation) don't work when the data has huge outliers, which AIS and ADS-B always do (a single ship convoy can spike volume 10x). Robust z-scores (median + MAD) are strictly better — they ignore outliers while still detecting genuine anomalies. Binary mode (present/absent) works best for the most volatile sources.

## What's Deployed

The diagnostic fixes are all in production:

- **Laundering relevance filter** — requires cluster to touch 3+ source categories before counting as laundering. Noise drops 80%.
- **Campaign evidence gate** — campaigns without any detection method get scored lower.
- **Robust baselines** — median+MAD for all sources, binary for high-CV sources (AIS, ADS-B).
- **DEGRADED flag** — days with <70% source coverage are marked, not scored normally.
- **Dead collector weight=0** — ACLED and IODA (zero data) removed from formula.

GREEN is now achievable under the corrected algorithm.

## What Went Wrong: The Weight Disaster

After diagnosing the problem, nb18 tried to fix it by recalibrating weights. The "consensus" approach cut signal weights from 72 to 24 — a 67% reduction. The result: **the algorithm was dead.** 30 of 50 study days scored near zero. Only GPS jamming data (available 15 of 88 days) produced meaningful signals.

VALIDITY.md caught this: "72→24 kills the algorithm." The moderate path (nb35) targets ~45, keeping FIMI share at ~46% instead of the broken 61%. But this needs 90+ days of stable collector data to validate — which requires fixing the dead collectors first (see [[Data Quality]]).

The YELLOW=7.9 threshold (nb19) is also wrong — it was calibrated against the broken algorithm's own output. Keep production thresholds (15.2/59.7/92.8) until weights are properly validated.

## The Sequence

You can't fix the CTI out of order:

1. Fix collectors ([[Data Quality]]) — you need stable inputs
2. Run 90 days under corrected algorithm — you need enough data
3. Validate moderate weights (~45) — you need the data to test against
4. Re-derive thresholds from external ground truth (ISW, ACLED) — not self-referential
5. Deploy

We're stuck at step 1.

## Key Experiments

The diagnostic chain (nb14-17) is worth reading directly — each notebook has clear methodology and reproducible results. nb18-19 are worth reading as cautionary tales about premature optimization. nb35 (moderate weights) is the current best proposal.

Full details: `../methodology/FINDINGS.md` Part 1, `../methodology/VALIDITY.md`.
