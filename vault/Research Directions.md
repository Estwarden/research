---
status: evergreen
tags: [research, experiments, new-directions]
---

# Research Directions

New research experiments to pursue, based on gaps identified in [[Gaps Analysis]], production system weaknesses, and evolving disinformation patterns. Each direction has a concrete experiment design.

> **Production has outrun the research.** The [multi-source GEOINT pipeline](https://blog.estwarden.eu/investigations/multi-source-geoint/) shipped SAR integration, EMCON detection, camouflage detection via NDRE, and multi-source confidence scoring — all without formal research validation. Several R-59 items (SAR baselines) now need to become *validation* experiments rather than *development* experiments. New priorities: validate NDRE camouflage detection, benchmark EMCON correlation against ISW, and measure multi-source confidence accuracy.

## Priority 1: Directly Actionable

### R-50: NLP Content Classification for Campaign Detection

**Problem:** Current detection uses metadata features (state_ratio, fimi_score) — it sees *who* spreads content and *how fast*, but not *what* it says. This makes it blind to content-aware manipulation and blocks origin-agnostic detection.

**Experiment design:**
1. Extract text features from `signals_90d.csv` RSS/Telegram content:
   - TF-IDF on trigrams (language-aware tokenization for RU/EN)
   - Sentiment polarity and subjectivity per signal
   - Named entity density (actors, locations, dates)
   - Certainty language markers (hedging vs assertion)
2. Train multilingual text classifier on 37 campaign summaries (`campaigns_full.csv`):
   - Target: `is_hostile` binary classification
   - Features: content-derived only (no source metadata)
   - Baseline: compare F1 against Fisher's 0.615
3. Test cross-lingual transfer: train on RU/EN, evaluate on LT signals

**Data:** `signals_90d.csv` (849K signals with text content), `campaigns_full.csv` (37 campaigns)

**Expected outcome:** Content-only classifier F1 > 0.615 would prove content features add signal beyond metadata. If F1 < 0.5, content analysis has limited value for this dataset.

**Notebook:** `50_content_classification.py`

### R-51: Actor Coordination Network

**Problem:** Co-coverage (nb30) measures pairwise source similarity. Hawkes (nb24) models temporal cascades. Neither builds an actor-level coordination graph that would reveal who amplifies whom.

**Experiment design:**
1. Build actor graph from `cluster_members.csv`:
   - Node = source (feed_handle or channel)
   - Edge weight = number of clusters both sources appear in
   - Directed edges: source A published before B in shared clusters
2. Run community detection (Louvain/Leiden) on the actor graph
3. Compare discovered communities against known labels:
   - Do `ru_state` sources cluster together?
   - Do `trusted` sources form separate communities?
   - Are there bridge nodes that connect state and trusted communities?
4. Identify amplification chains: which sources consistently publish AFTER state media in the same clusters?

**Data:** `cluster_members.csv` (7,587 mappings), `clusters.csv` (2,278 clusters)

**Expected outcome:** Actor communities that correlate with `category` labels validate the network approach. Bridge nodes between communities are the most interesting — potential laundering intermediaries.

**Notebook:** `51_actor_network.py`

### R-52: Labeled Dataset Expansion via EUvsDisinfo

**Problem:** Everything is blocked on N=17 hostile clusters (need 33+). Manual labeling from scratch is slow (~0.34 hostile/week natural rate = 47 weeks to reach target).

**Experiment design:**
1. Scrape EUvsDisinfo case database (1,000+ documented cases with narratives, sources, dates)
2. For each EUvsDisinfo case:
   - Extract key narrative (title, summary, date range)
   - Embed with same model used for clustering (gemini-embedding-001)
   - Find nearest clusters in our `clusters.csv` by cosine similarity
   - If similarity > 0.75 AND date overlap: label cluster as hostile
3. Validate: spot-check 20 auto-labeled clusters manually
4. Secondary source: NATO StratCom COE Baltic reports (specific to our region)

**Data:** `clusters.csv` (2,278 clusters), EUvsDisinfo public API/scrape

**Expected outcome:** 20-50 additional hostile labels from automated matching, enough to unblock Fisher+Hawkes (nb40) and community structure (nb43).

**Notebook:** `52_euvsdisinfo_labeling.py`

---

## Priority 2: New Detection Methods

### R-53: Claim Mutation Detection

**Problem:** The Bild map campaign succeeded because amplifying channels *added* fabricated claims ("1-2 months", "laws passed") not in the original source. The system clusters similar signals but doesn't detect content drift within a cluster.

**Experiment design:**
1. For each cluster with 5+ signals, identify root signal (earliest publication)
2. Extract claims from root using regex patterns:
   - Time references: `\d+[-–]\d+\s*(months?|weeks?|days?|месяц|недел)`
   - Legal claims: `(law|закон)\s*(passed|принят|одобрен)`
   - Certainty markers: `(will attack|final stage|неизбежн|точно)`
   - Numeric specifics: amounts, distances, unit counts
3. Compare claims in downstream signals (sorted by publication time)
4. Flag: downstream has claim pattern not present in root = MUTATION
5. Score: `mutation_score = count(added_claims) * certainty_escalation`
6. Validate against known fabrication_alerts.csv (50 alerts)

**Data:** `cluster_members.csv` + full signal text from `signals_90d.csv`

**Expected outcome:** Mutation detector catches Bild-map-style fabrication. Validate by checking if the 50 existing fabrication alerts would be caught.

**Notebook:** `53_mutation_detection.py`

### R-54: Frequency-Domain Signal Analysis

**Problem:** All time-series analysis is in the time domain (rolling averages, z-scores). Coordinated campaigns may have characteristic frequency signatures — weekly news cycle exploitation, pulsed amplification — that time-domain analysis misses.

**Experiment design:**
1. Run FFT on `signal_daily_counts.csv` per source_type
2. Identify dominant frequencies:
   - 7-day (weekly news cycle)?
   - ~30-day (monthly political cycles)?
   - Irregular bursts (campaign timing)?
3. Compare spectral profiles: `ru_state` vs `trusted` vs `baltic_media`
4. Cross-spectral coherence: which source pairs have synchronized frequency components?
5. Anomaly detection: flag days where spectral content deviates from the 30-day baseline

**Data:** `signal_daily_counts.csv` (499 rows), `signal_hourly_counts.csv` (2,154 rows)

**Expected outcome:** If state media have distinctive frequency signatures (e.g., synchronized weekly peaks), this provides a new detection axis independent of content or metadata.

**Notebook:** `54_spectral_analysis.py`

### R-55: Bot Detection from Posting Patterns

**Problem:** Campaign detection assumes all content is human-generated. Bot-amplified narratives should score differently from organically popular ones.

**Experiment design:**
1. Extract posting pattern features per Telegram channel from `cluster_members.csv`:
   - Inter-post interval mean, std, and regularity (CV)
   - Active hours distribution (bots post at unusual hours)
   - Content originality: pairwise cosine similarity between channel's own posts
   - Copy-paste rate: exact title matches across channels within 24h windows
2. Cluster channels by posting pattern (k-means on pattern features)
3. Compare pattern clusters against known `category` labels
4. Flag channels with: very regular intervals (CV < 0.3) + high copy-paste rate (> 50%)

**Data:** `cluster_members.csv` (7,587 mappings with timestamps), `signals_90d.csv` (for full text)

**Expected outcome:** Identify 5-15 channels with bot-like posting patterns. If these correlate with state-media amplification clusters, bot detection adds signal.

**Notebook:** `55_bot_detection.py`

---

## Priority 3: Adversarial & Robustness

### R-56: Red Team Analysis of Detection Methods

**Problem:** Detection methods are validated against historical data from a period when actors didn't know the system existed. Sophisticated actors (state intelligence services) will adapt once the system becomes known.

**Experiment design (thought experiment + simulation):**

For each detection method, answer:

| Method | Evasion Strategy | Cost to Actor | Detection Residual |
|--------|-----------------|---------------|-------------------|
| Fisher (state_ratio) | Route through non-state-labeled sources | Low — just use different channels | Lose state_ratio signal entirely |
| Hawkes (BR) | Slow-drip instead of burst coordination | Medium — slower spread = less impact | BR drops below threshold |
| FIMI regex | Avoid hedging language | Low — trivial linguistic adaptation | Regex becomes useless |
| Co-coverage (Jaccard) | Spread across more diverse sources | Medium — need more assets | Jaccard diluted |
| Narrative velocity | Sustain steady state_ratio, avoid spikes | Medium — requires patience | Velocity stays below threshold |
| PLMSE | Vary posting timing to break power-law | Low — add random delays | PLMSE noise increases |

**Simulation:**
1. Take the 6 labeled hostile clusters
2. For each, simulate what happens if the actor applies each evasion strategy
3. Measure: which detection methods survive? What's the minimum evasion effort?

**Expected outcome:** Identify which methods are robust (hard to evade without reducing campaign effectiveness) vs fragile (trivially evaded). Prioritize robust methods for production.

**Notebook:** `56_red_team.py`

### R-57: Adversarial Robustness of Embeddings

**Problem:** If actors learn the clustering threshold (cosine 0.75), they can craft content that stays just below it — semantically related but not clustered together.

**Experiment design:**
1. Take 10 hostile cluster seed texts
2. Progressively paraphrase each (increasing semantic distance)
3. Measure: at what paraphrase level does cosine similarity drop below 0.75?
4. Test: does switching to a different embedding model (BGE-M3, Jina) change the boundary?
5. Propose: adaptive threshold or ensemble embeddings as defense

**Data:** 10 hostile cluster texts from labeled dataset, embedding API access

**Expected outcome:** Understand how many paraphrase steps an actor needs to evade clustering. If the answer is > 3 steps, the embedding is reasonably robust.

**Notebook:** `57_embedding_robustness.py`

---

## Priority 4: Advanced Methods

### R-58: Stylometric Source Attribution

**Problem:** Multiple "independent" sources may share authorship — a stronger coordination signal than co-coverage. Currently no analysis of writing style.

**Experiment design:**
1. Extract per-source stylometric features from RSS content:
   - Sentence length distribution (mean, std)
   - Vocabulary richness (type-token ratio)
   - Function word frequencies (language-specific stopword patterns)
   - Punctuation patterns (exclamation marks, ellipses, em-dashes)
2. Compute pairwise stylistic similarity between all sources with 10+ signals
3. Hierarchical clustering on stylistic features
4. Compare stylistic clusters against:
   - `category` labels (do state sources share style?)
   - Actor network communities from R-51
   - Known editorial relationships

**Data:** `signals_90d.csv` (RSS content), need 10+ signals per source

**Expected outcome:** If 3+ "independent" sources share writing style, that's evidence of shared authorship — stronger than co-coverage.

**Notebook:** `58_stylometry.py`

### R-59: SAR Integration for Cloud-Penetrating Monitoring

**Problem:** Sentinel-2 optical imagery is cloud-limited in the Baltic (60-70% overcast). Sentinel-1 SAR works through clouds but isn't in the new pipeline.

**Experiment design:**
1. Port nb20 seasonal baseline approach to Sentinel-1 SAR:
   - Build 3-year VV/VH backscatter profiles per military site (via GEE)
   - Compute deseasonalized z-scores (same methodology as NDVI/BSI)
2. Correlate SAR anomalies with optical anomalies:
   - When both fire on same site/week: HIGH confidence
   - SAR-only anomalies: MEDIUM (could be rain/soil moisture)
   - Optical-only anomalies: MEDIUM (cloud gaps may miss context)
3. Test: does SAR detect the same Luga breakpoint that CCDC found in nb22?

**Data:** Sentinel-1 via GEE, same military site coordinates as nb20-23

**Expected outcome:** SAR baselines fill the 60-70% cloud gap. If the Luga breakpoint replicates in SAR, dual-sensor detection is validated.

**Notebook:** `59_sar_baselines.py`

### R-60: Evolving Pattern Detection

**Problem:** Seven new disinformation patterns identified in `../evolving-disinfo-patterns.md` that current detection doesn't address.

| Pattern | Why It Evades | Research Approach |
|---------|---------------|-------------------|
| Distortion-as-a-Service | Real source + fabricated amplification | R-53 mutation detection |
| Engagement-Optimized Panic | No coordination — solo actors optimizing for clicks | R-55 bot/pattern detection |
| LLM-Generated Analysis | High quality content, defeats quality filters | R-57 embedding analysis + perplexity scoring |
| Narrative Laundering | Multi-hop citation washing across platforms | R-51 actor network + citation chain tracing |
| Cognitive Flooding | No single post is "disinfo" — pattern emerges at aggregate | R-54 frequency analysis |
| Synthetic Context | Real elements, fabricated scenario | R-53 claim extraction |
| Pre-bunking Poisoning | Preemptive framing in legitimate reporting | Content classification (R-50) |

**Approach:** Not a single experiment. This is the umbrella research question that R-50 through R-59 collectively address. Each new pattern maps to one or more specific experiments above.

---

## Experiment Dependencies

```
R-52 (EUvsDisinfo labeling)
  ↓ labels
R-50 (content classification) ←── needs labeled + text data
R-51 (actor network) ←── standalone, uses cluster_members
  ↓                              ↓
R-53 (mutation detection) ←── needs actor graph + text
R-56 (red team) ←── needs all detection methods running
  ↓
R-57 (embedding robustness) ←── needs hostile examples
R-58 (stylometry) ←── standalone, uses signal text
R-54 (frequency analysis) ←── standalone, uses daily counts
R-55 (bot detection) ←── standalone, uses posting patterns
R-59 (SAR baselines) ←── standalone, needs GEE access
```

**Critical path:** R-52 → R-50 → R-53 → R-56

**Independent tracks (can start anytime):**
- R-51 (actor network)
- R-54 (frequency analysis)
- R-55 (bot detection)
- R-58 (stylometry)
- R-59 (SAR baselines)

## Estimated Research Outcomes

If all Priority 1-2 experiments succeed:

| Metric | Current | Target | How |
|--------|---------|--------|-----|
| Hostile cluster labels | 17 | 50+ | R-52 EUvsDisinfo matching |
| Fisher F1 | 0.615 | > 0.80 | R-50 content + R-52 labels |
| Detection coverage | RU-origin only | All origins | R-51 actor network + R-53 mutation |
| Evasion resilience | Unknown | Documented | R-56 red team analysis |
| Temporal gaps | 60-70% cloud | < 30% | R-59 SAR integration |

The goal is not perfection — it's **enough validated methods that losing any single one doesn't blind the system.**
