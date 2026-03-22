# Reading List: Scientific Foundations for Disinformation Detection

**Compiled:** 2026-03-22
**Purpose:** Research papers with implementable science for EstWarden's detection pipeline

## Tier 1: Directly Implementable

### 1. "Signals of Propaganda" — PLOS ONE, Jan 2025
- **URL:** https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0309688
- **Code:** DOI 10.5281/zenodo.10805274
- **Method:** PLMSE (Power Law MSE) metric detects manipulation through repetition patterns
- **Key result:** Distinguishes political from organic cascades (p=0.0001) using power-law distribution analysis
- **Language-independent, culture-independent.** Pure math.
- **TODO:** Implement PLMSE on EstWarden Telegram signal data

### 2. "Simulating Misinformation Propagation with LLMs" — Maurya et al., arXiv Nov 2025
- **URL:** https://arxiv.org/abs/2511.10384
- **Method:** LLM personas as synthetic agents. Auditor-node framework tracks claim-level factual drift
- **Key result:** Misinformation Index + Propagation Rate. Identity personas accelerate misinfo. Expert personas preserve accuracy.
- **TODO:** Implement auditor framework — compare source claims vs amplified claims per hop

### 3. "TIDE-MARK: Tracking Dynamic Communities in Fake News Cascades" — PMC, Jan 2026
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12876841/
- **Method:** Temporal GNN + Markov modeling + RL for community tracking
- **Key result:** Fake news spreads through MORE cohesive communities (higher modularity). Structure alone predicts fake vs real (AUC 0.83). No content analysis needed.
- **TODO:** Extract structural features from our signal clusters for fake/real classification

### 4. SemEval 2025 Task 7: Cross-lingual Fact-Checked Claim Retrieval
- **URL:** https://aclanthology.org/2025.semeval-1.35.pdf
- **Method:** Ensemble of embedding models (BGE-M3, Jina, GTE) + weighted cosine similarity
- **Key result:** Cross-lingual retrieval works. Ensemble > single model.
- **TODO:** Use our Gemini embeddings for cross-lingual claim matching (UK/RU/EN/DE)

## Tier 2: Foundational Understanding

### 5. Vosoughi, Roy & Aral — "The Spread of True and False News Online" (Science, 2018)
- **THE foundational paper.** 126K cascades, 3M users
- False news reaches more people, penetrates deeper, spreads faster
- NOT because of bots — humans spread falsehood faster
- Novelty and emotional reactions (fear, surprise) drive sharing

### 6. "Information Mutation in Gossip Networks" — Kaswan & Ulukus, UMD 2023
- **URL:** https://arxiv.org/abs/2305.04913
- **Method:** Stochastic hybrid systems. Mutation probability p at each hop.
- **Key result:** Very high or very low gossip rates curb misinfo. Moderate rates = worst case.
- Mathematical framework for understanding WHY 17 channels with moderate engagement is optimal for misinfo spread

### 7. "Drift Diffusion Model for (Mis)information Sharing" — Alvarez-Zuzek et al., 2024
- People instinctively share misleading news. Rational thinking curbs it.
- Older, more cautious users share less.
- Limiting followers = most effective containment.

### 8. "Conceptualizing the Evolving Nature of Computational Propaganda" — Annals of Communication, 2025
- **URL:** https://academic.oup.com/anncom/article/49/1/45/8078344
- Computational propaganda as complex adaptive system with feedback loops
- Shift to Telegram/WhatsApp. Nanoinfluencers replacing bots.
- Causal loop diagram modeling

## Tier 3: Cross-Lingual Claim Detection

### 9. "Cross-Lingual Debunked Narrative Retrieval" — Singh et al., Sheffield 2024
- **URL:** https://ceur-ws.org/Vol-4070/paper1.pdf
- MMTweets dataset. Cross-lingual retrieval of debunked claims.
- Same false claim persists in other languages months after debunking.

### 10. "Claim Detection for Automated Fact-checking" — Panchendrarajan & Zubiaga, 2024
- **URL:** https://arxiv.org/abs/2401.11969
- Comprehensive survey. XLM-R for cross-lingual. Botness feature improves detection.

### 11. MultiClaim Dataset — Pikuliak et al.
- 28K posts in 27 languages, 206K fact-checks in 39 languages
- The training dataset for cross-lingual claim matching

### 12. "Multilingual vs Crosslingual Retrieval of Fact-Checked Claims" — Zenodo, Jan 2026
- **URL:** https://zenodo.org/records/18108635
- 47 languages, 283 language combinations
- LLM-based re-ranking achieves best results

## Tier 4: Detection Methods

### 13. "Structure-aware Propagation Generation with LLMs" — EMNLP Findings 2025
- **URL:** https://aclanthology.org/2025.findings-emnlp.714/
- LLMs generate synthetic propagation for training detectors
- Works even with incomplete propagation data

### 14. "Blessing or Curse? GenAI and Fake News" — arXiv 2024
- **URL:** https://arxiv.org/html/2404.03021v1
- Comprehensive 2024 survey. BERT, GPT, multimodal detection.
- The paradox: same tools that create disinfo can detect it.

## Implementation Priority for EstWarden

1. **PLMSE metric** (#1) — implement on Telegram data. No deps. Pure math. Language-independent.
2. **Cross-lingual claim matching** (#4, #9) — use Gemini embeddings + pgvector. Match claims across UK/RU/EN/DE.
3. **Community structure features** (#3) — extract modularity/conductance from signal clusters. Predict fabrication from topology.
4. **Claim drift auditor** (#2) — LLM-based comparison of source vs amplified claims. Detect fabrication per hop.
5. **Cascade velocity math** (#6) — model optimal intervention timing based on gossip rate math.
