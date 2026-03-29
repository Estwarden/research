# PsyOp Detection Toolkit

Platform-agnostic detection of psychological operations, bot networks, and
coordinated inauthentic behavior. Trained on Telegram data from the
Russia-Ukraine war (2022-2026) because it's the richest open corpus available,
but the techniques apply to any platform with posts, timestamps, forwarding
graphs, and user metadata (X/Twitter, VK, Facebook, Reddit, etc.).

## Thesis

Four years of war produced a massive corpus of Telegram activity. Pro-Russian,
pro-Ukrainian, and bot-operated channels have distinct behavioral fingerprints:
posting cadence, forwarding graphs, reaction patterns, linguistic style, and
coordination signatures. These patterns are not Telegram-specific -- they're
properties of coordinated inauthentic behavior itself.

## Two Models

### Model 1: Cluster Classifier

**Input:** Vector representation of a narrative cluster. Platform-agnostic
features -- anything with posts, timestamps, and a sharing/forwarding graph
produces the same feature space.

| Feature Group | Platform-Agnostic | Source on Telegram |
|---------------|-------------------|--------------------|
| Posting cadence distribution | Post timestamps | `post.date` |
| Forwarding/repost graph structure | Share/repost edges | `post_fwd.csv` |
| Source diversity (unique accounts) | Unique author count | `peer_id` |
| Linguistic markers (propaganda, hedging) | Post text | `post.message` |
| Temporal coordination score | Cross-account timing correlation | Timestamps |
| Engagement pattern (views, reactions) | View/like counts | `post.views`, `post.forwards` |

**Output:** Cluster type label:
- `psyop` -- Coordinated information operation (state-directed or mercenary)
- `legit_narrative` -- Organic news coverage, editorial commentary
- `grey_zone` -- Amplified organic content, engagement farming, unclear intent
- `bot_network` -- Automated posting cluster, fake channel network

### Model 2: Comment Bot & Trollfarm Detector

**Input:** Individual message + user context. Same features work on any
platform with user post history and timestamps.

| Feature Group | Platform-Agnostic | What it catches |
|---------------|-------------------|-----------------|
| Inter-message timing distribution | Any post timestamps | Bots: inhuman regularity |
| Activity hour heatmap | Any post timestamps | Trollfarms: 8h shift blocks |
| Response latency to trigger topics | Reply timestamps | Bots: instant. Trollfarms: coordinated lag |
| Vocabulary diversity (type-token ratio) | Any text | Bots: low diversity. Trollfarms: talking-point clusters |
| Template reuse (MinHash fingerprint) | Any text | Bot networks reuse templates with minor variation |
| Account age vs activity ratio | Account metadata | Fake accounts: young + hyperactive |

**Output:**
- `bot` -- Automated account (scripted posting, inhuman cadence)
- `trollfarm` -- Human-operated coordinated account (talking points, shift patterns)
- `organic` -- Genuine user

## Plan

1. **Hoard the data** -- Combine existing academic datasets + scrape gaps
2. **Experiment** -- Behavioral analysis, ML classifiers, fine-tuned small LLMs
3. **Make conclusions** -- What works, what doesn't, what's deployable

## Available Datasets

### Tier 1: Production-Ready (large, labeled, downloadable)

