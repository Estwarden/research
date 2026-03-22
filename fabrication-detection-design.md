# Design: Origin-Agnostic Fabrication Detection

**Date:** 2026-03-22
**Problem:** Bild map campaign was not detected because (a) origin was non-Russian, (b) fabricated claims weren't in taxonomy, (c) no mutation detection within clusters.
**Goal:** Eliminate manual intervention. Detect fabrication automatically regardless of origin.

## Existing Infrastructure

| Component | Status | Where |
|-----------|--------|-------|
| Signal ingestion | ✅ | `pipeline_api.go` |
| Gemini embeddings | ✅ | `embeddings.go` → `signal_embeddings` table (pgvector) |
| Event clustering | ✅ | `narrative_clusters.go` → `event_clusters` + `cluster_signals` |
| Campaign assembly | ✅ | `process/assemble-campaigns` |
| Narrative velocity | ✅ | `narrative_velocity.go` (RU-origin only) |
| Amplification detection | ✅ | `detect_amplification.py` (keyword taxonomy, RU-origin only) |

## What's Missing

### 1. Cluster Mutation Detection
**Problem:** System clusters similar signals but doesn't detect when later signals in a cluster ADD claims not in earlier signals.

**Design:**
```
For each event_cluster with ≥3 signals:
  1. Get earliest signal (source/root)
  2. Get all subsequent signals
  3. Extract claims from each (LLM or heuristic)
  4. Compare: do later signals contain specific claims 
     (dates, numbers, legal refs, named entities) 
     that DON'T appear in the root signal?
  5. If yes → flag as MUTATION with severity proportional 
     to specificity of added claims
```

**Implementation:** New endpoint `POST /api/v1/detect/mutations`

**Claim extraction heuristics (no LLM needed):**
- Regex for time references: "1-2 months", "60 days", "by summer"
- Regex for legal claims: "law passed", "закон принят", "legislation"
- Regex for certainty markers: "will attack", "final stage", "beschlossene Sache"
- Compare against root signal — if root has question marks and later signals don't → flag

### 2. Cross-Category Velocity
**Problem:** Current velocity detection only watches RU state media acceleration. Needs to watch ALL categories.

**Design:**
```sql
-- Current: only counts ru_state/ru_proxy
COUNT(*) FILTER (WHERE category IN ('ru_state','ru_proxy'))

-- Proposed: count ALL categories, alert on cross-category spread
-- A cluster touching ≥3 different channel categories within 48h = velocity alert
SELECT cluster_id, 
       COUNT(DISTINCT s.metadata->>'category') as category_spread,
       COUNT(*) as total_signals,
       SUM((s.metadata->>'views')::int) as total_views
FROM cluster_signals cs
JOIN signals s ON s.id = cs.signal_id
WHERE s.published_at >= now() - interval '48 hours'
GROUP BY cluster_id
HAVING COUNT(DISTINCT s.metadata->>'category') >= 3
    OR SUM((s.metadata->>'views')::int) > 500000
```

**Implementation:** Modify `narrative_velocity.go` to add origin-agnostic mode.

### 3. View Velocity Alerting
**Problem:** No alerting on cumulative view counts.

**Design:**
```
For each event_cluster active in last 48h:
  total_views = SUM(views across all signals in cluster)
  if total_views > 500K → MEDIUM alert
  if total_views > 1M → HIGH alert
  if total_views > 5M → CRITICAL alert
```

**Implementation:** Add to the existing cluster processing pipeline.

### 4. Automatic Campaign Creation from Mutations
**Problem:** Campaigns require manual creation or RU-origin detection.

**Design:**
```
When a mutation is detected with:
  - ≥3 fabricated claims
  - OR ≥500K total views
  - OR ≥3 channel categories involved
→ Automatically create a campaign:
  - severity = based on view count + claim count
  - confidence = based on mutation specificity
  - summary = auto-generated from cluster root vs mutations
  - signals = all signals in the cluster
```

## Data Flow (proposed)

```
Signals ingested
    ↓
Embed (Gemini → pgvector)
    ↓
Cluster (cosine similarity → event_clusters)
    ↓
[NEW] Mutation Detection (compare root vs later signals)
    ↓
[NEW] Cross-Category Velocity (category spread + view count)
    ↓
[MODIFIED] Campaign Assembly (origin-agnostic, mutation-aware)
    ↓
Dashboard + Alerts
```

## Migration Path

### Phase 1 (quick wins, config only)
- Add 6 missing channels to watchlist
- Deploy collectors for new channels
- Signals start flowing into existing pipeline

### Phase 2 (code changes, no new dependencies)
- Add cross-category velocity to `narrative_velocity.go`
- Add view threshold alerting
- Remove RU-origin requirement from amplification detection

### Phase 3 (new detection capability)
- Build mutation detection (`detect/mutations` endpoint)
- Claim extraction heuristics (regex-based, no LLM)
- Automatic campaign creation from mutations

### Phase 4 (LLM-assisted, future)
- LLM-based claim extraction for higher accuracy
- Semantic comparison between root and amplifying signals
- Confidence scoring based on claim specificity

## Bild Map Case — What Would Have Been Detected

With all phases implemented:

| Phase | Detection | Timing |
|-------|-----------|--------|
| Phase 1 | Signals from @smolii, @Tsaplienko, @Bereza collected | Day 0 |
| Phase 2 | Cross-category velocity alert (3+ categories, 500K+ views) | Day 0 + 6h |
| Phase 3 | Mutation flagged: "1-2 months" added by Smolii (not in root) | Day 0 + 12h |
| Phase 3 | Auto-campaign created: "Baltic invasion fabrication" | Day 0 + 12h |
| Dashboard | Campaign visible, severity HIGH, linked signals | Day 0 + 12h |

**Result: Detected within 12 hours. No manual intervention needed.**
