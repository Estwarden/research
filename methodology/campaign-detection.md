# Disinformation Campaign Detection Methods

## Problem Statement

Detecting coordinated information operations from a stream of ~2,500 media signals/day across 50+ sources in 6 languages (EN, RU, ET, LV, LT, FI).

**What IS an information operation:**
- Fabrication of facts, quotes, or sources (e.g., citing non-existent officials)
- Manufactured outrage chains (minor event → official reaction articles → amplification)
- Hostile reframing of real events to serve strategic goals
- Coordinated temporal clustering of identical talking points across seemingly independent outlets

**What is NOT an information operation:**
- Multiple outlets covering the same news story (normal journalism)
- State media reporting facts that are embarrassing for the West
- Different editorial emphasis on the same event
- A source publishing content on its regular schedule

## Architecture: Event-Based Detection

```
signals → rejection gate → embedding → clustering → framing analysis → campaign
```

### Stage 1: Signal Relevance Gate

Not all signals are worth analyzing. TASS publishes ~700 articles/48h, 93% about domestic Russian news (sports, accidents, Iran). Only ~7% mention Baltic/NATO topics.

**Two-layer filter:**
1. **Region relevance**: Does the signal mention any monitored region (Estonia, Latvia, Lithuania, Kaliningrad, etc.) in any language?
2. **Topic relevance**: Is it about security, politics, military, energy — or about sports, cooking, weather?

Security-focused sources (government feeds, counter-disinfo) skip the topic filter. General media (including trusted Estonian/Baltic media) requires both region AND topic match.

**Result**: ~100 signals/day pass (from ~2,500). 96% noise reduction.

### Stage 2: Semantic Embedding

Multilingual embedding (Google `gemini-embedding-001`, 3072 dimensions) enables clustering signals about the same EVENT regardless of language.

"Российский истребитель нарушил воздушное пространство Эстонии" and "Russian fighter jet breaches Estonia's airspace" should cluster together despite being in different languages from different sources.

**Cost**: ~$0.002/day at current signal volume.

### Stage 3: Event Clustering

Cosine similarity threshold of 0.82 groups signals about the same story. Each cluster represents an EVENT — a real-world occurrence covered by multiple outlets.

Key metadata per cluster:
- `has_state`: Does the cluster contain Russian state/proxy media signals?
- `has_trusted`: Does it contain trusted/independent media signals?
- `sources`: Which specific outlets are in the cluster?
- `first_seen` / `last_seen`: Temporal spread

**Only clusters with BOTH state and trusted sources are interesting** — these are events where we can compare framing.

### Stage 4: Framing Analysis (LLM)

For mixed-source clusters, an LLM compares how state media vs trusted media frame the same event. The prompt is calibrated to distinguish between:

| Pattern | Example | Info Op? |
|---------|---------|----------|
| Fabrication | TASS cites "General Grinkevich" who doesn't exist | ✅ YES |
| Manufactured outrage | TASS: event → Duma reaction → expert outrage → editorial | ✅ YES |
| Hostile reframing | Event reported neutrally by ERR, spun as "Baltic oppression" by RT | ✅ YES |
| Same facts, different emphasis | TASS says "evacuated", 15min says "relocated" | ❌ NO |
| Reporting real Western statements | Trump called NATO "paper tigers" — both sides report it | ❌ NO |

**Output per cluster:**
- `event_fact`: What actually happened (neutral)
- `state_framing`: How state media covered it
- `trusted_framing`: How trusted media covered it
- `framing_delta`: What's materially different
- `is_hostile`: Boolean — is this manipulation or just journalism?
- `hostile_narrative`: Which taxonomy narrative does it serve (if hostile)

### Stage 5: Campaign Assembly

Only clusters with `is_hostile=true` and `confidence >= 0.7` become campaigns. Each campaign has:
- A clear event description (not AI-generated summary)
- Specific evidence of manipulation (fabricated source, manufactured outrage, etc.)
- Source chain showing who published what
- Taxonomy narrative mapping

## Open Research Questions

