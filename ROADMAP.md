# Research Roadmap

Prioritized plan for new research. Each item has a clear deliverable, prerequisite,
and estimated effort. See [RESEARCH-SPECS.md](RESEARCH-SPECS.md) for the status of
completed work.

**Guiding principle:** Fix infrastructure before algorithms. Accumulate labeled data
before optimizing thresholds. Deploy simple things that work before complex things
that might.

---

## Phase 0: Foundations (now -- 2 weeks)

Infrastructure and data fixes that unblock everything else. No new research required.

### F-01: Fix dead collectors
- **What:** Restore ACLED, IODA, Telegram, ADS-B collectors. Debug Sentinel-2 (dead since Mar 14).
- **Why:** 76% of days are DEGRADED. No formula fix matters if inputs are missing.
- **Deliverable:** All 11 CTI sources reporting daily. Collector uptime dashboard.
- **Prerequisite:** None. This is prerequisite for everything.
- **Effort:** Ops work, not research. 2-3 days.
- **Tracks:** Q-001, Q-002, S-005

### F-02: Expand watchlist
- **What:** Add 11 channels identified in the Bild map gap analysis. Deploy YAML configs from `bild-map-watchlist-gap.md`.
- **Why:** 40% watchlist coverage on a real campaign is unacceptable.
- **Deliverable:** 11 new channel configs deployed. Coverage of Bild-map-style campaigns > 80%.
- **Prerequisite:** None.
- **Effort:** Config changes, <1 day.
- **Tracks:** O-001

### F-03: Add Baltic media feeds
- **What:** Add ERR.ee (Estonian), LSM.lv (Latvian), 15min.lt (Lithuanian) RSS feeds.
- **Why:** ET/LV/LT embedding quality is too sparse to validate (nb34). Need >= 50 clustered signals per language.
- **Deliverable:** 3+ new RSS collectors. Baltic-language signal volume doubles within 2 weeks.
- **Prerequisite:** None.
- **Effort:** Config + collector setup, 1 day.
- **Tracks:** Q-003

### F-04: Fix category metadata
- **What:** 20K signals missing `category` field. Backfill from source_id mapping.
- **Why:** Fisher pre-screen and narrative velocity depend on `state_ratio`, which requires category.
- **Deliverable:** <1% of signals missing category.
- **Prerequisite:** None.
- **Effort:** DB query + backfill script, 1 day.
- **Tracks:** D-002, D-003

---

## Phase 1: Validated Improvements (weeks 2-6)

Research that extends proven methods and accumulates the labeled data needed for Phase 2.

### R-35: Moderate Weight Recalibration
- **What:** Find signal weight total ~45 (between broken 24 and original 72). Keep FIMI share at ~46%.
- **Why:** VALIDITY.md showed 72->24 kills the algorithm, but 72 overweights dead/noisy sources. Need a middle path.
- **Deliverable:** New weight vector validated on 90+ days of corrected algorithm data. Notebook `35_moderate_weights.py`.
- **Prerequisite:** F-01 (stable collectors for >= 2 weeks).
- **Effort:** 2-3 days. Reuse autoresearch optimizer with constrained search space.
- **Tracks:** R-006, R-007

### R-36: PLMSE Cascade Shape Metric
- **What:** Implement Power Law MSE from "Signals of Propaganda" (PLOS ONE 2025). Compute PLMSE for every cluster.
- **Why:** Language-independent, no ML required, p=0.0001 discrimination between political manipulation and organic cascades. Zero dependency on labeled data.
- **Deliverable:** Notebook `36_plmse_cascade.py`. PLMSE computed for all clusters in `cluster_members.csv`. Distribution comparison: hostile-labeled vs clean.
- **Prerequisite:** None (pure math on existing data).
- **Effort:** 2 days.
- **Tracks:** L-001, D-009

### R-37: Fabrication Same-Event Gate
- **What:** Add cosine similarity check between root and downstream signal titles before fabrication scoring. Skip pairs with similarity < 0.5.
- **Why:** nb31 showed score-10 alerts are DIFFERENT EVENTS, not fabrication. The detector conflates topic drift with falsification.
- **Deliverable:** Notebook `37_fabrication_gate.py`. Precision/recall with and without the gate. Production-ready threshold.
- **Prerequisite:** None.
- **Effort:** 1-2 days.
- **Tracks:** D-008

