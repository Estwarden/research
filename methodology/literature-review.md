# Literature Review: Computational Disinformation Campaign Detection

## Our Approach vs State of the Art

### What We Do

Three detection methods operating on ~2,500 media signals/day from 50+ sources in 6 languages:

1. **Manufactured outrage chains** — structural pattern matching on state media temporal patterns
2. **Hostile framing analysis** — cross-lingual embedding clustering (gemini-embedding-001, 3072d, cosine threshold 0.75) + LLM framing comparison
3. **Injection cascade detection** — propagation velocity profiling + disproportionate amplification scoring

### Academic Critique (from Perplexity literature review, March 2026)

**Strengths acknowledged:**
- Cross-lingual event matching via multilingual embeddings is a valid approach (aligns with Osavul-NATO StratCom cross-language similarity search)
- Pattern-based detection for outrage chains captures real disinformation TTPs
- Aligns with NATO ABCDE framework: we cover Behaviour (coordination), Content (framing), Degree (amplification)

**Weaknesses identified:**

| Weakness | Criticism | Our Response |
|----------|-----------|-------------|
| Arbitrary cosine threshold (0.75) | "Needs validation via silhouette scores" | **Validated** on 7 labeled events (Experiment 6). Clear gap at 0.75 between same-event (0.77+) and different-event (0.71-). |
| LLM unreliability for framing | "F1 scores 0.4-0.7 for intent detection" | Our prompt is NOT intent detection — it checks for fabrication (verifiable) and hedging language (structural). False positive rate: 0/5 in validation. |
| No ground truth evaluation | "Lacks precision/recall on labeled datasets" | **Valid criticism.** We validated on 7 manually labeled events. Need larger labeled dataset (target: 100+ events from EUvsDisinfo cases). |
| No fact-checking module | "Relies on framing diffs, not claim verification" | **Partially addressed.** The `extract_claims.py` processor exists but isn't integrated into detection pipeline yet. |
| Embedding bias on low-resource languages | "ET/LV/LT may underperform vs EN/RU" | **Validated partially.** EN↔RU cosine 0.77-0.85 for same events. Need to test ET/LV/LT specifically. |
| Rule-based detection brittleness | "Outrage keywords prone to false positives" | **Validated.** Tested on 7 events, 0 false positives. But limited test set. |
| Temporal drift | "Static models obsolete quickly" | **By design:** no fine-tuned models. Embedding API + LLM prompts updated without retraining. |

### Methods We Should Consider

#### 1. Hawkes Process for Temporal Coordination

**What it is:** Self-exciting point process that models event intensity as baseline + excitation from prior events.

**Formula:**
```
λ(t) = μ + Σ α·exp(-β(t - tᵢ))
```
Where μ = organic rate, α = excitation magnitude, β = decay rate.

**Why it matters:** Distinguishes organic news diffusion (low α, events spread gradually) from coordinated amplification (high α, synchronized bursts). Could replace our ad-hoc temporal metrics.

**Application to our system:** Fit Hawkes parameters per source category. State media with high α relative to trusted media = coordination signal. Would formalize our "inter-arrival time" intuition.

**Status:** Not yet implemented. Good research candidate.

**References:** Rizoiu et al. (2022, arXiv:2211.14114), Farajtabar et al. (2017), IC-TH model (ACM WWW 2023).

#### 2. Network-Based Coordination Detection

**What it is:** Build similarity networks from co-sharing patterns, filter edges by threshold (>0.95), measure eigenvector centrality.

**Formula:**
```
Edge weight: sim(a,b) = jaccard(content_a, content_b) × temporal_proximity(a,b)
Coordination: top 0.5% by eigenvector centrality
Network density: ρ = 2E / N(N-1)
```

**Why it matters:** Our current approach treats each outlet independently. Network analysis could reveal hidden coordination (outlets that consistently cover the same stories within minutes).

**Status:** We have the data (source × timestamp × content). Need to build the co-coverage network. Research candidate.

**References:** Pacheco et al. (2021), Luceri et al. (2024b), arXiv:2410.22716.

#### 3. Intent-Based Inoculation (IBI)

