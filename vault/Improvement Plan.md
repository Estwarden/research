---
status: evergreen
tags: [plan, improvements, deployment, priorities]
---

# Improvement Plan

What to improve in EstWarden, organized by what's deployable now vs what needs work. Based on analysis of all 43 notebooks, current data, production gaps, and the [multi-source GEOINT upgrade](https://blog.estwarden.eu/investigations/multi-source-geoint/) that shipped in production.

> **Note:** The satellite pipeline is now significantly ahead of the research — 7-source fusion, NDRE camouflage detection, EMCON correlation, dual-pol SAR, and alternative hypotheses are all in production but lack formal research validation. Phase 2 includes back-porting these for validation.

> The single most important insight: **90% of actionable improvements can deploy within 2 weeks using existing data.** The blocker is infrastructure, not research.

## Phase 0: Deploy This Week (zero blockers)

Research is done. These are validated findings sitting in notebooks, waiting for production deployment.

### 0.1 — Deploy Moderate Weights (nb35)

**What:** Replace the broken weight total (72 → 24, which kills the algorithm) with moderate weights (~45).

| Source | Old Weight | Broken (nb18) | Moderate (nb35) | Rationale |
|--------|-----------|----------------|-----------------|-----------|
| Reliable (low CV) | Original | Halved | Original | No reason to cut working sources |
| Moderate CV | Original | Halved | Halved | Reduce noise without killing |
| Dead/zero data | Original | Zeroed | Zeroed | Same — no data = no weight |
| **Total signal** | **72** | **24** | **~45** | Middle path |
| FIMI | 38 | 38 | 38 | Unchanged |
| **FIMI share** | **35%** | **61%** | **~46%** | Healthy balance |

**Why now:** The current nb18 consensus weights are deployed but broken — 30 of 50 days score near zero. Moderate weights fix algorithm liveness while keeping diagnostic improvements.

**Risk:** LOW. Strictly better than current deployed state.

**Effort:** 1 day. Update weight config in production.

### 0.2 — Deploy Fabrication Same-Event Gate (nb37)

**What:** Require n-gram title similarity ≥ 0.08 before fabrication scoring fires.

**Numbers from nb37:**
- Mean n-gram similarity across alerts: 0.0826
- 11 of 50 alerts are false positives (low similarity + high score)
- Gate eliminates **67% of fabrication CTI noise**
- Combined with existing relevance filter: 79% total noise reduction

**Why now:** Fabrication alerts fire on unrelated signal pairs (different events that happen to co-occur). The same-event gate is a simple regex check that eliminates garbage.

**Risk:** LOW. Only suppresses alerts where root and downstream signals aren't about the same event.

**Effort:** 1 day. Add n-gram similarity check before `fabrication_score` computation.

### 0.3 — Deploy PLMSE Metric (nb36)

**What:** Add Power Law MSE as a zero-cost detection feature for every cluster.

**How it works:** Hostile cascades follow power-law temporal patterns (few early signals, long tail of amplification). PLMSE measures how well the signal timing fits a power law.

**Numbers from nb36:**
- Computed for 1,271 clusters with 5+ signals
- Literature validation: p = 0.0001 (PLOS ONE, Jan 2025 — "Signals of Propaganda")
- Hostile clusters have lower PLMSE (better power-law fit) than organic clusters
- Pure math on existing `cluster_members.csv` temporal data — no ML, no training

**Why now:** Free information. Adds a scientifically validated feature to every cluster with zero ongoing cost.

**Risk:** LOW. Read-only metric, doesn't change scoring until explicitly used.

**Effort:** 1 day. Compute PLMSE per cluster, store as column.

### 0.4 — Expand Watchlist (F-02)

**What:** Add 11 channels identified in the Bild map gap analysis.

**The case:** Bild.de published a "Baltic invasion plan" map. The system missed it entirely because 8 of 10 amplifying channels weren't monitored. 40% watchlist coverage on a real campaign is unacceptable.

**Priority channels (from `../bild-map-watchlist-gap.md`):**

| Channel | Subscribers | Why |
|---------|-------------|-----|
| @smolii_ukraine | 392K | Key fabricator — added "1-2 months" timeline |
| @Tsaplienko | 336K | War correspondent, dramatic amplification |
| @portnikov | ~200K | Opinion leader, plants fear framework |
| @BerezaJuice | ~100K | YouTube clickbait crossposter |
| @channel5UA | ~50K | TV channel Telegram, fabricated "laws passed" |
| + 6 more | — | See bild-map-watchlist-gap.md |

**Why now:** Config-only change. YAML files are already specified in the analysis doc. No code changes.

**Risk:** LOW. More coverage = better detection.

**Effort:** < 1 day.

### 0.5 — Remove RU-Origin Gate from Velocity (nb41)

**What:** Current narrative velocity detection only flags clusters with Russian-origin signals. Remove this gate.

**Numbers from nb41:**
- Current (RU-gated) flags: 47 narratives
- Origin-agnostic flags: 89 narratives
- **42 additional narratives detected** that the current system misses
- The Bild map campaign (Ukrainian-origin) would have been caught

