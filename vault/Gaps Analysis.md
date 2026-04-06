---
status: evergreen
tags: [gaps, analysis, education, methodology]
---

# Gaps Analysis

What's missing in the research, identified by cross-referencing with the Education vault (`~/Education/vault/`). Each gap references the Education course that covers the missing methodology.

## Summary

| Gap | Severity | Education Course | Impact on Research |
|-----|----------|------------------|--------------------|
| No NLP content analysis | HIGH | `ai-ml/` (NLP phase) | Campaign detection uses regex, not actual language understanding |
| No link analysis for coordination | HIGH | `forensics-deanon/` | Co-coverage is structural; no entity/actor graph |
| No adversarial robustness | HIGH | `security/` (Adversarial ML) | Actors could game the CTI by learning what triggers it |
| No SAR in new pipeline | MEDIUM | `geoint/` | Cloud-penetrating capability missing from satellite track |
| No bot detection | MEDIUM | `cognitive-warfare/` | Campaign detection assumes human-generated content |
| No frequency-domain analysis | MEDIUM | `dsp/` | Time-series are analyzed only in time domain |
| No stylometry / attribution | MEDIUM | `forensics-deanon/` | Can't attribute campaigns to specific actors |
| No formal threat model | LOW | `security/` (Threat Modeling) | No STRIDE/attack-tree analysis of the monitoring system itself |
| No synthetic media detection | LOW | `cognitive-warfare/` | Deepfakes not addressed (lower priority for text-heavy domain) |

## Detailed Gaps

### 1. No NLP Content Analysis

**Education source:** `ai-ml/` Phase 6 (NLP) — text classification, NER, embeddings, transformers

**What the research does:** FIMI regex (nb29) uses pattern matching for hedging/amplification. Fisher discriminant uses `state_ratio` and `fimi_score` — metadata features, not content.

**What's missing:**
- Semantic similarity beyond cosine clustering (topic modeling, argument mining)
- Named Entity Recognition to track actors, locations, claims across narratives
- Sentiment/stance classification per signal (not just per cluster)
- Cross-lingual content analysis (regex is RU/EN only)
- Transformer-based FIMI detection instead of regex heuristics

**Why it matters:** The current detection stack is blind to *what* narratives say. It only sees *who* spreads them (state_ratio) and *how fast* (velocity). Content-aware features would reduce dependence on source labels, which is exactly what origin-agnostic detection (roadmap Phase 3) needs.

**Concrete next step:** Train a multilingual text classifier (Baltic languages + RU + EN) on the existing 37 campaign summaries to predict `is_hostile` from content features. Compare F1 against Fisher's 0.615.

### 2. No Link Analysis for Coordination Networks

**Education source:** `forensics-deanon/` — link analysis, multi-modal identity correlation

**What the research does:** Co-coverage network (nb30) measures pairwise Jaccard similarity between sources. Hawkes process (nb24) models temporal cascades. Neither builds an actor-level coordination graph.

**What's missing:**
- Entity resolution across sources (is "Rybar" on Telegram the same actor as Rybar on VK?)
- Actor-network graph showing who amplifies whom
- Temporal coordination detection (synchronized posting within minutes)
- Cross-platform cascade tracing (Telegram → RSS → social media)
- Community detection on the actor graph (nb43 starts this but for narratives, not actors)

**Why it matters:** The research detects *signal-level* coordination but not *actor-level* coordination. Two sources posting the same story might be independent coverage or orchestrated — actor-level link analysis would distinguish these.

**Concrete next step:** Build actor graph from `cluster_members.csv` — node per source, edge weighted by co-occurrence in clusters. Run community detection. Compare communities against known state/trusted labels.

### 3. No Adversarial Robustness Analysis

**Education source:** `security/` Phase 4 (Adversarial ML) — evasion attacks, data poisoning, model robustness

**What the research does:** Assumes signals are honest. Optimizes detection against historical data from a period when actors didn't know the system existed.

**What's missing:**
- Adversarial threat model: how would a sophisticated actor evade each detection method?
- Evasion of Fisher: manipulate state_ratio by routing through non-state-labeled sources
- Evasion of Hawkes: slow-drip coordination below the branching ratio threshold
- Evasion of FIMI regex: avoid hedging language while still spreading disinformation
- Data poisoning: flood system with false negatives to shift baseline distributions
- Red team exercise against the CTI formula

**Why it matters:** The system will become public knowledge eventually. Sophisticated actors (state intelligence services) will adapt. Detection methods that can be trivially evaded have limited operational lifespan.

**Concrete next step:** Write a red team assessment for each detection method. For each, answer: "What's the minimal change an actor must make to evade this, and what does that evasion cost them?"

### 4. No SAR Integration in New Pipeline

**Education source:** `geoint/` — SAR fundamentals, all-weather monitoring

