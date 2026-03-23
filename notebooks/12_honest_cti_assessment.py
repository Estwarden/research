#!/usr/bin/env python3
"""
12. Honest CTI Assessment — what does the score actually measure?
=================================================================

After fixing the FIMI false positives, what does CTI actually tell us?
"""
import csv
import json
import os
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

print("=" * 70)
print("HONEST CTI ASSESSMENT")
print("=" * 70)

print("""
WHAT THE CTI CURRENTLY MEASURES (after today's fixes):

  1. FIMI (0-25 pts, drives 55% of score variance):
     - Active campaigns with evidence (framing analysis, injection, outrage)
     - Fabrication alerts (region-filtered, content-verified)
     - Narrative laundering (3+ categories, region-relevant)
     - Narrative tag volume
     
     HONEST VERDICT: This is the strongest component. Campaign detection
     with framing analysis IS finding real Russian info ops (airspace
     violation doubt-casting, Lukashenko legitimization, NATO weakness
     amplification). When FIMI is high, there IS active hostile activity.

  2. HYBRID (0-25 pts, drives 47% of variance):
     - Signal z-scores weighted by source (gpsjam=12, adsb=10, etc.)
     - GPS jamming severity
     
     HONEST VERDICT: Almost entirely driven by gpsjam. Other sources
     (adsb, ais, firms) contribute noise due to collector instability.
     When hybrid is high, it means gpsjam detected elevated interference
     OR a broken collector produced a random spike. Can't distinguish.

  3. SECURITY (0-25 pts, drives 22% of variance):
     - ADS-B z-scores (weight=10)
     - ACLED conflict z-scores (weight=8)
     
     HONEST VERDICT: Near-zero most of the time. ADS-B has 69% collection
     gaps, ACLED has no data at all. This pillar is non-functional.

  4. ECONOMIC (0-25 pts, drives 30% of variance):
     - Energy price z-scores
     - IODA internet outage z-scores (no data)
     - Business signal z-scores
     
     HONEST VERDICT: Energy price z-scores work correctly when data is
     fresh. IODA has no data. Business is low volume. This pillar
     functions but is weak.

WHAT THE USER SEES:
  - GREEN: no active campaigns + normal gpsjam + normal energy prices
  - YELLOW: either active campaigns OR elevated gpsjam/energy
  - The signal z-score component is mostly noise
  - The useful signal comes from campaign detection + gpsjam

WHAT WOULD MAKE CTI MORE HONEST:

  1. Disable weights for broken/dead collectors (adsb=0, acled=0, gdelt=0, ioda=0)
     so they don't inject random noise.
  
  2. Acknowledge that "sensor z-scores" is really just "gpsjam detector"
     and rename the component accordingly.
  
  3. Add collector health as a DEGRADATION signal:
     if >30% of sources are stale, mark score as "DEGRADED" regardless
     of the numeric value. Don't claim GREEN when you're blind.
  
  4. The most valuable signals are:
     a) gpsjam (real electronic warfare detection)
     b) framing_analysis campaigns (real hostile narrative detection)
     c) fabrication alerts (real claim mutation detection)
     d) energy prices (real economic stress indicator)
     
     Everything else is either noise or content that should feed
     into campaigns/fabrication rather than volume z-scores.

NEXT RESEARCH PRIORITIES:
  
  1. Campaign detection quality: Are the 5 framing_analysis campaigns
     from Mar 21 actually correct? Manual verification needed.
  
  2. Can we replace volume z-scores with content-based threat signals?
     e.g., keyword/topic z-scores on RSS content rather than RSS volume.
  
  3. Fabrication detection: the 16 alerts are all from a single detection
     run. How stable is this across time? Is it finding consistent results
     or hallucinating based on LLM mood?
""")