**Why now:** The algorithm is ready. The RU-origin gate was an early assumption that non-Russian sources don't coordinate — the Bild map case proved this wrong.

**Depends on:** 0.4 (watchlist expansion) — new channels need to be monitored for velocity to detect them.

**Risk:** MEDIUM. May increase false positives from non-hostile viral content. Monitor precision for 2 weeks.

**Effort:** 1 day. Change category filter in `narrative_velocity.go`.

---

## Phase 1: Fix Infrastructure (weeks 1–2)

Not research — ops work. But everything downstream depends on it.

### 1.1 — Fix Dead Collectors (F-01)

| Collector | Status | Fix |
|-----------|--------|-----|
| ACLED | Zero data | Restore API integration |
| IODA | Zero data | Restore API integration |
| Legacy Telegram | 20% uptime | Debug collector, merge with telegram_channel |
| Sentinel-2 | Dead since Mar 14 | Debug GEE auth / collector process |
| ADS-B | 76% misclassification | Fix ICAO hex → military callsign mapping |

**Impact:** 76% of days are DEGRADED. No weight/threshold calibration is meaningful until this is fixed.

**Effort:** 2–3 days ops.

### 1.2 — Fix Category Metadata (F-04)

**What:** 20K signals have empty `category` field. Backfill from `source_id` → `feed_handle` → `category` mapping.

**Impact:** Fisher pre-screen and narrative velocity depend on `state_ratio`, which requires `category`. Without it, detection silently degrades.

**Effort:** 1 day. DB query + backfill script.

### 1.3 — Add Baltic Media Feeds (F-03)

**What:** Add ERR.ee (Estonian), LSM.lv (Latvian), 15min.lt (Lithuanian) RSS feeds.

**Impact:** ET/LV embedding quality is too sparse to validate (< 50 clustered signals per language). Detection is English/Russian only.

**Effort:** 1 day. RSS collector config.

---

## Phase 2: Validate Detection (weeks 2–6)

These improvements require the labeled dataset (nb38) to be completed first.

### 2.1 — Complete Labeled Dataset (nb38) — CRITICAL PATH

**Current state:**
- 17 hostile clusters labeled (14 from framing analysis, 3 from campaign evidence)
- 11 clean clusters labeled
- Need: 33+ hostile for Fisher p < 0.01

**Fast path:** Cross-reference existing clusters against EUvsDisinfo case database. Their structured database has 1,000+ documented disinformation cases. Matching against our 2,278 clusters should yield 16+ additional hostile labels in 2–3 hours of manual work.

**Why critical:** Blocks nb40 (Fisher+Hawkes), nb43 (community structure), and all detection threshold calibration.

### 2.2 — Fisher + Hawkes Combined (nb40)

**What:** Add Hawkes branching ratio as third feature to Fisher discriminant.

- Current Fisher: `score = 0.670 * state_ratio + 0.742 * fimi_score` → F1 = 0.615
- Proposed: add `w₃ * hawkes_BR` → expected F1 improvement TBD
- Hawkes alone: BR = 0.53 (state) vs 0.22 (clean), p = 0.04

**Blocked on:** 2.1 (need 33+ hostile labels). Bootstrap CI methodology ready.

### 2.3 — Community Structure Validation (nb43)

**What:** Test whether propagation graph density discriminates hostile from organic clusters.

**Hypothesis (TIDE-MARK paper):** Fake news spreads through more cohesive communities (AUC = 0.83 in literature, no content analysis needed).

**Features computed in nb43:** density, clustering coefficient, degree distribution, component count, bridge count, max clique size.

**Blocked on:** 2.1 (need labeled dataset for training/evaluation).

### 2.4 — AIS Tiered Scoring (nb39)

**What:** Split AIS into defense-relevant (Tier 1: military zones, naval exercises) vs raw volume (Tier 2: commercial shipping).

**Numbers from nb39:**
- AIS CV = 117% — too noisy for single z-score
- 5 regime changes detected in 90 days
- Proposal: Tier 1 weight = 4, Tier 2 = conditional on anomaly

**Blocked on:** 1.1 (stable AIS collector for 2+ weeks).

---

## Phase 3: New Production Features (weeks 6–12)

Code changes that implement research findings not yet in production.

### 3.1 — Mutation Detection Endpoint

**What:** Detect when amplifying signals ADD fabricated claims not in the original source.

**Architecture (from `../fabrication-detection-design.md`):**

```
POST /api/v1/detect/mutations

For each cluster:
1. Identify root signal (earliest, usually state media)
2. Extract claims from root (regex: time refs, legal refs, certainty markers)
3. Compare claims in downstream signals
4. Flag ADDED claims: downstream has specifics not in root
   - "1-2 months" added by @smolii_ukraine (not in Bild original)
   - "laws passed" added by @channel5UA (fabricated entirely)
```

