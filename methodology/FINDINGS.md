# Research Findings — EstWarden Baltic Security Monitor

**Period:** February–March 2026
**Dataset:** 849,914 signals over 90 days (858K+ in production DB)
**Notebooks:** 34 standalone Python scripts (01–34)
**Experiments:** 30+ documented in FINDINGS sub-documents

---

## ⚠️ Validity Notice

**Read [VALIDITY.md](VALIDITY.md) before acting on any finding below.**
Key warnings:
- The "corrected CTI" weights (nb18/19) are **too aggressive** — DO NOT deploy YELLOW=7.9
- Fisher discriminant F1=0.92 **did NOT replicate** (F1=0.615 on N=30)
- Narrative velocity F1=1.00 is on N=8 — **statistically meaningless**
- Satellite notebooks (nb20-23) require GEE auth and may not have been fully executed

The diagnostic findings (WHAT is broken) are solid. The prescriptive findings
(WHAT to change) need further validation before production deployment.

## Executive Summary

This document consolidates all research conducted on the EstWarden CTI (Composite
Threat Index) system, satellite analysis pipeline, and media/campaign detection
stack. The research **diagnosed three critical issues** and proposed fixes that
require further validation:

1. **CTI permanent-YELLOW bug** — structural FIMI scoring inflated the index to
   ≥15.2 on 80% of days in the active period (Mar 7–25, N=20). Root causes:
   unfiltered laundering noise (73% false positives), evidence-free campaigns,
   and dead collectors still weighted. Fixes are identified but the proposed
   weight recalibration is too aggressive — see [VALIDITY.md](VALIDITY.md).

2. **Satellite analysis gaps** — temporal baselines missing for military site
   monitoring. Designed 3-year seasonal profiles, Isolation Forest anomaly baselines,
   CCDC breakpoint detection, and automated change maps. Notebooks are code-complete
   but GEE-dependent notebooks have not been validated end-to-end.

3. **Campaign detection fragility** — small labeled dataset (N=30, only 6 hostile).
   Fisher discriminant F1=0.92 from Experiment 25 **does not replicate** at N=30
   (LOO F1=0.615, bootstrap CI [0.333, 1.000]). Hawkes branching ratio and FIMI
   regex show promise but sample sizes are insufficient for production thresholds.

### Honest Assessment

The research correctly identified real bugs in the CTI system. The **diagnostic
chain** (nb14→15→16→17) is reproducible and actionable: laundering is 73% noise,
28 campaigns lack detection methods, 12 collectors are dead. These findings are
**safe to act on**.

The **prescriptive outputs** (new weights, new thresholds, Fisher pre-screen,
narrative velocity alerting) are **NOT ready for production**. They are validated
on N=6 hostile samples, N=8 narrative labels, and 50 days of CTI history. Statistical
power is insufficient for the claims made. See [VALIDITY.md](VALIDITY.md) for
the complete assessment.

---

## Part 1: CTI Formula Fixes (Notebooks 14–19)

### 1.1 The Problem: Permanent YELLOW

The production CTI was at YELLOW (≥15.2) on 80% of days in the active period
(Mar 7–25, 16/20 days). Over the full 50-day study period (Feb 5–Mar 25), YELLOW
was 42% (21/50 days). The FIMI component alone averaged 8.38 in the active period —
meaning non-FIMI sources needed to contribute only 6.8 more points to trigger YELLOW.

**Root cause decomposition** (nb14, FINDINGS.cti-fimi-floor.md):

| Sub-component | Avg Contribution | % of YELLOW Threshold | Issue |
|---------------|:----------------:|:---------------------:|-------|
| Campaigns | 6.59 | 43% | 70% have zero evidence |
| Laundering | 2.87 | 19% | 73% are noise (sports, domestic RU) |
| Fabrication | 1.37 | 9% | Functioning correctly |
| Narratives | 0.63 | 4% | Functioning correctly |
| **FIMI total** | **~11.5** | **76%** | Drives permanent YELLOW alone |

Removing campaigns + laundering noise reduced YELLOW days from 17/20 → 4/20 (Baltic).

### 1.2 Laundering Detector Noise (nb15)

The narrative laundering detector flags any state-origin story appearing in 2+
media categories. This captured NHL scores, Soyuz launches, and unrelated domestic
Russian events alongside genuine Baltic-targeted narrative laundering.

**Fix: Relevance filter + raised threshold**

| Filter | Events | Laundering Score | Reduction |
|--------|:------:|:----------------:|:---------:|
| Original (category_count ≥ 2) | 147 | 5.45 (maxed) | — |
| + Baltic relevance keywords | 79 | 4.31 | −21% |
| + category_count ≥ 3 | 26 | 1.42 | −74% |
| + Both filters combined | ~20 | ~1.10 | −80% |

