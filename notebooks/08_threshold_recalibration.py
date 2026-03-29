#!/usr/bin/env python3
"""
08. Threshold Recalibration
============================

The YELLOW threshold (15.2) was calibrated for the OLD CTI formula which
only had signal z-scores. The new formula added campaigns, fabrication,
laundering, and narrative components. We need new thresholds.

Method: Use CTI history to find where GREEN/YELLOW should split.
"""
import csv
import json
import os
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# Load all data
campaigns = []
with open(f"{DATA}/campaigns_full.csv") as f:
    for row in csv.DictReader(f):
        campaigns.append(row)

# Load CTI history
cti_rows = []
with open(f"{DATA}/threat_index_history.csv") as f:
    for row in csv.DictReader(f):
        row['score'] = float(row['score'])
        row['components'] = json.loads(row['components'].replace("'", '"')) if row['components'] else {}
        cti_rows.append(row)

by_region = defaultdict(list)
for r in cti_rows:
    by_region[r['region']].append(r)

# ================================================================
# 1. SCORE DISTRIBUTION ANALYSIS
# ================================================================
print("=" * 70)
print("1. SCORE DISTRIBUTIONS BY REGION")
print("=" * 70)

for region in sorted(by_region.keys()):
    entries = by_region[region]
    scores = sorted([e['score'] for e in entries])
    n = len(scores)
    if n < 5:
        print(f"\n  {region}: only {n} entries, skip")
        continue
    
    p25 = scores[int(n * 0.25)]
    p50 = scores[int(n * 0.50)]
    p75 = scores[int(n * 0.75)]
    p90 = scores[int(n * 0.90)]
    
    print(f"\n  {region} ({n} entries):")
    print(f"    min={scores[0]:.1f}  P25={p25:.1f}  P50={p50:.1f}  P75={p75:.1f}  P90={p90:.1f}  max={scores[-1]:.1f}")
    
    # Show component contribution at different score levels
    low = [e for e in entries if e['score'] < p50]
    high = [e for e in entries if e['score'] >= p75]
    
    if low:
        avg_low = {k: sum(float(e['components'].get(k, 0)) for e in low)/len(low) 
                   for k in ['security', 'fimi', 'hybrid', 'economic']}
        print(f"    Below median: " + " | ".join(f"{k}={v:.1f}" for k, v in avg_low.items()))
    if high:
        avg_high = {k: sum(float(e['components'].get(k, 0)) for e in high)/len(high) 
                    for k in ['security', 'fimi', 'hybrid', 'economic']}
        print(f"    Above P75:    " + " | ".join(f"{k}={v:.1f}" for k, v in avg_high.items()))

# ================================================================
# 2. COMPONENT BUDGET ANALYSIS
# ================================================================
print("\n" + "=" * 70)
print("2. COMPONENT BUDGET — theoretical max contributions")
print("=" * 70)

# From the CTI code
from cti_constants import TOTAL_WEIGHT  # 110
# But note: energy price also contributes but isn't in the weight constant

# Max possible per component
# Signal z-scores: each source can contribute min(z*10, 100) * (w/110)
# With typical z-scores of 1-2, most sources contribute 1-3 points
# Campaign: min(raw, 100) * (10/110) = max 9.09
# Fabrication: min(total/5, 100) * (8/110) = max 7.27
# Laundering: min(count, 100) * (6/110) = max 5.45
# Narrative: min(count/10, 100) * (4/110) = max 3.64
# GPS jamming: min(rate*200, 100) * (10/110) = max 9.09
# Energy price: min(z*10, 50) * (6/110) = max 2.73

print("""
  Component          Max contribution   Current typical
  ─────────────────  ─────────────────  ─────────────────
  Signal z-scores    ~20 (all sources)  ~2-5
  Campaigns          9.09               8-9 (always near max)
  Fabrication        7.27               5-7 (often near max)
  Laundering         5.45               5.45 (ALWAYS at max)
  Narratives         3.64               2-3
  GPS jamming        9.09               0-2
  Energy price       2.73               0-1
  ─────────────────  ─────────────────  ─────────────────
  TOTAL              ~57                ~25-32
""")

# ================================================================
# 3. THE STRUCTURAL PROBLEM
# ================================================================
print("=" * 70)
print("3. THE STRUCTURAL PROBLEM")
print("=" * 70)