**Regex patterns needed:**
- Time references: `\d+[-–]\d+\s*(months?|weeks?|days?)`
- Legal claims: `(law|закон)\s*(passed|принят)`
- Certainty escalation: `(will attack|final stage|неизбежн)`

**Impact:** Would have detected Bild map fabrication within 12 hours.

### 3.2 — Cross-Category Velocity Detection

**What:** Alert when a cluster spreads across 3+ source categories in 48 hours.

**Current limitation:** `narrative_velocity.go` only counts `ru_state`/`ru_proxy`. Misses Ukrainian, Baltic, and Western amplification chains.

```sql
SELECT cluster_id,
       COUNT(DISTINCT category) as category_spread,
       SUM(views) as total_views
FROM cluster_signals cs
JOIN signals s ON cs.signal_id = s.id
WHERE s.published_at >= now() - interval '48 hours'
GROUP BY cluster_id
HAVING COUNT(DISTINCT category) >= 3
```

**Alert tiers:**
- 3 categories + > 500K views → MEDIUM
- 4+ categories + > 1M views → HIGH
- 5+ categories + > 5M views → CRITICAL

### 3.3 — FIRMS Per-Site Baseline

**What:** Anomaly detection on FIRMS thermal data per military site.

**Current state:** FIRMS is the only working satellite-adjacent source (1,005 signals in 14 days across 14 sites). But no per-site baseline exists.

**Numbers from milbase audit:**
- Pskov-76VDV: Mar 17 spike — 22 hotspots vs baseline 5.0 (z = 2.2)
- Rostov-Southern-HQ: Mar 14 spike — 30 hotspots vs baseline 12.0 (z = 1.4)

**Implementation:**
```python
for site in monitored_sites:
    baseline = median(firms_hotspots_30d[site])
    mad = median_abs_deviation(firms_hotspots_30d[site])
    z = (today - baseline) / mad
    if z > 2.0:
        alert(site, "ELEVATED", z_score=z)
```

### 3.4 — Hawkes BR in Production

**What:** Add branching ratio proxy to cluster features (O(n log n), no scipy needed).

**Go implementation approach:**

```go
// Compute inter-arrival gaps for cluster signals
gaps := computeGaps(sortedTimestamps)
medGap := median(gaps)
// Count rapid-fire signals (< 30% of median gap)
shortGaps := countBelow(gaps, medGap * 0.3)
brProxy := float64(shortGaps) / float64(len(gaps))
// brProxy > 0.4 → coordination signal
```

This proxy correlates with true Hawkes BR without requiring numerical optimization.

---

## Phase 4: Threshold Recalibration (week 12+)

Only possible after 90+ days of stable collector data under corrected weights.

### 4.1 — Weight Validation (R-35 continued)

After 90 days of Phase 0 moderate weights + Phase 1 collector fixes:
- Compute CTI distribution under new regime
- Validate FIMI share stays at ~46%
- Confirm DEGRADED days < 30% (down from 76%)

### 4.2 — Threshold Re-derivation

Derive new YELLOW / ORANGE / RED thresholds from:
- 90+ days of stable data (not 50 days of broken data like nb19)
- External ground truth (ISW, ACLED, EU DisinfoLab) — not self-referential
- Per-region calibration with sufficient N (>30 per region)

**Current (keep until validated):** YELLOW = 15.2, ORANGE = 59.7, RED = 92.8

### 4.3 — Rebuild Fusion Engine

Once all sensors work individually:
- Combine satellite + FIRMS + AIS + media + OSINT per site
- Dempster-Shafer evidence combination (or simpler weighted vote)
- Original weights: satellite 30%, OSINT 25%, FIRMS 15%, GDELT 15%, ACLED 10%, milwatch 5%

---

## Summary: What To Do When

| Week | Action | Type | Impact |
|------|--------|------|--------|
| 1 | Deploy moderate weights | Config | Fixes broken algorithm |
| 1 | Deploy fabrication gate | Code (small) | 67% noise reduction |
| 1 | Deploy PLMSE metric | Code (small) | Free detection feature |
| 1 | Expand watchlist | Config | Catches non-RU campaigns |
| 1 | Remove RU-origin gate | Code (small) | 42 new narrative detections |
| 1–2 | Fix dead collectors | Ops | Unblocks everything |
| 1–2 | Fix category metadata | DB | Unblocks Fisher/velocity |
| 2 | Add Baltic feeds | Config | Unblocks ET/LV/LT |
| 2–4 | Complete labeled dataset | Manual | Unblocks all detection validation |
| 4–6 | Fisher+Hawkes validation | Research | Better pre-screen |
| 4–6 | Community structure test | Research | New detection feature |
| 6–8 | Mutation detection | New code | Catches fabrication chains |
| 6–8 | Cross-category velocity | New code | Catches multi-origin campaigns |
| 6–8 | FIRMS baselines | New code | Per-site anomaly detection |
| 12+ | Threshold recalibration | Research | Validated threat levels |
| 12+ | Rebuild fusion engine | New code | Multi-sensor threat picture |