### R-38: Labeled Campaign Dataset
- **What:** Build a labeled dataset of 50+ hostile campaigns using EUvsDisinfo case database + manual review. Cross-reference with existing cluster data.
- **Why:** Fisher (D-002) needs 33+ hostile clusters. Narrative velocity (D-003) needs 30+ labeled narratives. Everything is blocked on this.
- **Deliverable:** `data/labeled_hostile_campaigns.csv` with columns: cluster_id, narrative_tag, hostile (bool), evidence_source, labeler.
- **Prerequisite:** F-04 (category metadata).
- **Effort:** 3-5 days of research + manual labeling.
- **Tracks:** D-002, D-003, D-009, L-003

### R-39: AIS Tiered Scoring
- **What:** Split AIS into Tier 1 (defense_osint: alert count, sensitive to naval activity) and Tier 2 (raw volume: binary detection only).
- **Why:** nb33 showed 4x throughput swings from collector instability. Raw volume is noise; defense-tagged signals carry information.
- **Deliverable:** Notebook `39_ais_tiers.py`. Per-tier CTI contribution analysis. Recommended tier weights.
- **Prerequisite:** F-01 (AIS collector stabilized for >= 14 days).
- **Effort:** 1-2 days.
- **Tracks:** Q-002

---

## Phase 2: New Detection Capabilities (weeks 6-14)

Research that builds new detection methods. Requires Phase 1 labeled data.

### R-40: Fisher + Hawkes Revalidation
- **What:** Revalidate Fisher discriminant with Hawkes BR as third feature on the expanded labeled dataset (R-38).
- **Why:** F1=0.92 did not replicate at N=30. Hawkes BR (p=0.04) may recover it. But needs N>=33 hostile for p<0.01.
- **Deliverable:** Notebook `40_fisher_hawkes.py`. Updated Fisher coefficients. Bootstrap 95% CI. LOO F1. Power analysis.
- **Prerequisite:** R-38 (labeled dataset with >= 33 hostile clusters).
- **Effort:** 2-3 days.
- **Tracks:** D-002, D-004

### R-41: Origin-Agnostic Velocity
- **What:** Remove RU-origin gate from narrative velocity and cross-category amplification detection. Test on the Bild map case and other non-RU campaigns.
- **Why:** The #1 architectural gap. The Bild map was missed because velocity is RU-only.
- **Deliverable:** Notebook `41_origin_agnostic_velocity.py`. False positive rate on organic non-RU coverage. Precision/recall on labeled hostile campaigns.
- **Prerequisite:** R-38 (labeled dataset), F-02 (expanded watchlist).
- **Effort:** 2-3 days.
- **Tracks:** O-002, D-003

