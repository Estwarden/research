# Autonomous Cognitive Defense System — Architecture Document

**Version:** 0.1
**Date:** 2026-03-23
**Author:** EstWarden Research
**Classification:** Public

## Mission

Build a fully autonomous, fairly unbiased system to protect Estonian people's mental health from cognitive warfare.

**Core constraint:** No human in the decision loop. Humans introduce bias. The system must operate on mathematics, not editorial judgment.

**What the system does NOT do:**
- Does not decide what is "true" or "false"
- Does not censor content
- Does not take political positions
- Does not require an analyst to classify threats

**What the system DOES:**
- Measures behavioral anomalies in information flow
- Detects when claims mutate beyond their source material
- Quantifies emotional amplification gradients
- Compares narrative claims against physical sensor data
- Exposes the mechanism — lets humans make informed decisions

---

## The Threat Model

### Current: Disinformation
False or misleading content spread to deceive. Detectable through fact-checking.

### Next: Cognitive Warfare
Deliberate exploitation of human cognitive processes to alter decision-making. Does not require false content — true information weaponized through framing, timing, repetition, and emotional manipulation.

**Key insight:** Cognitive warfare doesn't need to lie. It needs to make you afraid, exhausted, or unable to distinguish signal from noise.

### Why Human-in-the-Loop Fails
1. **Bias inheritance:** Analyst's political views contaminate classification
2. **Scalability:** Humans can't process 40K signals/day
3. **Speed:** By the time a human classifies a threat, the cascade has peaked
4. **Adversarial adaptation:** Actors learn what humans flag and adapt
5. **Quis custodiet:** Who watches the watchers? The system must be auditable and bias-free

---

## Architecture: Five Measurement Layers

Each layer produces a numerical score. No layer makes a truth judgment. Combined scores create a threat assessment that is transparent, auditable, and reproducible.

### Layer 1: Behavioral Coordination Detection

**Question:** Are channels acting in statistically unusual synchronization?

**Method:**
- For each channel, compute baseline posting frequency and topic distribution (30-day rolling window)
- For each pair of channels, compute co-posting rate on same event clusters
- Flag when co-posting rate exceeds baseline by >3σ (standard deviations)
- Build coordination network: nodes = channels, edges = co-posting frequency
- Compute network features: density, clustering coefficient, modularity

**Output:** Coordination Score (0-100)
- 0-20: Normal organic behavior
- 20-50: Elevated synchronization (could be breaking news)
- 50-80: Anomalous coordination (unlikely to be organic)
- 80-100: Extreme coordination (statistically near-impossible without organization)

**Scientific basis:**
- CooRnet methodology (Giglietto et al., 2020)
- Signals of Propaganda PLMSE metric (PLOS ONE, 2025)
- TIDE-MARK community topology (PMC, 2026)

**No content analysis. Pure behavioral signal.**

**Implementation:**
- Data: `signals` table + `event_clusters` + `cluster_signals`
- Compute: PostgreSQL window functions + Python statistical analysis
- Storage: New table `coordination_scores` (cluster_id, score, features_json, computed_at)
- Trigger: Runs after each clustering cycle (every 6 hours)

### Layer 2: Claim Mutation Tracking

**Question:** Are claims gaining specificity as they propagate? (Fabrication signature)

**Method:**
- For each event cluster, identify root signal (earliest, or highest-credibility source)
- Extract verifiable claims from root: time references, numbers, legal claims, certainty markers
- Extract same from each subsequent signal in cluster
- Compute drift: claims ADDED that don't exist in root = mutation
- Natural news loses detail over hops. Fabrication ADDS detail.

**Output:** Mutation Score (0-100)
- 0-20: Faithful reproduction — claims decrease or stay constant
- 20-50: Moderate drift — some framing changes, some additions
- 50-80: Significant mutation — new specific claims added (dates, laws, numbers)
- 80-100: Fabrication — claims manufactured that contradict or extend far beyond source

**Scientific basis:**
- Misinformation Index (Maurya et al., arXiv 2025)
- Information mutation in gossip networks (Kaswan & Ulukus, 2023)
- Cross-lingual claim detection (Panchendrarajan & Zubiaga, 2024)

**Content-adjacent but not truth-judging.** Measures CHANGE, not correctness.