| Dataset | Size | Coverage | Labels | URL |
|---------|------|----------|--------|-----|
| **Kyrychenko War Channels** | 79.5M posts, 66K channels, 18.2M forwards | 2015-2024 | Leiden clusters (8), pro-RU/pro-UA/neutral side labels, fake flag, toxicity score | [zenodo.org/16949193](https://zenodo.org/records/16949193) |
| **EPFL Propaganda Dataset** | 6GB dataset + embeddings + trained models | 2022-2024 | Propaganda binary labels per post, annotated by researchers | [zenodo.org/14736756](https://zenodo.org/records/14736756) |
| **TGDataset (Sapienza)** | 120K+ channels, metadata snapshots | 2021-2025 | Channel categories, network structure | [github.com/SystemsLab-Sapienza/TGDataset](https://github.com/SystemsLab-Sapienza/TGDataset) |

### Tier 2: Supplementary (smaller, partial labels, specific focus)

| Dataset | Size | Coverage | Focus | URL |
|---------|------|----------|-------|-----|
| VoynaSlov | Multi-platform (Telegram + VK + Twitter) | Feb-May 2022 | Topic modeling, first months of invasion | [github.com/chan0park/VoynaSlov](https://github.com/chan0park/VoynaSlov) |
| WarNews | RU + UA channel posts (JSON) | Feb-Mar 2022 | Early war narratives | [github.com/Aleksandr-Simanychev/WarNews](https://github.com/Aleksandr-Simanychev/WarNews) |
| tg-misinfo-data | RU news/propaganda channels | Feb-Jun 2022 | Misinformation, NLP | [github.com/yarakyrychenko/tg-misinfo-data](https://github.com/yarakyrychenko/tg-misinfo-data) |
| z-words-collector | Pro-Russian Z channels | Ongoing | Archival scraper, Docker-based | [github.com/anandhuabp/z-words-collector](https://github.com/anandhuabp/z-words-collector) |
| Destructive Texts Corpus | RU Telegram samples | 2023-2024 | Destructive/extremist content | [github.com/alexxromanov/destructive_texts_corpus](https://github.com/alexxromanov/destructive_texts_corpus) |

### Tier 3: Reference (papers with methods but limited/no public data)

| Paper | Key Finding | Data | URL |
|-------|-------------|------|-----|
| "Telegram as a Battlefield" (ICWSM 2025) | Kremlin narrative evolution, volume analysis | 2022-2024, channels listed but data not public | [arxiv.org/2501.01884](https://arxiv.org/abs/2501.01884) |
| "Russian military bloggers" (PMC 2025) | Milblogger corpus + dataset | Restricted access | [PMC/12545825](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545825/) |
| "Disinformation in suspicious channels" (arXiv 2025) | Automated disinfo detection pipeline | Method paper | [arxiv.org/2503.05707](https://arxiv.org/abs/2503.05707) |
| "Large-scale coordinated activity" (npj Complexity 2025) | Multilingual CIB detection on Telegram | 2024 US election focus | [nature.com/s44260-025-00056-w](https://www.nature.com/articles/s44260-025-00056-w) |
| "Propaganda-Spreading Accounts" (EPFL 2024) | 97.6% accuracy propaganda detector using SBERT + DNN | Dataset on Zenodo (Tier 1) | [arxiv.org/2406.08084](https://arxiv.org/abs/2406.08084) |
| OpenMinds Kremlin Connection | 3,600+ channels, 24,500 audience-overlap links | Network map, not raw data | [openminds.ltd](https://www.openminds.ltd/reports/the-kremlin-connection-mapping-telegram-networks-in-russia-ukraine-and-belarus) |
| Atlantic Council Bot Report | 3,634 bot accounts in occupied Ukraine | Indicators listed, data not public | [atlanticcouncil.org](https://www.atlanticcouncil.org/in-depth-research-reports/report/report-russian-bot-networks-occupied-ukraine/) |

## What's Missing (Gaps to Fill)

1. **Chat/comment data** -- All datasets are channel posts. No public dataset of Telegram group chat messages or comment sections where bots are most active.
2. **Behavioral metadata at scale** -- View count timeseries, reaction patterns over time (not just snapshots). The Kyrychenko dataset has views/forwards per post but not temporal view curves.
3. **Bot labels** -- Kyrychenko has `fake` channel flag but no per-account bot labels in chats. Atlantic Council identified 3,634 bots but data isn't public.
4. **2024-2026 data** -- Kyrychenko stops at Mar 2024. Two years of evolution missing.
5. **Cross-platform links** -- Telegram -> Twitter/X -> VK forwarding chains.

## Detection Approaches

### What works (from literature)

| Technique | Accuracy | Source | Notes |
|-----------|----------|--------|-------|
| SBERT embeddings + 3-layer DNN | 97.6% | EPFL (Kireev 2024) | Propaganda detection from trigger-reply pairs |
| LLM+GNN fusion (LGB framework) | +10.95% over baselines | arxiv 2406.08762 | Best for dense networks; LLM better for isolated nodes |
| Graph-only (friend network) | AUC > 0.9 | VKontakte study | Language-independent, cheap compute |
| Behavioral patterns (timing, posting cadence) | High recall, moderate precision | Atlantic Council | Bots have distinctive timing signatures |
| PLMSE cascade shape | p=0.0001 | "Signals of Propaganda" | Power-law fit distinguishes political from organic |
| Forwarding graph analysis | Structural | OpenMinds | Audience overlap reveals hidden coordination |

### What to try

| Approach | Why | Compute | Data Needed |
|----------|-----|---------|-------------|
| **Fine-tune small LLM (Qwen2.5-3B / Gemma-3-4B)** on propaganda labels | EPFL dataset has labels + embeddings ready | 1x GPU, hours | EPFL Zenodo dataset |
| **Temporal behavioral classifier** (XGBoost on posting patterns) | Bot cadence is distinctive, no NLP needed | CPU only | Kyrychenko timestamps + forwards |
| **Graph Neural Network** on forwarding graph | Coordinated networks have structural signatures | 1x GPU | Kyrychenko post_fwd.csv (18.2M edges) |
| **RAG fact-checker** (small LLM + known-claims DB) | Ground claims against verified facts | 1x GPU + pgvector | EPFL labels + EUvsDisinfo |
| **Ensemble: behavioral + content + network** | Multi-signal beats single-signal always | Combined | All datasets merged |

## Project Structure

```
telegram-psyop/
  data/
    raw/          # Downloaded datasets (gitignored)
    processed/    # Cleaned, merged, feature-extracted
    labels/       # Ground truth labels from all sources
  scripts/        # Data download, preprocessing, scraping
  notebooks/      # Research experiments
  models/         # Trained model weights (gitignored)
  output/         # Results, metrics, figures
```

## Experiment Roadmap

### Phase 1: Data Assembly (week 1-2)

| # | Task | Input | Output |
|---|------|-------|--------|
| E-01 | Download Kyrychenko dataset (49GB) | Zenodo | `data/raw/kyrychenko/` |
| E-02 | Download EPFL propaganda dataset (6GB) | Zenodo | `data/raw/epfl/` |
| E-03 | Download supplementary datasets | GitHub repos | `data/raw/supplementary/` |
| E-04 | Merge channel metadata + Leiden labels | All sources | `data/processed/channels_unified.csv` |
| E-05 | Extract behavioral features from 79.5M posts | Kyrychenko posts | `data/processed/behavioral_features.parquet` |
| E-06 | Build forwarding graph | post_fwd.csv (18.2M edges) | `data/processed/forwarding_graph.npz` |
| E-07 | Scrape 2024-2026 gap for key channels (Telethon) | Channel list from EstWarden | `data/raw/scraped_2024_2026/` |

### Phase 2: Cluster Classifier Experiments (week 2-5)

Goal: input = cluster vector, output = {psyop, legit_narrative, grey_zone, bot_network}

| # | Experiment | Method | Expected Signal |
|---|-----------|--------|-----------------|
| E-10 | Cluster feature extraction | Aggregate per-cluster: posting cadence, forwarding density, source diversity, linguistic markers | Feature matrix for all Leiden clusters |
| E-11 | Baseline cluster classifier | XGBoost on cluster features, Kyrychenko `side` + `score` as labels | Structural features alone predict cluster type |
| E-12 | Forwarding graph embeddings | GraphSAGE on forwarding graph -> per-channel embeddings -> cluster mean | Network structure encodes coordination |
| E-13 | Content embeddings | Fine-tune Qwen2.5-3B or multilingual-e5 on EPFL propaganda labels -> per-post vectors -> cluster mean | Propaganda content adds signal beyond structure |
| E-14 | PLMSE per cluster | Power-law cascade shape metric | Psyop clusters have lower PLMSE (more power-law) |
| E-15 | Ensemble cluster classifier | Combine E-11 structural + E-12 graph + E-13 content + E-14 PLMSE | Multi-signal beats single-signal |
| E-16 | RAG narrative tracker | pgvector claim DB + small LLM -> track claim mutations across cluster channels | Identify fabrication chains within clusters |

### Phase 3: Comment Bot & Trollfarm Detector (week 4-7)

Goal: input = chat message + context, output = {bot, trollfarm, organic}

| # | Experiment | Method | Expected Signal |
|---|-----------|--------|-----------------|
| E-20 | Behavioral feature extraction | Per-user: inter-message timing, hour-of-day distribution, response latency, vocabulary diversity | Bots: regular cadence. Trollfarms: shift patterns (8h blocks) |
| E-21 | Temporal classifier | XGBoost on behavioral features only (no NLP) | Timing alone detects bots at high recall |
| E-22 | Content classifier | SBERT embeddings + DNN (replicating EPFL 97.6% approach) | Propaganda reply patterns are distinctive |
| E-23 | Template detection | MinHash / n-gram fingerprinting for message reuse | Bot networks reuse templates with minor variations |
| E-24 | Shift pattern detection | Fourier transform on per-user activity timeseries | Trollfarm workers have periodic shift patterns |
| E-25 | Ensemble comment classifier | Behavioral + content + template + shift features | Combined model for bot/trollfarm/organic |

### Phase 4: Conclusions (week 7-8)

| # | Deliverable |
|---|------------|
| E-30 | Accuracy comparison: which technique works for which detection task |
| E-31 | Trained cluster classifier (packaged for inference, ONNX or torchscript) |
| E-32 | Trained comment detector (same) |
| E-33 | False positive analysis on neutral/organic channels and genuine users |
| E-34 | Writeup: what's deployable, compute requirements, what needs more data |
| E-35 | Integration spec: how these models feed into EstWarden pipeline |