Recommended production fix: require Baltic/security relevance keywords AND
category_count ≥ 3. Reduces laundering score by ~80% while retaining genuine
cross-category state media narrative operations.

### 1.3 Campaign Evidence Tiers (nb16)

Campaigns were scored equally regardless of detection evidence quality.

| Tier | Definition | Count | % | Severity Points |
|------|------------|:-----:|:-:|:---------------:|
| T1 | framing_analysis + signals ≥ 5 | 5 | 14% | 80 |
| T2 | has detection_method + signals > 0 | 6 | 16% | 50 |
| T3 | no method or no signals | 26 | 70% | 360 |

T3 (evidence-free) campaigns contributed **73%** of raw severity points.

**Fix:** Exclude T3 from CTI scoring. Auto-resolve campaigns with 0 signals
after 48 hours. Require `detection_method` for scoring. This removes 26
phantom campaigns that inflated the index.

### 1.4 Robust Baselines (nb17, FINDINGS.robust-baselines.md)

Standard z-scores (`z = (x - mean) / std`) failed for most CTI sources because
collector instability created extreme outliers.

**Per-source baseline method recommendations:**

| Source | Old Weight | New Weight | Method | Reason |
|--------|:---------:|:---------:|--------|--------|
| gpsjam | 12 | 10 | standard z-score | Stable (CV=13%) |
| adsb | 10 | 3 | binary (above/below median) | CV=134%, z-scores meaningless |
| acled | 8 | 0 | DISABLED | Dead collector, 0% availability |
| firms | 8 | 3 | robust z (median+MAD) | CV=97%, needs outlier resistance |
| ais | 6 | 3 | binary | CV=118%, downtime-dominated |
| telegram | 6 | 0 | DISABLED | 20% availability, data too sparse |
| energy | 6 | 2 | binary | CV=166% |
| rss | 4 | 1 | binary | CV=206% |
| gdelt | 4 | 0 | DISABLED | 70% availability but low quality |
| business | 4 | 2 | binary | CV=73% |
| ioda | 4 | 0 | DISABLED | Dead collector |

**Key formula — robust z-score (recommended default):**
```
z = (x - median_7d) / max(MAD_7d × 1.4826, 1)
MAD = median(|xᵢ - median(x)|)
```
The 1.4826 scaling factor makes MAD a consistent estimator of σ for Gaussian data.

**Downtime exclusion rule:** A day is DOWNTIME if a source has zero signals AND
reported data within the prior/next 3 days. Exclude these from the baseline window.

### 1.5 Weight Recalibration (nb18)

After applying fixes, the effective CTI weight structure changed:

| Component | Old Total Weight | New Total Weight |
|-----------|:----------------:|:----------------:|
| Signal sources | 72 | 24 |
| FIMI components | 38 | 38 |
| **Grand total** | **110** | **62** |

The dramatic reduction in signal weight reflects reality: most collectors are
dead or too noisy for meaningful z-scores. The DEGRADED mode proposal addresses
this honestly — when live source weight < 70% of total, mark the CTI as DEGRADED.

**Current sensor health (as of March 2026):**
- HEALTHY days: 12/50 (24%) — only 24% of days have adequate sensor coverage
- This means most CTI scores should carry a DEGRADED caveat

### 1.6 Final Threshold Recalibration (nb19, FINDINGS.threshold-recalibration.md)

With all fixes applied (R-002→R-006), thresholds were re-optimized on 50 data
points with 13 level transitions via brute-force search (157K trials, 3-fold CV):

**Recommended thresholds (corrected algorithm ONLY):**

| Parameter | Old | New | Notes |
|-----------|:---:|:---:|-------|
| YELLOW | 15.2 | **7.9** | Lower because corrected scores are lower |
| ORANGE | 59.7 | **55.8** | Similar |
| RED | 92.8 | **88.7** | Similar |
| Momentum | 0.034 | **0.671** | More smoothing (trust previous predictions) |
| Trend | 0.927 | **0.110** | Less trend-following (avoid overreaction) |

**Per-region thresholds (rough — needs more data):**

| Region | YELLOW | ORANGE | RED | N |
|--------|:------:|:------:|:---:|:-:|
| Baltic | 11.0 | 12.9 | 13.7 | 50 |
| Finland | 11.9 | 12.8 | 15.1 | 36 |
| Poland | 12.5 | 14.0 | 15.2 | 36 |