**Implementation:**
- Data: `signals` table with text content, `event_clusters`
- Compute: Regex-based claim extraction (Phase 1) → LLM claim extraction (Phase 2)
- Comparison: Gemini embeddings in `signal_embeddings` (pgvector) for semantic similarity
- Storage: New table `mutation_scores` (cluster_id, root_signal_id, score, mutations_json, computed_at)
- Trigger: Runs after clustering, for clusters with ≥3 signals

### Layer 3: Emotional Amplification Detection

**Question:** Is fear/urgency escalating as information spreads?

**Method:**
- Score each signal for emotional intensity (fear, urgency, anger, panic markers)
- Track emotional gradient across the cluster timeline
- Natural reporting: flat or decreasing emotional intensity
- Weaponized content: escalating emotional intensity per hop

**Emotional markers (regex-based, multilingual):**
- Urgency: "BREAKING", "СРОЧНО", "ТЕРМІНОВО", "IMMINENT"
- Fear: "invasion", "attack", "нападение", "вторжение"
- Certainty escalation: question marks → exclamation marks
- Capitalization ratio: increasing CAPS = increasing alarm
- Exclamation density: !/word ratio

**Output:** Amplification Score (0-100)
- 0-20: Flat or decreasing emotion — normal reporting
- 20-50: Moderate escalation — editorial framing
- 50-80: Significant escalation — fear amplification
- 80-100: Extreme escalation — panic manufacturing

**Scientific basis:**
- Vosoughi et al. (Science, 2018) — novelty and emotional reactions drive sharing
- Drift Diffusion Model (Alvarez-Zuzek et al., 2024) — instinctive sharing of fear content
- Cognitive warfare doctrine: emotional manipulation as weapon

**No truth judgment. Measures emotional gradient only.**

**Implementation:**
- Data: `signals` table text content
- Compute: Multilingual regex scoring + optional sentiment model
- Storage: New columns on `signals` (emotional_intensity float) + aggregate in `cluster_scores`
- Trigger: On signal ingestion (per-signal) + aggregation after clustering

### Layer 4: Sensor Divergence (EstWarden's Unique Advantage)

**Question:** How far are narrative claims from measured physical reality?

**Method:**
- Extract threat-level claims from narrative clusters ("invasion imminent", "troop buildup", "military activity")
- Compare against actual sensor readings:
  - Military indicators (satellite, ADS-B, AIS)
  - GPS jamming levels
  - ACLED conflict events
  - FIRMS fire/explosion data
  - IODA internet disruptions
- Compute divergence: narrative says RED, sensors say GREEN = maximum divergence

**Output:** Divergence Score (0-100)
- 0-20: Narrative aligns with sensor data
- 20-50: Narrative slightly exceeds sensor readings
- 50-80: Significant gap — claims not supported by sensors
- 80-100: Complete divergence — narrative contradicts all available evidence

**THIS IS THE KEY DIFFERENTIATOR.** No other system in the world has this capability — real-time physical sensor data to anchor narrative analysis.

**Scientific basis:**
- EstWarden CTI methodology (existing)
- Ground truth validation (existing research/findings-ground-truth-validation.md)
- Multi-source intelligence fusion principles

**Implementation:**
- Data: Existing CTI scores + signal narrative extraction
- Compute: Compare cluster narrative tags against daily CTI category scores
- Storage: Existing `threat_indices` table + new `narrative_sensor_divergence` view
- Trigger: Daily after CTI computation

### Layer 5: Impact Measurement

**Question:** Did this cascade actually change people's behavior?

**Method:**
- Track downstream indicators after a flagged cascade:
  - Google Trends search volume for related terms
  - Social media engagement velocity (views/forwards acceleration)
  - News pickup: did mainstream media amplify?
  - Cross-platform spread: TG → YouTube → web → TG cycle
- Apply Granger causality: does coordinated activity predict future organic engagement?

**Output:** Impact Score (0-100)
- 0-20: Cascade died — no downstream effects
- 20-50: Moderate pickup — some organic engagement
- 50-80: Significant impact — mainstream amplification, search spikes
- 80-100: Mass behavior change — panic buying, travel cancellations, policy pressure

**Scientific basis:**
- Granger causality for CIB impact (Frontiers in Communication, 2025)
- Agent-based modeling of CIB impact on recommendations (Mehtaverse, 2024)
- Information cascade dynamics (TIDE-MARK, 2026)

**Implementation:**
- Data: External APIs (Google Trends, social media metrics) + internal signal velocity
- Compute: Time-series analysis, Granger causality tests
- Storage: New table `cascade_impact` (cluster_id, impact_metrics_json, computed_at)
- Trigger: 24h and 72h after cascade detection