print("""
The FIMI components (campaigns + fabrication + laundering + narratives)
have a theoretical max of 25.45 and a FLOOR of about 15-20 because:

  - Laundering is ALWAYS maxed (5.45) — any week with 100+ state-origin
    cross-category events hits the cap, and that's every normal week.
  
  - Campaigns are nearly always maxed (8-9) — the system detects 10+
    campaigns per week including actor blitz and volume spikes that
    are normal activity.
  
  - Fabrication is usually 5+ — any fabrication alert with >10K views
    and score >=3 contributes significantly.

  - Narratives add 2+ — any 20+ narrative tags in a week.

So the FIMI floor is roughly:
  5.45 (laundering, always maxed) +
  8.00 (campaigns, usually many) +
  3.00 (fabrication, usually some) +
  2.00 (narratives, usually some) =
  ~18.5 MINIMUM

The current YELLOW threshold is 15.2.
FIMI alone has a FLOOR of ~18.5.
The system can NEVER be GREEN.
""")

# ================================================================
# 4. PROPOSED FIXES (from most impactful to least)
# ================================================================
print("=" * 70)
print("4. PROPOSED FIXES")
print("=" * 70)

# Option A: Raise threshold
# Use baltic historical data (most entries)
baltic = by_region.get('baltic', [])
if len(baltic) >= 10:
    baltic_scores = sorted([e['score'] for e in baltic])
    n = len(baltic_scores)
    p50 = baltic_scores[int(n * 0.50)]
    p75 = baltic_scores[int(n * 0.75)]
    p90 = baltic_scores[int(n * 0.90)]
    print(f"\n  Option A: Raise YELLOW threshold")
    print(f"    Baltic score P50={p50:.1f}, P75={p75:.1f}, P90={p90:.1f}")
    print(f"    Set YELLOW = P75 = {p75:.1f} → {round(sum(1 for s in baltic_scores if s >= p75)/n*100)}% YELLOW")
    print(f"    Set YELLOW = P90 = {p90:.1f} → {round(sum(1 for s in baltic_scores if s >= p90)/n*100)}% YELLOW")

# Option B: Cap FIMI sub-components
print(f"\n  Option B: Cap FIMI sub-component contributions")
print(f"    Current: each sub-component can contribute up to ~9 points")
print(f"    Proposed: cap each sub-component at 3 points")
print(f"    FIMI max would be 4 × 3 = 12 instead of 25")
print(f"    This prevents any single noisy component from dominating")

# Option C: Fix laundering definition
print(f"\n  Option C: Fix the laundering detector")
print(f"    Current: 'state origin + 2 categories' = laundering")
print(f"    Problem: Kim Jong Un on a tank is 'laundering'")
print(f"    Fix: require region relevance OR >=3 categories")
print(f"    Impact: reduces laundering from ~147 to ~73 events")

# Option D: Don't count resolved campaigns
resolved_active = [c for c in campaigns if c['status'] == 'RESOLVED']
print(f"\n  Option D: Exclude RESOLVED campaigns from score")
print(f"    Current: resolved campaigns still contribute with 0.2-0.8 decay")
print(f"    {len(resolved_active)} of {len(campaigns)} are RESOLVED")
print(f"    Fix: only score ACTIVE campaigns")

# Option E: Require evidence for campaign scoring  
print(f"\n  Option E: Only score campaigns with detection_method")
evidence_campaigns = [c for c in campaigns 
                      if c.get('detection_method') and int(c['signal_count']) > 0]
print(f"    Only {len(evidence_campaigns)} of {len(campaigns)} have a detection method + signals")

# ================================================================
# 5. RECOMMENDED NEW THRESHOLDS
# ================================================================
print("\n" + "=" * 70)
print("5. RECOMMENDED APPROACH")
print("=" * 70)

print("""
Don't just move the threshold. The algorithm needs structural fixes:

1. FIX LAUNDERING (biggest single fix):
   - Require region relevance for counting
   - OR raise category_count from 2 to 3
   - OR cap laundering contribution at 2.0 instead of 5.45

2. FIX CAMPAIGN SCORING:
   - Only count campaigns with detection_method AND signal_count > 0
   - Don't count RESOLVED campaigns
   
3. FIX FABRICATION REGION FILTER:
   - Only count fabrication alerts relevant to the brand's region

4. THEN recalibrate thresholds on the fixed algorithm.
   Don't raise thresholds on a broken algorithm — that just hides bugs.
   
After fixes 1-3, the FIMI floor should drop from ~18.5 to ~8-12,
which means GREEN becomes possible again and YELLOW means something.
""")