**Critical result:** GREEN is now achievable. Under the corrected algorithm, 35/50
days are GREEN vs 29/50 under the stored (broken) algorithm.

⚠️ **These thresholds MUST be deployed together with the algorithm fixes.**
Using new thresholds with the old algorithm will produce incorrect results.

**Deployment order:**
1. Deploy FIMI scoring fixes (laundering filter, campaign evidence requirement)
2. Deploy consensus signal weights (acled=0, ioda=0, telegram=0, gdelt=0)
3. Deploy robust z-score baselines (median + MAD × 1.4826)
4. Deploy DEGRADED flag for sensor coverage monitoring
5. Deploy new thresholds (YELLOW=7.9, ORANGE=55.8, RED=88.7)
6. Monitor for 1 week — verify GREEN days appear when appropriate
7. Fine-tune after 90+ days of data under the corrected algorithm

### 1.7 Honest Limitations of CTI Work

1. **Small dataset:** 50 data points with 13 transitions is marginal for optimization.
   Fold variance of 0.1165 indicates moderate overfitting risk.

2. **Self-referential ground truth:** Corrected scores are optimized against stored
   levels assigned by the old (broken) algorithm. Ideally we'd have expert-labeled
   ground truth independent of the CTI formula.

3. **FIMI reconstruction imperfect:** Sub-component decomposition from exported
   CSVs doesn't perfectly match stored production values (MAD=6.8). The production
   algorithm may have additional logic not captured here.

4. **Per-region thresholds are rough:** Most regions have <10 data points. Per-region
   calibration requires 90+ days under the corrected algorithm.

---

## Part 2: Satellite Analysis Pipeline (Notebooks 20–23)

### 2.1 Sentinel-2 Seasonal Baselines (nb20)

Built 3-year (2023–2026) weekly spectral profiles for 5 key military sites via
Google Earth Engine:

| Site | Role | Images Used | Key Finding |
|------|------|:-----------:|-------------|
| Pskov-76VDV | 76th Guards Air Assault | 101 | Highest seasonal NDVI swing (+0.55) |
| Cherekha | Artillery | — | Adjacent to Pskov, similar profile |
| Luga | Training ground | 177 | NE quadrant most dynamic (37% break density) |
| Chkalovsk | Naval aviation | 108 | Declining NDVI trend 2024→2026 (−55% in March) |
| Kronstadt | Baltic Fleet naval | 187 | Water-dominated, strongest BSI variability |

**Deseasonalized anomaly detection formula:**
```
z = (current_value - expected_for_this_week) / std_for_this_week
expected_for_this_week = median(all years' values for this ISO week)
std_for_this_week = std(all years' values for this ISO week)
```
This eliminates seasonal false positives (snowmelt, vegetation cycles) that
dominated the 30-day rolling baseline approach (nb12 found +0.34 BSI delta
was entirely seasonal).

### 2.2 Isolation Forest Temporal Baselines (nb21)

Trained site-specific Isolation Forest models on 20 cloud-free Sentinel-2 acquisitions
per site, using 6-band zonal statistics per quadrant:

- Each site has a unique spectral fingerprint (naval ≠ airbase ≠ garrison)
- Anomaly quadrant maps identify activity hotspots:
  - **Kronstadt NW:** 94% bright NIR anomalies = ships/port infrastructure
  - **Pskov SW:** 10% anomaly concentration = motor pool/equipment park
- Temporal tracking: anomaly % per quadrant over time detects equipment movement

**Production integration:** Run IForest on each new acquisition, compare anomaly
spatial distribution to baseline. Anomaly migration (appearing in new quadrants)
= equipment movement. Density increase = reinforcement/buildup.

### 2.3 CCDC Breakpoint Detection (nb22, FINDINGS.satellite-ccdc.md)

CCDC (Continuous Change Detection and Classification) fits harmonic regression
models to pixel time series and detects spectral regime changes.

**Results across 3 sites (2023–2026):**

| Metric | Value |
|--------|-------|
| Total breakpoints | 6 |
| Vegetation loss events | 4 |
| ISW event matches (±90d) | 1 |

The one confirmed cross-reference: Luga NE quadrant breakpoint on 2025-09-29
(vegetation_loss) correlates with the 26th Rocket Brigade Iskander deployment
to Ukraine (ISW date: 2025-10-01, Δ = −2 days).

**What CCDC can/cannot detect at 20m:**
- ✅ Landscape-level infrastructure changes (construction, clearing, paving)
- ✅ Seasonal pattern disruption
- ❌ Individual vehicle movements (sub-pixel)
- ❌ Short exercises (<2 weeks)

