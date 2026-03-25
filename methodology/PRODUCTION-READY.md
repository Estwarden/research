# Production-Ready Changes from Research

**Updated:** 2026-03-25 (post-validity audit)
**See:** [VALIDITY.md](VALIDITY.md) for full assessment

## ✅ Already deployed to production (2026-03-25)

| Fix | Source | Status |
|-----|--------|--------|
| Robust baselines (median+MAD) | nb17 | In prod since Mar 21 |
| Campaign evidence filter | nb16 | `detection_method IS NOT NULL` + signal_count > 0 |
| Laundering relevance filter | nb15 | `category_count >= 3` + content_regex per region |
| Cluster size cap at 15 | nb12 | In prod |
| Cosine threshold 0.75 | nb06 | In prod |
| Cluster two-pass (>10 need ≥0.82) | nb26 | Deployed 2026-03-25 |
| Campaign auto-resolve (48h stale) | R-004 | Deployed 2026-03-25 |
| DEGRADED flag (<70% sources) | nb18 | Deployed 2026-03-25 |
| Signal weight fixes | VALIDITY.md | telegram_channel, adsb=5, gdelt=2, firms=6, +3 new |
| Dead collector restoration | nb32 | All collectors fixed 2026-03-25 |

## 🟡 Validated concept, insufficient data for thresholds

### Fisher Pre-Screen
Original claim: F1=0.92 at N=13 (Experiment 25).
**Replication (nb25):** F1=0.615 at N=30, bootstrap CI [0.333, 1.000].
**Status:** Concept sound (state_ratio + fimi_score discriminates), but specific
weights and thresholds are NOT validated. Do NOT deploy the -0.7/+0.5 cutoffs.
**Need:** 33+ hostile-labeled clusters for p<0.01.

### Narrative Velocity Alert
Original claim: F1=1.00.
**Reality:** N=8 total (5 hostile, 3 organic). ANY reasonable threshold gives F1≥0.83.
**Status:** The weaponization escalation pattern (0%→10%→59%) is real and documented.
The specific thresholds (0.20, 0.15) are not validated.
**Need:** 30+ labeled narratives.

### Hawkes Branching Ratio
**Status:** Solid metric. BR=0.52 for state clusters vs 0.22 organic (N=281).
Statistical power is moderate. Ready for supplementary use in campaign detection.
Not yet implemented in Go.

### FIMI Regex Detection
**Status:** Interesting. Hedging/omission patterns on N=30 (6 hostile).
Supplement to LLM, don't replace.

## 🔴 Do NOT deploy

| Item | Why |
|------|-----|
| Consensus weights (72→24) | Makes algorithm dead, 30/50 days score=0 |
| YELLOW=7.9 threshold | Calibrated to broken algorithm |
| Per-region thresholds | <10 data points per region |