**What it is:** Prompt LLMs with malicious intent priors before classification. E.g., "If a hostile actor wanted to undermine NATO, would this article serve that goal?"

**Why it matters:** Boosts zero-shot F1 by 9-20% on cross-lingual disinformation tasks. Could improve our framing analysis prompt.

**Status:** Easy to test by modifying the framing prompt. Research candidate.

**Reference:** arXiv:2603.14525v1.

#### 4. ABCDE Framework Alignment

Our system covers:
- ✅ **A (Actor):** Source category classification (russian_state, trusted, etc.)
- ✅ **B (Behaviour):** Outrage chains, coordination detection
- ✅ **C (Content):** Framing analysis, embedding clustering
- ⚠️ **D (Degree):** Signal count only — need reach/virality metrics
- ❌ **E (Effect):** No influence measurement — would need survey data or engagement metrics

**Gap:** We don't measure actual EFFECT on audiences. This is a fundamental limitation shared by most automated systems.

### What We Do Better Than Literature

1. **Cross-lingual event clustering at media monitoring scale** — most papers focus on single-platform (Twitter) social media analysis. We operate across RSS, Telegram, and YouTube in 6 languages.

2. **Framing comparison, not just detection** — most systems classify individual posts as "disinformation" or "not." We compare HOW different source categories cover the SAME event, which is more nuanced and less prone to false positives.

3. **Structural detection without ML** — outrage chain detection uses pure pattern matching, making it interpretable, auditable, and immune to model drift. Most papers rely on black-box classifiers.

4. **Injection cascade as a novel pattern** — we haven't found published work specifically on detecting when trusted media inadvertently amplifies a trivial social media event into a security threat. This appears to be a novel contribution.

### Data Source Gaps

| Source Type | Current | Needed | Impact |
|-------------|---------|--------|--------|
| RSS feeds | 50+ in 6 langs | Sufficient for Baltic | ✅ |
| Telegram channels | 138 monitored | Good coverage | ✅ |
| YouTube | 10 channels | Need more Baltic | ⚠️ |
| Facebook/Meta | None | CrowdTangle discontinued, need alt | ❌ Critical gap |
| TikTok | None | Growing disinfo vector | ❌ |
| VKontakte | None | Key RU social platform | ❌ |
| Engagement metrics | None | Need for Degree/Effect | ❌ |

### Signal Flow Requirements

**Current throughput:** ~2,500 classifiable signals/day, ~100 pass relevance gate, ~20-50 cluster into events

**Minimum for detection:**
- Outrage chains: 3+ signals from same outlet in 24h (works with current flow)
- Framing analysis: need mixed-source clusters (state + trusted covering same event) — ~3-5/week currently
- Injection cascade: need 5+ signals over 48+ hours with 3+ categories — rare, ~1/month

**Analysis frequency:**
- Embedding + clustering: every 4 hours (current)
- Framing analysis: every 4 hours (current, but batched — only analyzes new mixed clusters)
- Outrage chain scan: every 4 hours (current)
- Injection cascade: daily is sufficient (slow phenomenon, spans days)
- CTI recompute: every 3 hours (current)

**Campaign criteria:**
- Minimum signals: 3 (for outrage chains), 2+ sources (for framing), 5+ (for injection)
- Root signal: first signal in the event cluster — determines origin type
- Confidence threshold: 0.7 (framing analysis), 0.85 (outrage chain — structural), 7/12 score (injection)

### References

1. Rizoiu et al. "Detecting Coordinated Information Operations in Social Media" (arXiv:2211.14114, 2022)
2. Pacheco et al. "Uncovering Coordinated Networks on Social Media" (ICWSM, 2021)
3. Luceri et al. "Unmasking Social Bots: Coordinated Behavior Detection" (2024)
4. NATO "Countering Information Threats" (2024)
5. EEAS "3rd FIMI Threat Report" (March 2025)
6. arXiv:2603.14525v1 "Intent-Based Inoculation for Fake News Detection" (2026)
7. EU DisinfoLab "CIB Detection Tree" (2024)
8. Osavul/NATO StratCom "Virtual Manipulation Brief" (2024)