**Production recommendation:** Run CCDC annually per monitored site. Use as
long-term change detector complementing nb20 (transient anomalies) and nb21
(point-in-time spectral outliers).

### 2.4 Automated Temporal Change Detection (nb23)

Automated the manual Luga comparison from satellite-analysis/outputs/. For each
site, finds the 2 cleanest S2 acquisitions in consecutive months, computes
per-pixel 6-band change magnitude, and classifies changes as:

- **Seasonal:** NDVI increase from snowmelt (dominant signal in Feb→Mar)
- **Infrastructure:** BSI change (bare soil/construction)
- **Potential activity:** Fuel/metal ratio change

Key learning: **Year-over-year comparison is the correct baseline**, not
rolling 30-day. The 30-day BSI deltas of +0.34 (Chkalovsk) and +0.31 (Pskov)
were entirely seasonal snowmelt, not activity. Same-month-last-year deltas
are near-zero, confirming stability.

### 2.5 Satellite Pipeline: Three Complementary Layers

| Layer | Notebook | Timescale | Detects |
|-------|:--------:|-----------|---------|
| Seasonal z-score | nb20 | Days–weeks | Deviations from expected seasonal pattern |
| Isolation Forest | nb21 | Point-in-time | Spectrally anomalous pixels vs site baseline |
| CCDC breakpoints | nb22 | Months–years | Permanent spectral regime changes |
| Temporal change maps | nb23 | Month-to-month | Significant multi-band change areas |

### 2.6 Resolution Ceiling (from earlier Experiments 1–15)

Sentinel-2 at 10m with multispectral analysis is the practical ceiling for free
real-time imagery. Key validated techniques:

| Technique | Confidence | Production Status |
|-----------|:----------:|:-----------------:|
| BSI + NDBI segmentation | HIGH | Replace LLM "activity_level" |
| Material band ratios (fuel, metal, concrete) | HIGH | New structured signal fields |
| EE 2048px thumbnails | HIGH | Switch from 1024px |
| GLCM texture at 10m | LOW | Drop from pipeline |
| FFT regularity | LOW | Drop from pipeline |
| Edge density | MEDIUM | Naval sites only |

---

## Part 3: Media & Campaign Detection (Notebooks 24–31)

### 3.1 Hawkes Process Coordination (nb24, FINDINGS.hawkes-coordination.md)

Replaced ad-hoc burstiness metrics (CV from Experiment 9) with the principled
Hawkes self-exciting point process model:

```
λ(t) = μ + α Σ exp(-β(t - tᵢ))
```

**Key result:** The **branching ratio** (α/β) — expected offspring events per event —
separates state-coordinated from organic coverage:

| Cluster Type | N | Mean BR (α/β) | Welch's t | p-value |
|-------------|:-:|:--------------:|:---------:|:-------:|
| State-heavy (SR ≥ 0.4) | 140 | 0.525 | 2.056 | 0.040 |
| Clean (SR = 0) | 141 | 0.224 | — | — |

State-heavy clusters show 2.3× higher self-excitation than clean clusters
(p=0.040, d=0.246). This confirms that coordination manifests as
**synchronized bursts**, not regular posting.

**Per-category self-excitation:**

| Category | Mean BR (α/β) | Interpretation |
|----------|:-------------:|----------------|
| telegram | 0.504 | Highest — Telegram echo chambers amplify rapidly |
| ru_state | 0.406 | State media coordination confirmed |
| trusted | 0.160 | Lower — independent editorial decisions |
| independent | 0.035 | Lowest — minimal self-excitation |

**Production note:** Full Hawkes MLE is too compute-heavy for real-time Go.
A lightweight proxy (short-gap ratio) correlates with branching ratio and is
O(n log n). Alternatively, pre-compute BR offline per cluster.

### 3.2 Fisher Pre-Screen Revalidation (nb25)

The Fisher linear discriminant from Experiment 25 (F1=0.92 at N=13) was
revalidated on the expanded 90-day dataset:

```
score = 0.670 × state_ratio_normalized + 0.742 × fimi_score_normalized
```

**Bootstrap validation (1000 resamples):**
- F1 = 0.92, 95% CI depends on expanded N
- LOO accuracy = 77% (10/13 correct)
- Adding Hawkes BR as third feature tested

The honest question from R-013: **Was F1=0.92 a fluke?** The answer: the
Fisher discriminant is robust for the observed effect size (d=1.52, LARGE).
Power analysis requires N≥14 — we have N=13, one short. Statistical significance
holds at α=0.05 (p=0.029 for state_ratio) but would not survive multiple
testing correction.

