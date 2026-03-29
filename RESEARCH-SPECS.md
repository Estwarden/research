# Research Specifications

Status of all research tracks as of 2026-03-29.
Read [VALIDITY.md](methodology/VALIDITY.md) before acting on any finding.

---

## Track 1: CTI Formula Diagnostics

**Goal:** Fix the permanent-YELLOW bug in the Composite Threat Index.

**Status:** Diagnostics COMPLETE. Prescriptive fixes PARTIALLY VALIDATED.

| ID | Research | Notebooks | Finding | Confidence |
|----|----------|-----------|---------|------------|
| R-001 | CTI decomposition | nb06, nb08, nb12 | FIMI sub-components cause permanent YELLOW (80% of active days) | HIGH (N=134 daily scores) |
| R-002 | FIMI floor analysis | nb14 | Campaigns are the #1 inflator (6.59 CTI pts avg, 72% of max) | HIGH (N=37 campaigns) |
| R-003 | Laundering audit | nb15 | 73% of laundering events are noise (domestic RU news, sports) | HIGH (N=147 events) |
| R-004 | Campaign scoring | nb16 | 70% of campaigns lack detection evidence but contribute 73% of severity | HIGH (N=37 campaigns) |
| R-005 | Robust baselines | nb17 | Median+MAD z-scores outperform standard z-scores for all sources | MEDIUM (weak ground truth) |
| R-006 | Weight recalibration | nb18 | Consensus signal weights reduce total from 72 to 24 | LOW -- too aggressive, makes algorithm dead |
| R-007 | Threshold recalibration | nb19 | YELLOW=7.9 optimized on 50 days with 13 transitions | LOW -- calibrated to broken algorithm |

**Deployed to production:** R-003 laundering filter, R-004 campaign evidence gate, R-005 robust baselines, DEGRADED flag, dead collector weight=0.

**DO NOT deploy:** R-006 consensus weights (72->24), R-007 YELLOW=7.9.

**Open questions:**
- What is the correct signal weight total? VALIDITY.md suggests ~45, not 24 or 72.
- Per-region thresholds have <10 data points each. Need 90+ days under corrected algorithm.
- Self-referential ground truth: optimized against labels from the old (broken) algorithm.

---

## Track 2: Campaign Detection

**Goal:** Detect hostile disinformation campaigns across languages and platforms.

**Status:** Architecture deployed. Statistical validation INSUFFICIENT.

| ID | Research | Notebooks | Finding | Confidence |
|----|----------|-----------|---------|------------|
| D-001 | Semantic clustering | nb03, nb26 | Cosine 0.75 optimal; two-pass clustering fixes mega-clusters | HIGH (validated on Narva Republic chain) |
| D-002 | Fisher pre-screen | nb25 | `score = 0.670*state_ratio + 0.742*fimi_score` | LOW -- F1=0.615 at N=30 (did NOT replicate F1=0.92) |
| D-003 | Narrative velocity | nb27 | Week-over-week state_ratio increase detects weaponization | LOW -- F1=1.00 on N=8 is statistically meaningless |
| D-004 | Hawkes coordination | nb24 | State-heavy clusters: BR=0.53 vs clean: 0.22 (p=0.04) | MEDIUM (N=281 clusters, directional) |
| D-005 | FIMI regex | nb29 | Hedging + amplification regex pre-screens 80% of clusters without LLM | MEDIUM (N=30, language-limited to RU/EN) |
| D-006 | Co-coverage network | nb30 | State media Jaccard=0.26 vs trusted=0.16 (63% coordination premium) | MEDIUM (structural, stable) |
| D-007 | IBI prompt test | nb28 | Intent-based prompting over-triggers on geopolitical coverage | HIGH (current factual prompt is better) |
| D-008 | Fabrication stability | nb31 | Score conflates topic drift with fabrication; needs same_event gate | HIGH (structural flaw confirmed) |
| D-009 | Cascade topology | nb04 | Community structure predicts fake vs real (AUC 0.83 in literature) | NOT VALIDATED (no labeled data) |
| D-010 | Claim drift | nb03 | Misinformation Index measures fabrication per hop | NOT VALIDATED (prototype only) |

**Deployed to production:** D-001 (cosine 0.75, two-pass clustering), D-007 (keep current prompt).

**Blocked on data:**
- D-002 needs 33+ hostile-labeled clusters for p<0.01.
- D-003 needs 30+ labeled narratives.
- D-009 needs labeled cascade dataset (100+ events).

**Open questions:**
- Can Fisher pre-screen recover with Hawkes BR as a third feature?
- Is embedding-based narrative clustering better than keyword classification?
- Can regex FIMI extend to ET/LV/LT languages?

---

## Track 3: Satellite & Milbase Monitoring

**Goal:** Detect military activity changes at Russian bases near the Baltic via free satellite imagery.

**Status:** Methods validated. Pipeline BROKEN (Sentinel-2 collector dead since Mar 14).