### Q1: Optimal Embedding Model
Is `gemini-embedding-001` (3072d, multilingual) the best choice? Alternatives:
- `multilingual-e5-large` (1024d, open-source, can self-host)
- OpenAI `text-embedding-3-small` (1536d, cheaper)
- Fine-tuned model on Baltic disinfo corpus

**Experiment**: Compare clustering quality (V-measure) across models using manually labeled event pairs.

### Q2: Clustering Threshold
Is cosine 0.82 optimal? Too high = miss related coverage in different languages. Too low = merge unrelated stories.

**Experiment**: Plot precision/recall curve for event clustering at thresholds 0.70-0.95 using manually labeled pairs.

### Q3: Temporal Decay in Clustering
Should a signal from 6 days ago cluster with today's signal about the same topic? Currently yes (7-day window). But a story from last week is often a new development, not the same event.

**Experiment**: Measure cluster quality vs temporal window (1d, 3d, 7d).

### Q4: Manufactured Outrage Detection
The LLM catches fabrication well but manufactured outrage chains are harder. Can we detect them structurally?

Pattern: signal₁ (original event) → signal₂ (official reaction, same outlet, <6h) → signal₃ (expert outrage, <12h) → signal₄ (editorial, <24h). All from the same outlet or outlet group.

**Experiment**: Find outrage chains in historical data using temporal + source patterns.

### Q5: Cross-Outlet Coordination Metrics
When 5 outlets publish the same talking point within 2 hours, is that coordination or just news? Statistical test: compare temporal clustering of state media signals vs trusted media signals for the same events.

**Experiment**: For each event cluster, compute inter-arrival times for state vs trusted sources. Test if state media is significantly more synchronized.

### Q6: Framing Classification Without LLM
Can we detect hostile framing without an LLM call per cluster? Features:
- Sentiment delta (state vs trusted)
- Entity usage (who is quoted, who is blamed)
- Headline emotion markers (СРОЧНО, !!!, 🔴)
- Source attribution patterns (anonymous sources vs named officials)

**Experiment**: Train a classifier on the LLM's is_hostile labels to identify cheap proxy features.

## Narrative Taxonomy

Specific narrative IDs used for mapping hostile framings:

| ID | Theme | Target |
|----|-------|--------|
| `russian_speakers_oppressed` | Russian minorities face discrimination | EE, LV |
| `baltic_failed_states` | Baltic economies collapsing | EE, LV, LT |
| `nazi_baltic` | Baltic states harbor Nazi sympathizers | EE, LV, LT |
| `baltic_attack_imminent` | Russia will attack Baltic states | EE, LV, LT |
| `article5_failure` | NATO won't defend Baltic states | Global |
| `nato_provocation` | NATO/Baltics provoking Russia | Global |
| `nuclear_threat` | Nuclear war imminent | Global |
| `western_fatigue` | West will abandon Ukraine | Global |
| `sanctions_backfire` | Sanctions hurt Europe more | Global |
| `migration_weapon` | Migrants weaponized against Baltics | LT, PL |

## Data Sources

| Source | Type | Volume | Region |
|--------|------|--------|--------|
| TASS, RT, Kommersant, Interfax | Russian state RSS | ~1,400/48h | Global |
| ERR, Postimees | Estonian media RSS | ~340/48h | Estonia |
| 15min.lt, Delfi LT | Baltic media RSS | ~350/48h | Lithuania |
| LSM.lv | Baltic media RSS | ~80/48h | Latvia |
| 138 Telegram channels | Social monitoring | ~385/48h | Mixed |
| Perplexity OSINT | AI research | ~13/48h | Baltic |

## References

- EU FIMI framework: [EEAS FIMI reports](https://www.eeas.europa.eu/eeas/1st-eeas-report-foreign-information-manipulation-and-interference-threats_en)
- Baltic Centre for Media Excellence: [methodology](https://bcme.eu/)
- NATO StratCom COE: [publications](https://stratcomcoe.org/publications)
- EUvsDisinfo: [disinformation cases](https://euvsdisinfo.eu/disinformation-cases/)