---

## Combined Threat Assessment

The five scores combine into a **Cognitive Threat Level** (CTL):

```
CTL = w1 × Coordination + w2 × Mutation + w3 × Amplification + w4 × Divergence + w5 × Impact
```

**Default weights (adjustable, transparent):**
- w1 (Coordination): 0.25 — behavioral anomaly is the strongest signal
- w2 (Mutation): 0.20 — fabrication indicates intentionality
- w3 (Amplification): 0.15 — emotional escalation indicates weaponization
- w4 (Divergence): 0.25 — sensor data is ground truth
- w5 (Impact): 0.15 — actual harm measurement

**Thresholds:**
- CTL 0-25: GREEN — normal information flow
- CTL 25-50: YELLOW — elevated activity, monitoring
- CTL 50-75: ORANGE — likely manipulation, automatic alert
- CTL 75-100: RED — active cognitive threat, maximum visibility

**Key properties:**
1. **Transparent:** Every score is computed from auditable data
2. **Reproducible:** Same inputs → same outputs
3. **Unbiased:** No human decides what is "true" — math measures anomalies
4. **Adaptable:** Weights can be tuned based on validated outcomes
5. **Auditable:** All intermediate scores stored with methodology references

---

## What the System Outputs

### For the public (estwarden.eu dashboard):
- CTL score per region (existing CTI, enhanced)
- Active cascades with scores (transparency)
- "What our sensors actually show" vs "what channels claim" (divergence visualization)

### For automated alerting:
- CTL > 50 → Telegram channel alert with scores
- CTL > 75 → Full investigation auto-generated (like the Bild map case study, but automated)

### For researchers:
- All scores, features, and methodology in open database
- Reproducibility: anyone can verify the computation

---

## Implementation Roadmap

### Phase 1: Foundation (weeks 1-4)
- [ ] Add missing channels to watchlist (6 from Bild map case)
- [ ] Implement PLMSE metric on signal data
- [ ] Implement claim extraction (regex-based)
- [ ] Create `coordination_scores` and `mutation_scores` tables

### Phase 2: Core Detection (weeks 5-8)
- [ ] Implement Layer 1: Behavioral coordination detection
- [ ] Implement Layer 2: Claim mutation tracking
- [ ] Implement Layer 3: Emotional amplification scoring
- [ ] Connect Layer 4: Sensor divergence (link existing CTI to narratives)

### Phase 3: Autonomy (weeks 9-12)
- [ ] Combined CTL scoring
- [ ] Automated alerting pipeline
- [ ] Auto-generated investigation reports
- [ ] Impact measurement (Layer 5)

### Phase 4: Validation & Hardening (weeks 13-16)
- [ ] Backtest on historical campaigns (labeled data)
- [ ] Cross-validate with external datasets (IRA, ISOT)
- [ ] Bias audit: does the system flag different sources fairly?
- [ ] Red team: can we game the system?

---

## Ethical Guardrails

1. **The system does not censor.** It measures and exposes. People decide.
2. **The system does not take political positions.** It flags behavioral anomalies regardless of who benefits.
3. **All methodology is public.** Anyone can audit the scores.
4. **Weights are transparent and adjustable.** No hidden parameters.
5. **The system can be wrong.** Confidence intervals and uncertainty are part of every output.
6. **Regular bias audits.** Monthly check: are we flagging one side more than another? If yes, investigate whether the algorithm or the reality is skewed.

---

## References

1. Giglietto et al. "CooRnet: Coordinated Link Sharing Behavior" (2020)
2. Vosoughi, Roy & Aral. "The Spread of True and False News Online" (Science, 2018)
3. Maurya et al. "Simulating Misinformation Propagation with LLMs" (arXiv, 2025)
4. PLOS ONE. "Signals of Propaganda — PLMSE Metric" (2025)
5. TIDE-MARK. "Tracking Dynamic Communities in Fake News Cascades" (PMC, 2026)
6. Kaswan & Ulukus. "Information Mutation in Gossip Networks" (2023)
7. NATO Chief Scientist. "Cognitive Warfare Report" (2025)
8. EU DisinfoLab. "CIB Detection Tree" (2024)
9. Frontiers in Communication. "Granger Causality for CIB Impact" (2025)
10. EstWarden CTI Methodology (internal, validated)