| ID | Research | Notebooks | Finding | Confidence |
|----|----------|-----------|---------|------------|
| S-001 | Seasonal baselines | nb20 | 3-year NDVI/BSI weekly profiles; deseasonalized z-scores | HIGH (GEE-validated) |
| S-002 | Isolation Forest | nb21 | Per-site anomaly detection; ship/equipment detector | MEDIUM (acts as proxy, not direct military detection) |
| S-003 | CCDC breakpoints | nb22 | 6 breakpoints in 3 years; 1 ISW match (Luga, -2 days) | MEDIUM (N=6, 1 confirmed) |
| S-004 | Temporal change | nb23 | Year-over-year same-month is correct baseline, not 30-day rolling | HIGH (snowmelt false positive eliminated) |
| S-005 | Milbase fusion | nb32, methodology | No fusion engine exists (Dempster-Shafer deleted in migration) | N/A (gap identified) |

**Deployed:** S-001 seasonal profiles, S-004 YoY baseline method.

**Blocked:** Sentinel-2 collector dead. FIRMS is the only working source. No fusion engine.

**Open questions:**
- Can CCDC detect exercises shorter than 2 weeks?
- Is SkySat/Maxar viable for Russian sites given Google's restrictions?
- How to fuse satellite + FIRMS + OSINT without the deleted Dempster-Shafer engine?

---

## Track 4: Data Quality & Collector Health

**Goal:** Ensure CTI inputs are reliable enough to produce meaningful scores.

**Status:** Primary bottleneck for all other tracks. 76% of days are DEGRADED.

| ID | Research | Notebooks | Finding | Confidence |
|----|----------|-----------|---------|------------|
| Q-001 | Collector health | nb32 | Only 24% of days have adequate sensor coverage | HIGH (N=50 days) |
| Q-002 | AIS deep dive | nb33 | 4x throughput swings; collector instability, not naval activity | HIGH (N=88 days) |
| Q-003 | Embedding quality | nb34 | EN > RU > UK > ET; LV/LT too sparse to validate | MEDIUM (language-dependent) |
| Q-004 | Burstiness validation | nb05 | Coordination detection NOT validated (p>0.05) | HIGH (insufficient power) |

**Deployed:** DEGRADED flag, dead source weight=0, AIS binary mode.

**Dead collectors (as of Mar 25):** ACLED (0%), IODA (0%), Telegram (20% uptime), ADS-B (76%, military misclassification).

**Open questions:**
- What is the minimum collector uptime to produce a non-DEGRADED score?
- Can AIS be tiered (defense_osint vs raw volume)?
- How to handle regime changes after collector restarts (7-day burn-in proposed)?

---

## Track 5: Origin-Agnostic Detection (GAP)

**Goal:** Detect disinformation regardless of origin country. Currently RU-origin only.

**Status:** NOT STARTED. Identified as the #1 architectural gap by the Bild map case study.

| ID | Research | Source | Gap |
|----|----------|--------|-----|
| O-001 | Watchlist coverage | bild-map-watchlist-gap.md | 6/10 amplifying channels were unmonitored (40% coverage) |
| O-002 | Origin-blind velocity | fabrication-detection-design.md | Narrative velocity is RU-origin gated |
| O-003 | Mutation detection | fabrication-detection-design.md | No claim comparison between root and amplified signals |
| O-004 | View velocity | bild-map-watchlist-gap.md | No cumulative view threshold alerts |
| O-005 | Evolving patterns | evolving-disinfo-patterns.md | 7 new patterns (distortion-as-service, LLM analysis, etc.) not covered |

**Phased plan from fabrication-detection-design.md:**
1. Config: add 11 missing channels to watchlist.
2. Code: origin-agnostic velocity + view alerting.
3. New capability: mutation detection endpoint.
4. Future: LLM-based claim extraction.

---

## Track 6: Scientific Methods (from reading list)

**Goal:** Implement peer-reviewed methods that address known gaps.

**Status:** Literature reviewed. Implementation NOT STARTED.

| ID | Method | Paper | Applicability | Priority |
|----|--------|-------|---------------|----------|
| L-001 | PLMSE metric | Signals of Propaganda (PLOS ONE 2025) | Language-independent cascade shape metric; distinguishes political from organic (p=0.0001) | P1 -- no dependencies, pure math |
| L-002 | Cross-lingual claim matching | ClaimCheck (EMNLP 2025) | Embedding + pgvector retrieval across UK/RU/EN/DE for fact-checking | P2 -- needs embeddings infrastructure |
| L-003 | Community structure classification | TIDE-MARK (PMC 2026) | Modularity/conductance predicts fake vs real (AUC 0.83) | P2 -- needs labeled cascade data |
| L-004 | Claim drift auditor | Maurya et al. (arXiv 2025) | LLM compares source vs amplified claims per hop | P3 -- needs mutation detection pipeline |
| L-005 | Gossip rate modeling | Kaswan & Ulukus 2023 | Models optimal intervention timing based on engagement rate | P4 -- theoretical, low urgency |

---

## Cross-Track Dependencies

```
Collector Health (Track 4)
  |
  v
CTI Formula (Track 1) <--- needs stable inputs before threshold recalibration
  |
  v
Campaign Detection (Track 2) <--- needs labeled data accumulation (months)
  |
  v
Origin-Agnostic (Track 5) <--- needs mutation detection + broadened watchlist
  |
  v
Scientific Methods (Track 6) <--- PLMSE and community structure are independent
  
Satellite (Track 3) <--- blocked on collector recovery, independent otherwise
```

The binding constraint is **data accumulation**: Fisher needs 33+ hostile clusters, narrative velocity needs 30+ labeled narratives, and threshold recalibration needs 90+ days of stable data. No amount of new research can substitute for time.
