# Research Validity Assessment

**Date:** 2026-03-25
**Reviewer:** Post-completion audit of 24 ralph-automated research tasks

This document is the honest assessment of what's valid, what's broken, and what
should NOT be deployed from this research.

---

## 🔴 DO NOT DEPLOY: Corrected CTI Weights (nb18/nb19)

The "consensus weights" in nb18 reduced signal weights from 72→24 (67% cut) by
zeroing 4 sources and halving the rest. This makes FIMI 61% of total weight and
produces **near-zero scores** for 30 of 50 days in the study period.

| Day Range | Corrected CTI | Stored CTI | Problem |
|-----------|--------------|------------|---------|
| Feb 5–Mar 9 | 0.00–1.61 | 4.5–21.5 | Algorithm is dead |
| Mar 10–17 | 7–20 | 11–21 | Reasonable |
| Mar 18–25 | 27–50 | 16–31 | Over-reactive FIMI spikes |

**Why it's broken:** Only gpsjam (10pts) produces meaningful signal, but gpsjam
has data on only 15 of 88 days. Other sources got cut to 1-3pts each and most
have unstable baselines, so their z-scores round to zero under robust methods.

**What to do instead:** Fix collectors first, THEN adjust weights. The diagnostic
(dead collectors, noisy baselines) is correct. The prescription (gut the weights)
is wrong. Moderate approach:
- Zero truly dead sources: acled=0, ioda=0 (no data at all)
- Keep gdelt at reduced weight (2 instead of 4) — was working until Mar 20
- Keep telegram at 4 (was 6) — telegram_channel works, legacy telegram dead
- Keep adsb at 5 (was 10) — collector has gaps but produces data
- Keep firms at 6 (was 8) — noisy but has real signal per-site
- **Signal total: ~45 instead of 72 or 24**
- FIMI stays at 38. Total = ~83. FIMI share = 46% (not 61%)

**The YELLOW=7.9 threshold is calibrated to the broken algorithm. DO NOT USE IT.**
Keep production thresholds (15.2/59.7/92.8) until collectors are fixed and weights
are properly validated on 90+ days of stable data.

---

## 🔴 DO NOT DEPLOY: Narrative Velocity Thresholds

F1=1.00 on N=5 hostile + N=3 organic is meaningless. This is a 2-parameter model
(velocity_threshold, state_ratio_threshold) fit on 8 data points. Any reasonable
parameters would achieve F1≥0.83 on this dataset.

**What's valid:** The CONCEPT of narrative velocity (Δstate_ratio/Δweek) is sound
and the weaponization pattern (0%→10%→59%) documented in Experiment 29 is real.

**What's not valid:** The specific thresholds (0.20, 0.15) and the F1=1.00 claim.
Need 30+ labeled narratives before setting production thresholds.

---

## 🟡 DEPLOY WITH CAVEATS

### Laundering Relevance Filter (nb15)
**Valid.** 73% noise rate is reproducible. The fix (require Baltic/security keywords)
is conservative and safe. Score reduction 5.45→2.56 with merge+filter.

**Caveat:** The keyword list is hand-curated and may miss new narratives. Should be
config-driven, not hardcoded.

### Campaign Evidence Tiers (nb16)
**Valid with updated data.** The re-export shows 21 campaigns have signals but no
detection_method (manual/blitz), 5 are truly empty. The original analysis
miscounted because campaigns_full.csv lacked signal_count.

**Corrected recommendation:** Don't exclude all campaigns without detection_method.
Instead: exclude campaigns with signal_count=0 AND no detection_method. Only 5
campaigns, not 28-29.

### Robust Baselines — median+MAD (nb17)
**Valid.** Robust z-scores are strictly better than mean+std. Safe to deploy for
ALL sources. No downside, only upside.

### Cluster Size Cap + Two-Pass (nb26)
**Valid.** Mega-clusters at cosine 0.75 are a real problem (98% low coherence).
Two-pass re-validation at 0.82 for clusters >10 is sound.

### FIMI Regex Detection (nb29)
**Interesting but undertested.** Hedging/omission regex patterns on N=30 (6 hostile).
Promising supplement to LLM but don't replace LLM-based framing analysis.

---

## ✅ SOLID FINDINGS (deploy or build on)

### Diagnostic Results
- **FIMI floor decomposition (nb14):** The WHY of permanent-YELLOW is correctly identified
- **Campaign tier analysis (nb16):** Evidence-free campaigns inflate the score — true
- **AIS regime detection (nb33):** CV=2.6% within stable periods — collector, not data
- **Dead collectors (nb32):** 12 sources dead since Mar 15-20, confirmed
- **Fisher NON-replication (nb25):** F1=0.615 on N=30 — honest science

### Satellite Analysis
- **Seasonal baselines (nb20):** Method is correct (IF GEE auth works)
- **CCDC breakpoint concept (nb22):** Correct approach, needs GEE execution
- **Spectral indices (existing FINDINGS):** BSI+NDBI segmentation validated

### Media/Campaign Theory
- **Hawkes branching ratio (nb24):** Principled metric (BR=0.52 state vs 0.22 clean)
- **Co-coverage confirms coordination (nb30):** State outlets share more stories
- **Fabrication detector is stable (nb31):** 100% consistency across 3 runs

---

## Misleading Claims in FINDINGS.md

| Claim | Actual | Fix |
|-------|--------|-----|
| "stuck at YELLOW 85% of days" | 42% overall, 80% in Mar 7-25 only | Specify date range |
| "FIMI floor drops from 8.38 to 10.34" | Numbers are swapped or mislabeled | Fix table labels |
| "validated Fisher discriminant F1=0.92" | Did NOT replicate: F1=0.615 on N=30 | Lead with non-replication |
| "narrative velocity F1=1.00" | N=8 total, meaningless statistically | Add sample size caveat |
| "corrected algorithm achieves GREEN" | Achieves GREEN by being mostly dead (score=0) | Remove this claim |

---

## Statistical Power Summary

| Finding | N | Required N | Power | Verdict |
|---------|---|-----------|-------|---------|
| Laundering noise rate | 147 events | — | High | ✅ Solid |
| Campaign tier distribution | 37 campaigns | — | High | ✅ Solid |
| Fisher discriminant | 30 (6 hostile) | 33 hostile for p<0.01 | LOW | ⚠️ Insufficient |
| Narrative velocity | 8 narratives | 30+ for any threshold | VERY LOW | ⚠️ Meaningless |
| Hawkes BR difference | 281 clusters | — | Moderate | ✅ Directional |
| Embedding quality | 6 languages | — | Moderate | ✅ Usable |
| Fabrication stability | 10×3 runs | — | Moderate | ✅ Consistent |
| AIS regime analysis | 18 days, 7 regimes | 30+ days stable | LOW | ⚠️ Directional |