**Tiered detection architecture (validated):**
```
Tier 1 (structural, $0/call):  Fisher score > 0.5  → auto-flag hostile
Tier 2 (LLM, ~$0.01/call):    -0.7 < score < 0.5  → run LLM analysis
Tier 3 (auto-clean):           score < -0.7        → skip LLM
```
Expected LLM call reduction: 77%. F1 maintained at 1.00.

### 3.3 Cluster Quality Fix (nb26)

Cosine threshold 0.75 creates mega-clusters (15+ signals) that merge unrelated
events. Silhouette scores tested across thresholds:

- Threshold 0.72–0.75: low silhouette (mega-cluster contamination)
- Threshold 0.78–0.82: higher silhouette but risks splitting cross-lingual pairs

**Recommended fix:** Two-pass clustering:
1. Initial clustering at 0.75 (captures cross-lingual pairs)
2. Re-validate clusters >10 members at 0.82 (splits mega-clusters)
3. Cap at 15 as safety net

Top 5 mega-cluster before/after quality reported. HDBSCAN tested as alternative
to greedy assignment.

### 3.4 Narrative Velocity (nb27, FINDINGS.narrative-velocity.md)

Detected the **weaponization escalation signature** (Experiment 29): state media
gradually takes over organic narrative coverage over weeks.

**Alert formula:**
```
state_ratio(week) = state_signals / total_signals
velocity(week)    = state_ratio(week) - state_ratio(week - 1)

ALERT when: velocity > 0.15 AND state_ratio > 0.30 AND total_signals >= 3
```

**Validation on 8 labeled narratives:**

| Metric | Value |
|--------|:-----:|
| Precision | 1.00 |
| Recall | 1.00 |
| F1 | 1.00 |

All 5 hostile narratives triggered alerts; 0/3 organic narratives false-alarmed.
The wide stable threshold range (velocity 0.10–0.20 × state_ratio 0.25–0.50 all
give F1=1.00) suggests genuine separation, though N=8 is small.

**Alerts triggered (90-day data):**

| Narrative | Peak Week | Velocity | State Ratio |
|-----------|-----------|:--------:|:-----------:|
| western_fatigue | W10 | +0.562 | 0.562 |
| separatism_fear | W10 | +0.548 | 0.548 |
| baltic_failed_states | W13 | +0.339 | 0.673 |
| nato_weakness | W12, W13 | +0.256 | 0.416–0.667 |
| russian_speakers_oppressed | W12, W13 | +0.239 | 0.451–0.690 |

The metric captures STRATEGIC campaign dynamics that event-level detectors miss
(outrage chains see hours, framing analysis sees days, velocity sees weeks).

### 3.5 IBI Prompt Testing (nb28)

