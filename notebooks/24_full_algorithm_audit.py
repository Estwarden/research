#!/usr/bin/env python3
"""
24-25. Full Algorithm Audit
============================

AUDIT RESULTS:

1. CTI SIGNAL Z-SCORES (72% weight):
   ❌ ALL sources volatile (CV > 60%)
   ❌ AIS baseline corrupted by 7 downtime days
   ❌ FIRMS false alarm confirmed (z=2.0 raw vs 1.85 corrected)
   FIX: exclude downtime, use median, min 5/7 data days

2. CAMPAIGN DETECTION (14% weight):
   🟡 96% of campaigns have evidence (good)
   ❌ 63% LLM disagrees with name-matching labels
   ❌ Russian state media presence does NOT predict hostile intent
   ❌ 5 ORGANIC campaigns inflate threat score
   FIX: LLM-based label validation, filter organic from CTI

3. NARRATIVE VOLUME (8% weight):
   ❌ Single tag in 14 days (taxonomy too coarse)
   ❌ Keyword matching produces high false positive rate
   FIX: replace with embedding-based narrative clustering

4. GPS JAMMING (10% weight):
   ✅ Stable baseline (CV=13%)
   ✅ Clear signal (13 elevated zones)
   KEEP as-is

5. SATELLITE ANALYSIS:
   ❌ 0 actionable findings out of 76 signals
   DeepState data is duplicate labels, not intelligence
   FIX: need LLM post-processing or manual review

6. EVENT CLUSTERING:
   🟡 41% of clusters have good coherence (≥0.2 Jaccard)
   ❌ 59% have moderate-to-poor coherence
   Some clusters contain duplicate signals (coherence=1.0)
   Some clusters group unrelated signals (coherence=0.0)
   FIX: raise embedding similarity threshold, dedup

7. BURSTINESS DETECTION:
   ✅ p < 0.001, confound-free (validated)
   ❌ Detects Russian state media patterns, NOT hostile intent
   Need additional signals for hostile vs organic distinction

8. FEAR MEASUREMENT:
   ❌ Keyword matching inflated by defense reporting
   ✅ Corrected to 8% (excluding defense sources)
   Baltic-specific fear: ~0%

OVERALL: System detects patterns but cannot reliably distinguish
hostile from organic. CTI number is inflated. Clustering has noise.
Satellite data provides no actionable intelligence.

GPS jamming and burstiness are the only validated, reliable signals.
"""