**What the research does:** Earlier work (satellite-analysis/03-sar-analysis.ipynb) tested SAR backscatter comparison. New pipeline (nb20–23) uses only Sentinel-2 optical imagery.

**What's missing:**
- Sentinel-1 SAR integration for cloud-penetrating monitoring
- SAR change detection (coherence loss indicates surface disturbance)
- Optical + SAR fusion for higher confidence detections
- Maritime SAR for port/naval activity at coastal sites

**Why it matters:** Sentinel-2 is cloud-limited in the Baltic region (overcast 60–70% of the year). SAR works through clouds. Without it, satellite monitoring has massive temporal gaps.

**Concrete next step:** Port the nb20 seasonal baseline approach to Sentinel-1 SAR. Build VV/VH backscatter profiles alongside NDVI/BSI. This requires GEE access.

### 5. No Bot Detection

**Education source:** `cognitive-warfare/` — bot detection, synthetic media, coordinated inauthentic behavior

**What the research does:** Treats all signals as human-generated content from known sources. No analysis of whether sources themselves are automated or inauthentic.

**What's missing:**
- Posting pattern analysis (frequency, timing, regularity)
- Content originality assessment (copy-paste detection across sources)
- Account age/activity profiling for Telegram channels
- Coordinated inauthentic behavior detection (synchronized accounts)

**Why it matters:** Bot-amplified narratives should be scored differently from organically popular ones. The current `state_ratio` feature doesn't capture bot amplification from non-state accounts.

**Concrete next step:** Analyze posting patterns of Telegram channels in `cluster_members.csv`. Flag channels with suspiciously regular posting intervals or high copy-paste rates.

### 6. No Frequency-Domain Analysis of Time Series

**Education source:** `dsp/` — Fourier decomposition, spectral analysis, filtering

**What the research does:** All time-series analysis is in the time domain — rolling averages, z-scores, day-over-day changes.

**What's missing:**
- Spectral analysis of signal patterns (are there weekly/monthly cycles?)
- Frequency-domain anomaly detection (unusual periodicity = coordination)
- Filtering to separate slow trends from burst events
- Cross-spectral coherence between source types

**Why it matters:** Coordinated campaigns may have characteristic frequency signatures (e.g., weekly news cycle exploitation, pulsed amplification). Time-domain analysis misses these patterns.

**Concrete next step:** Run FFT on `signal_daily_counts.csv` per source type. Look for spectral peaks that differ between state and trusted sources.

### 7. No Stylometric Attribution

**Education source:** `forensics-deanon/` — stylometry, authorship analysis, multi-modal identity correlation

**What the research does:** Tracks narrative origins by `first_source` and `first_category` (nb narrative_origins). No analysis of writing style or authorship patterns.

**What's missing:**
- Writing style features per source (sentence length, vocabulary richness, punctuation patterns)
- Cross-source authorship comparison (do multiple "independent" sources share writing style?)
- Language model perplexity analysis (machine-generated vs human text)
- Temporal style consistency (does a source's writing style change, suggesting handover?)

**Why it matters:** Attribution is the ultimate goal of counter-disinformation. Knowing that three "independent" sources share authorship style is stronger evidence of coordination than co-coverage alone.

**Concrete next step:** Extract stylometric features from RSS content in `signals_90d.csv`. Cluster sources by writing style and compare against known category labels.

## Labeled Dataset Expansion

The single most impactful gap across all tracks. Every detection method is bottlenecked on labeled data:

| What | Current N | Needed N | Source |
|------|-----------|----------|--------|
| Hostile clusters | 6 | 33+ | R-38 |
| Labeled narratives | 8 | 30+ | R-38 |
| Cascade events | 0 | 100+ | R-38 |
| ISW-confirmed satellite detections | 1 | 10+ | Manual |

R-38 (`38_labeled_dataset.py`) exists but needs domain expert input to label.

## External Ground Truth

The research currently validates against its own outputs. External sources needed:

| Source | What It Provides | How to Get |
|--------|-----------------|------------|
| ISW daily updates | Military activity timeline | Web scraping / API |
| ACLED | Conflict events with locations | API (collector dead — F-01) |
| EU DisinfoLab | Documented disinformation campaigns | Manual curation |
| EUvsDisinfo | Debunked narratives with sources | Structured database |
| NATO StratCom COE | Baltic-specific info ops reports | Manual curation |

## Priority Order

Based on impact vs effort:

1. **Labeled dataset expansion** (R-38) — unblocks everything, moderate effort
2. **NLP content analysis** — high impact, leverages existing data
3. **Actor-level link analysis** — high impact, data already in cluster_members
4. **Adversarial robustness** — critical for operational longevity, research-only
5. **SAR integration** — medium impact, requires GEE work
6. **Frequency-domain analysis** — quick win, applies to existing time series
7. **Bot detection** — medium impact, needs Telegram metadata
8. **Stylometric attribution** — medium effort, needs text content
9. **Formal threat model** — low priority, can be done anytime