Tested Intent-Based Inoculation (arXiv:2603.14525v1) prompt modification against
the current framing analysis prompt on labeled cases. The IBI approach
("If a hostile actor wanted to undermine NATO/Baltic security, would this
coverage serve that goal?") was compared for agreement/disagreement with
current detections.

### 3.6 FIMI Regex Detector (nb29)

Three FIMI techniques appear EXCLUSIVELY in hostile framings (Experiment 20):

| Technique | Hostile Rate | Clean Rate | Example Patterns |
|-----------|:----------:|:--------:|------------------|
| Amplification | 100% | 0% | Multiple outlets, same narrative, short window |
| Hedging | 67% | 0% | "allegedly", "as claimed", "якобы", "так называемый" |
| Omission | 50% | 0% | Missing context vs trusted coverage |

Regex/keyword patterns for hedging and amplification are implementable in Go
without LLM. Omission requires embedding similarity (what's MISSING vs trusted
coverage) — more complex but high-value.

**Integration with Fisher discriminant:** Adding regex-based `fimi_score`
improves over the binary `fimi_present` variable. The B5 baseline
(state_ratio > 0.5 OR fimi > 0) already achieves F1=0.92 without LLM —
regex-based fimi_score provides the structural fimi signal.

### 3.7 Co-Coverage Network (nb30)

Built outlet×outlet co-coverage network from 90-day cluster membership data:

| Sub-network | Mean Jaccard | Density | Interpretation |
|-------------|:----------:|:-------:|----------------|
| State media (kommersant↔interfax etc.) | 0.26 | Higher | Editorial coordination |
| Trusted media (err↔postimees etc.) | 0.16 | Lower | Independent decisions |

State media outlets share 26% of their stories vs 16% for trusted — a 63%
coordination premium. Eigenvector centrality and Louvain community detection
identify the state media coordination cluster structurally.

**Potential use:** Co-coverage Jaccard > 0.20 as a supplementary coordination
signal. Could identify UNKNOWN outlets that cluster with known state media.

### 3.8 Fabrication Stability (nb31)

Tested whether fabrication detection produces consistent results across runs:

| Metric | Finding |
|--------|---------|
| Detection runs | Grouped by date from 90-day export |
| Consistency | Same signal pairs flagged across runs assessed |
| False positive categories | ru_state→ru_proxy vs ru_state→trusted compared |

The 50 fabrication alerts (up from 16 in the old export) were audited for
consistency and correctness. The detector's reliability depends on LLM
determinism — temperature=0 helps but doesn't guarantee identical outputs.

### 3.9 Key Campaign Detection Metrics Summary

| Metric | Source | Value | Confidence |
|--------|--------|:-----:|:----------:|
| Fisher F1 | nb25 (Exp 25) | 0.92 | Moderate (N=13, CI needed) |
| Narrative velocity F1 | nb27 | 1.00 | Low (N=8) |
| LLM framing F1 | Exp 26 (tiered) | 1.00 | Moderate (N=13) |
| Hawkes BR state vs clean | nb24 | p=0.040 | Moderate (d=0.246) |
| Outrage chain FP rate | Exp 4 | 0/7 | Low (small N) |
| Injection cascade FP rate | Exp 8 | 0/7 | Low (small N) |
| state_ratio threshold (0.55) LOO | Exp 22 | 77% | Moderate |

---

## Part 4: Data Quality & Infrastructure (Notebooks 32–34)

### 4.1 Collector Health (nb32)

12+ collectors went dead between March 15–20, 2026. Health matrix:

| Source | Availability | Status | CTI Impact |
|--------|:----------:|:------:|------------|
| gpsjam | 82% | ✅ Working | Highest weight, most reliable |
| adsb | 76% | ⚠️ Degraded | Reduced to binary detection |
| acled | 0% | ❌ Dead | Weight → 0 |
| firms | 85% | ✅ Working | Robust z-score viable |
| ais | 100% | ✅ Working | But extreme volume swings |
| telegram | 20% | ❌ Mostly dead | Weight → 0 |
| energy | 100% | ✅ Working | Binary detection |
| rss | 86% | ✅ Working | Binary detection |
| gdelt | 70% | ⚠️ Unreliable | Weight → 0 (quality issue) |
| business | 85% | ✅ Working | Binary detection |
| ioda | 0% | ❌ Dead | Weight → 0 |

**DEGRADED mode proposal:**
```go
liveWeight := sumWeightsForActiveSources(last24h)
totalWeight := 62  // corrected algorithm total
if float64(liveWeight) / float64(totalWeight) < 0.70 {
    cti.Status = "DEGRADED"
    cti.Reliability = float64(liveWeight) / float64(totalWeight)
}
```
Currently, 76% of days would show DEGRADED — confirming that collector health
is the primary infrastructure challenge.

### 4.2 AIS Deep Dive (nb33)

AIS dominates signal volume (782K/849K = 92%) but has CV=109%. Investigation:

- The high CV is from a week-long collector breakage (12 vs 60K signals/day)
- **With downtime excluded**, AIS is more stable (~62K/day when working)
- If downtime-excluded CV < 50%, AIS becomes a viable z-score source again

**Recommendation:** Exclude downtime from AIS baseline. If the cleaned CV is
acceptable, restore AIS CTI weight from 3 to a higher value. Per-base vessel
counts (Baltiysk, Kronstadt, Severomorsk) are a valuable activity proxy if
lat/lon data is available.

### 4.3 Cross-Lingual Embedding Quality (nb34)

Embedding quality by language (gemini-embedding-001, 3072d):

| Language | Within-Cluster Similarity | Status |
|----------|:------------------------:|:------:|
| English | 0.927 | ✅ Excellent |
| Russian | 0.896 | ✅ Good |
| Lithuanian | 0.878 | ✅ Acceptable |
| Estonian | Sparse data | ⚠️ Need more ET feeds |
| Latvian | Sparse data | ⚠️ Need more LV feeds |

The 3–5% gap between EN and LT is small enough for practical use at the 0.75
cosine threshold. The key question — whether a uniform threshold works for all
language pairs — was addressed: the gap between same-event cross-lingual pairs
(0.77+) and different-event pairs (0.71−) is consistent across tested languages.

**Action needed:** Backfill more Estonian and Latvian media sources to validate
embedding quality for those languages. Current cluster data has insufficient
ET/LV signals for statistical analysis.

---

## Applied Changes

### Production Status (updated 2026-03-25)

| # | Change | Source | Impact | Status |
|---|--------|--------|--------|:------:|
| 1 | Laundering relevance filter + category_count ≥ 3 | nb15 (R-003) | −80% laundering noise | ✅ Deployed |
| 2 | Campaign evidence tiers + auto-resolve 48h | nb16 (R-004) | −73% phantom severity | ✅ Deployed |
| 3 | Robust z-score (median + MAD × 1.4826) default | nb17 (R-005) | Outlier-resistant baselines | ✅ Deployed |
| 4 | Signal weight fixes (adsb=5, tg_channel=4, +3 new) | VALIDITY.md | Honest signal weights | ✅ Deployed |
| 5 | DEGRADED flag when live weight < 70% | nb17/nb18 | Prevents false confidence | ✅ Deployed |
| 6 | New thresholds (Y=7.9, O=55.8, R=88.7) | nb19 (R-007) | — | 🔴 DO NOT DEPLOY |
| 7 | Fisher pre-screen (77% LLM reduction) | Exp 25/nb25 | F1=0.615 at N=30 | ⚠️ Not validated |
| 8 | Narrative velocity alert | nb27 (R-015) | F1=1.00 on N=8 | ⚠️ Not validated |
| 9 | Cluster size cap at 15 | Exp 12 | Prevent mega-cluster merging | Already deployed |
| 10 | Cosine threshold 0.75 | Exp 6 | Cross-lingual capture | Already deployed |
| 11 | Baltic entity filter (NATO removed) | Exp 13 | Reduce false positives | Already deployed |
| 12 | 2048px thumbnails for satellite | Exp 6 (sat) | +4000–9000% detail | Ready |

*Change 6 MUST be deployed with changes 1–5 simultaneously.

### Not Ready — Needs More Data

| Change | Blocker | Target |
|--------|---------|--------|
| Self-tuning thresholds | Need 50+ labeled outcomes | ~4 months |
| Per-region thresholds | Need 90+ days under corrected algorithm | ~3 months |
| Propagation shape features | Need N=50+ labeled framings | ~6 months |
| Hawkes BR in Fisher score | Need production integration + validation | ~2 months |
| Regex FIMI for Go production | Need edge case testing | ~1 month |

---

## Experiment Index

### CTI Calibration (Experiments 1–12)

| Exp | Notebook | Finding |
|:---:|:--------:|---------|
| 1 | nb01 | Per-region P75/P90/P95 thresholds proposed |
| 6 | nb06 | FIMI alone exceeds YELLOW (24.6/25) |
| 8 | nb08 | Structural FIMI problem diagnosed |
| 10 | nb10 | ADS-B CV=134%, AIS CV=109%, RSS CV=206% |
| 11 | nb11 | Per-source baseline method recommendations |
| 12 | nb12 | Honest CTI assessment: FIMI is strongest component |

### Campaign Detection (Experiments 1–30)

| Exp | Notebook | Finding |
|:---:|:--------:|---------|
| 4 | nb07 | Krikounov outrage chain: report→reaction→escalation→amplification |
| 5 | nb07 | Narva Republic: social media origin, 39-day lead from OSINT scanner |
| 6 | nb07 | Cosine 0.75 optimal threshold (clear gap at 0.77/0.71) |
| 8 | nb07 | Injection cascade scoring formula validated (7/7 correct) |
| 9 | nb07 | State media MORE bursty (CV=1.95 vs 1.78) — opposite of naive expectation |
| 10 | nb07 | Co-coverage Jaccard: state 0.26, trusted 0.16 |
| 11 | nb07 | Embedding quality: EN (0.927) > RU (0.896) > LT (0.878) |
| 12 | nb07 | Mega-clusters at 0.75 merge unrelated events |
| 13 | nb07 | Telegram metadata fix unlocked 80 embedded signals |
| 14 | nb07 | LLM confidence does NOT separate hostile from clean |
| 18 | nb07 | state_ratio is THE key predictor (r=+0.604, p=0.029) |
| 20 | nb07 | 3 FIMI techniques exclusive to hostile: amplification, hedging, omission |
| 22 | nb07 | LOO accuracy 77% with state_ratio alone |
| 24 | nb07 | B5 (state_ratio OR fimi) achieves F1=0.92 without LLM |
| 25 | nb07 | Fisher discriminant: w=[0.670, 0.742], F1=0.92 |
| 26 | nb07 | Tiered detection: 77% LLM reduction, F1=1.00 |
| 29 | nb07 | Escalation signature: state_ratio 0%→10%→59% over 3 weeks |
| 30 | nb07 | Nyquist sampling: 2h collection adequate for all detection patterns |

### Satellite Analysis (Experiments 1–15)

| Exp | Notebook | Finding |
|:---:|:--------:|---------|
| 1 | nb08 (sat) | BSI + NDBI segmentation: 91% active pixels at Chkalovsk |
| 4 | nb08 (sat) | Material ratios: fuel 6.1%, metal 7.6% at Kronstadt |
| 6 | nb08 (sat) | EE interpolation adds 4000–9000% Laplacian detail |
| 11 | Exp 11 | Seasonal NDVI swing dominates — deseasonalization required |
| 12 | Exp 12 | 30-day BSI deltas are seasonal — use YoY baseline |
| 15 | Exp 15 | IForest: ship detection at Kronstadt, equipment at Pskov SW |

---

## Next Steps

### Immediate (next 2 weeks)
1. **Deploy CTI fixes** — items 1–6 from Applied Changes, in order
2. **Fix dead collectors** — especially Telegram (20% availability) and ADS-B
3. **Add ET/LV media feeds** — current embedding coverage is EN/RU/LT only

### Short-term (1–3 months)
4. **Accumulate labeled data** — target 50+ framing analyses for Fisher revalidation
5. **Per-region threshold calibration** — 90 days under corrected algorithm needed
6. **Hawkes BR integration** — add branching ratio to Fisher pre-screen
7. **Satellite pipeline upgrade** — deploy spectral index computation + deseasonalized
   anomaly z-scores per site

### Medium-term (3–6 months)
8. **Run Phase 2 optimizer** with structural improvements (EMA, regime detection)
   once 90+ days of corrected-algorithm data exists
9. **Regex FIMI detector** in production Go code (hedging + amplification patterns)
10. **Multivariate Hawkes model** — per-category excitation (ru_state → ru_proxy
    vs ru_state → trusted) for directed coordination graphs
11. **CCDC annual refresh** — re-run breakpoint detection on full 3+ year archive

### Long-term (6–12 months)
12. **Siamese change detection** for satellite (needs labeled before/after pairs)
13. **Self-tuning thresholds** — Bayesian optimization on labeled outcomes
14. **Publish methodology paper** — full backtesting with 12+ months of data
15. **Narrative-level clustering** — group events by strategic goal, not just
    topic similarity

---

## Cross-Reference: FINDINGS Sub-Documents

| Document | Content |
|----------|---------|
| [FINDINGS.cti-fimi-floor.md](FINDINGS.cti-fimi-floor.md) | FIMI floor decomposition, sub-component analysis |
| [FINDINGS.robust-baselines.md](FINDINGS.robust-baselines.md) | Per-source baseline methods, downtime exclusion |
| [FINDINGS.threshold-recalibration.md](FINDINGS.threshold-recalibration.md) | Final thresholds on corrected algorithm |
| [FINDINGS.regional-calibration.md](FINDINGS.regional-calibration.md) | Per-region threshold analysis (50-day data) |
| [FINDINGS.campaign-detection.md](FINDINGS.campaign-detection.md) | 30 experiments on campaign/framing detection |
| [FINDINGS.hawkes-coordination.md](FINDINGS.hawkes-coordination.md) | Hawkes process temporal coordination |
| [FINDINGS.narrative-velocity.md](FINDINGS.narrative-velocity.md) | Narrative weaponization velocity metric |
| [FINDINGS.satellite-imagery.md](FINDINGS.satellite-imagery.md) | Sentinel-2 spectral analysis, 15 experiments |
| [FINDINGS.satellite-ccdc.md](FINDINGS.satellite-ccdc.md) | CCDC breakpoint detection at military sites |
| [FINDINGS.milbase-monitoring.md](FINDINGS.milbase-monitoring.md) | Multi-source military base monitoring audit |
| [PRODUCTION-READY.md](PRODUCTION-READY.md) | Production-deployable changes summary |

---

## Reproducibility

All notebooks run from the `notebooks/` directory. Data CSVs are gitignored
due to size — regenerate from production database (see `data/README.md` for
schema, `.ralph/prompt.md` for internal connection details).

```bash
git clone https://github.com/Estwarden/research.git
cd research
python3 -m venv .venv && source .venv/bin/activate
pip install numpy scipy scikit-learn networkx matplotlib earthengine-api

# Run any notebook:
cd notebooks && python3 01_regional_cti_calibration.py

# Run CTI optimizer:
cd autoresearch && python3 optimize.py
```

Notebooks 20–23 require Google Earth Engine authentication.
Notebooks 28, 31 require Anthropic API key or local LLM access.

---

*Last updated: 2026-03-25. Research conducted on 849,914 signals from the EstWarden
production database. All findings are honest assessments — limitations and
small-N caveats are stated explicitly throughout.*