### R-42: Mutation Detection Prototype
- **What:** Build claim extraction + comparison pipeline. For each cluster, extract verifiable claims from root signal, compare to downstream signals, score fabrication rate.
- **Why:** The core capability missing from the Bild map case. Detects distortion-as-a-service (evolving-disinfo-patterns.md pattern #1).
- **Deliverable:** Notebook `42_mutation_detection.py`. Claim extraction via regex heuristics (Phase 1) and LLM (Phase 2). Misinformation Index per cluster.
- **Prerequisite:** R-37 (same-event gate), F-02 (expanded watchlist).
- **Effort:** 4-5 days.
- **Tracks:** O-003, D-010, L-004

### R-43: Community Structure Classification
- **What:** Extract modularity, conductance, and degree distribution from cluster propagation graphs. Train logistic regression on labeled cascades.
- **Why:** TIDE-MARK paper: structure alone predicts fake vs real at AUC 0.83, no content analysis needed.
- **Deliverable:** Notebook `43_community_structure.py`. Per-cluster structural features. Classifier AUC on labeled dataset.
- **Prerequisite:** R-38 (labeled dataset with cascade structure).
- **Effort:** 3-4 days.
- **Tracks:** L-003, D-009

### R-44: Regex FIMI for Baltic Languages
- **What:** Extend hedging/amplification regex patterns from RU/EN to ET/LV/LT.
- **Why:** nb29 regex covers RU/EN only. Baltic-language disinformation is a growing vector.
- **Deliverable:** Notebook `44_fimi_regex_baltic.py`. Patterns for ET/LV/LT. Precision on Baltic-language clusters.
- **Prerequisite:** F-03 (Baltic media feeds producing data).
- **Effort:** 2-3 days.
- **Tracks:** D-005

---

## Phase 3: System Integration (weeks 14-26)

Turning validated research into production capabilities.

### R-45: Milbase Fusion Engine
- **What:** Rebuild the deleted Dempster-Shafer fusion engine. Combine satellite (30%), OSINT (25%), FIRMS (15%), GDELT (15%), ACLED (10%), milwatch (5%) into per-site threat scores.
- **Why:** Each source reports independently with no combined threat picture. FIRMS is the only working source.
- **Deliverable:** Notebook `45_milbase_fusion.py`. Fusion algorithm. Retroactive scoring of known events (Luga deployment, Pskov exercises).
- **Prerequisite:** F-01 (Sentinel-2 and FIRMS collectors working), S-003 (CCDC breakpoints).
- **Effort:** 5-7 days.
- **Tracks:** S-005

### R-46: Autoresearch Phase 2
- **What:** Run the LLM-agent optimization loop (autoresearch/run.sh) with structural improvements to `backtest.py`: source-specific thresholds, time-of-week weighting, exponential decay, conditional cross-source logic.
- **Why:** Phase 1 optimized parameters. Phase 2 optimizes the algorithm structure itself.
- **Deliverable:** Updated `backtest.py` with measurably improved eval_score (>= 0.5% per commit). Git history of experiments.
- **Prerequisite:** R-35 (stable weight vector), F-01 (90+ days of data under corrected algorithm).
- **Effort:** Ongoing, agent-driven. Setup: 1 day.
- **Tracks:** R-007

### R-47: Threshold Recalibration v2
- **What:** Re-run threshold optimization on 90+ days of data under the corrected algorithm (R-35 weights, fixed collectors, cleaned FIMI).
- **Why:** R-007 was calibrated on 50 days with broken inputs. Need clean data and larger sample.
- **Deliverable:** Notebook `47_threshold_v2.py`. New YELLOW/ORANGE/RED thresholds with 3-fold CV. Per-region thresholds where data supports (>= 30 days per region).
- **Prerequisite:** R-35 deployed, F-01 collectors stable for 90+ days.
- **Effort:** 2-3 days.
- **Tracks:** R-007

### R-48: Cross-Lingual Claim Matching
- **What:** Implement embedding-based claim retrieval across UK/RU/EN/DE using Gemini embeddings + pgvector. Match new claims against fact-checked database.
- **Why:** ClaimCheck paper achieves SOTA cross-lingual retrieval. Closes the "no fact-checking module" gap from literature review.
- **Deliverable:** Notebook `48_claim_matching.py`. Retrieval accuracy on EUvsDisinfo test set.
- **Prerequisite:** R-42 (claim extraction pipeline), Q-003 (embedding quality validated).
- **Effort:** 4-5 days.
- **Tracks:** L-002

---

## Phase 4: Advanced Research (6-12 months)

Long-term investigations requiring significant data accumulation or compute resources.

| ID | Research | What | Prerequisite | Effort |
|----|----------|------|-------------|--------|
| R-49 | Multivariate Hawkes | Per-category directed excitation graphs (ru_state -> ru_proxy vs ru_state -> trusted) | R-40 (Hawkes validated) | 5-7 days |
| R-50 | Self-tuning thresholds | Bayesian optimization of CTI thresholds with online learning | R-47 (threshold v2), 6+ months of data | 5-7 days |
| R-51 | Siamese change detection | Trained model for satellite imagery change pairs | Labeled change pairs (~2h manual), GPU access | 7-10 days |
| R-52 | Narrative-level clustering | Embedding-based narrative grouping replacing keyword classification | R-38 (labeled narratives), F-03 (Baltic feeds) | 5-7 days |
| R-53 | Gossip rate intervention modeling | Optimal timing for counter-narrative deployment based on Kaswan & Ulukus 2023 | R-36 (PLMSE), R-41 (velocity) | 3-5 days |
| R-54 | Platform expansion | Facebook, TikTok, VKontakte monitoring collectors | Collector infrastructure, API access | 10+ days |
| R-55 | Methodology paper | Publish research methodology with 12+ months of validated production data | All tracks validated | 2-4 weeks |

---

## Timeline Summary

```
Month 1          Month 2          Month 3          Month 4-6
|--- Phase 0 ---|--- Phase 1 ----|--- Phase 2 -----|--- Phase 3 ----->
F-01 collectors   R-35 weights     R-40 Fisher v2    R-45 milbase fusion
F-02 watchlist    R-36 PLMSE       R-41 origin-free  R-46 autoresearch v2
F-03 Baltic feeds R-37 fab gate    R-42 mutations    R-47 thresholds v2
F-04 categories   R-38 labeling    R-43 community    R-48 claim matching
                  R-39 AIS tiers   R-44 Baltic regex
```

**Critical path:** F-01 -> R-35 -> R-47 (CTI recalibration requires 90+ days of stable data, so start the clock on F-01 immediately).

**Highest ROI items:**
1. F-01 (fix collectors) -- unblocks everything, costs nothing.
2. R-36 (PLMSE) -- zero dependencies, scientifically validated, closes a detection gap.
3. R-38 (labeled dataset) -- unblocks 4 downstream research items.
4. F-02 (watchlist) -- config change that would have caught the Bild map campaign.
