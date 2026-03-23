#!/usr/bin/env python3
"""
07. CTI False Positive Audit
==============================

Finding from notebook 06: FIMI alone (24/25) exceeds YELLOW threshold.
This notebook audits each FIMI component for false positives.

Key question: how much of the threat score is real threat vs measurement noise?
"""
import csv
import json
import math
import os
from collections import defaultdict, Counter

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# ================================================================
# 1. NARRATIVE LAUNDERING — the biggest problem
# ================================================================
print("=" * 70)
print("1. NARRATIVE LAUNDERING AUDIT")
print("=" * 70)

origins = []
with open(f"{DATA}/narrative_origins.csv") as f:
    for row in csv.DictReader(f):
        origins.append(row)

laundering = [o for o in origins
              if o['is_state_origin'] == 't' and int(o['category_count']) >= 2]

print(f"\nTotal 'laundering' events: {len(laundering)}")

# Classify by content — is this Baltic/security relevant or just noise?
baltic_keywords = [
    'эстон', 'латв', 'литв', 'балт', 'нато', 'nato', 'eesti',
    'tallinn', 'riga', 'vilnius', 'kaliningrad', 'baltic',
    'финлянд', 'суоми', 'finland', 'польш', 'poland',
    'нарв', 'narva', 'псков', 'pskov',
]
security_keywords = [
    'войн', 'ракет', 'дрон', 'бпла', 'удар', 'атак', 'оруж',
    'санкци', 'диверс', 'шпион', 'развед', 'военн',
    'ядер', 'nuclear', 'missile', 'weapon',
    'кибер', 'cyber', 'хакер',
]

relevant = 0
noise = 0
noise_examples = []

for o in laundering:
    title = (o.get('first_title', '') or '').lower()
    cats = o.get('categories', '')
    
    is_baltic = any(k in title for k in baltic_keywords)
    is_security = any(k in title for k in security_keywords)
    
    if is_baltic or is_security:
        relevant += 1
    else:
        noise += 1
        if len(noise_examples) < 20:
            noise_examples.append(o.get('first_title', '')[:100])

noise_pct = noise / len(laundering) * 100 if laundering else 0
print(f"Relevant (Baltic/security keywords): {relevant} ({100-noise_pct:.0f}%)")
print(f"Noise (general Russian news): {noise} ({noise_pct:.0f}%)")

print(f"\nSample noise items counted as 'laundering':")
for ex in noise_examples[:15]:
    print(f"  • {ex}")

# What would the score be if we only counted relevant items?
LAUNDERING_WEIGHT = 6
TOTAL_WEIGHT = 110
current_score = min(len(laundering), 100) * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)
filtered_score = min(relevant, 100) * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)
print(f"\nCurrent laundering score: {current_score:.2f} (from {len(laundering)} events)")
print(f"Filtered score (relevant only): {filtered_score:.2f} (from {relevant} events)")
print(f"Score reduction: {current_score - filtered_score:.2f}")

# ================================================================
# 2. CAMPAIGN FALSE POSITIVES
# ================================================================
print("\n" + "=" * 70)
print("2. CAMPAIGN FALSE POSITIVE AUDIT")
print("=" * 70)

campaigns = []
with open(f"{DATA}/campaigns_full.csv") as f:
    for row in csv.DictReader(f):
        campaigns.append(row)

# Categorize by quality
empty_campaigns = [c for c in campaigns if int(c['signal_count']) == 0]
no_evidence = [c for c in campaigns if not c.get('event_fact') and not c.get('detection_method')]
blitz_only = [c for c in campaigns if 'blitz' in c.get('name', '').lower()]
framing = [c for c in campaigns if c.get('detection_method') == 'framing_analysis']
injection = [c for c in campaigns if c.get('detection_method') == 'injection_cascade']
outrage = [c for c in campaigns if c.get('detection_method') == 'outrage_chain']

print(f"\nTotal campaigns: {len(campaigns)}")
print(f"  With framing analysis evidence: {len(framing)}")
print(f"  Injection cascades: {len(injection)}")
print(f"  Outrage chains: {len(outrage)}")
print(f"  Actor blitz (volume spike only): {len(blitz_only)}")
print(f"  No detection method + no evidence: {len(no_evidence)}")
print(f"  Zero signals attached: {len(empty_campaigns)}")

# Which empty/evidence-free campaigns are HIGH severity?
high_empty = [c for c in campaigns 
              if c['severity'] == 'HIGH' and (int(c['signal_count']) == 0 or not c.get('event_fact'))]
print(f"\n  HIGH severity but no evidence or signals: {len(high_empty)}")
for c in high_empty:
    print(f"    • [{c['status']}] {c['name'][:80]} (sigs={c['signal_count']})")

# Score impact — what if we only count campaigns with actual evidence?
sev_scores = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 8, "LOW": 3}
CAMPAIGN_WEIGHT = 10

all_raw = sum(sev_scores.get(c['severity'], 5) for c in campaigns 
              if c['status'] == 'ACTIVE')
evidence_raw = sum(sev_scores.get(c['severity'], 5) for c in campaigns
                   if c['status'] == 'ACTIVE' and c.get('detection_method') 
                   and int(c['signal_count']) > 0)

all_score = min(all_raw, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)
evidence_score = min(evidence_raw, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)
print(f"\nCurrent ACTIVE campaign FIMI: {all_score:.2f} (raw={all_raw})")
print(f"Evidence-only FIMI: {evidence_score:.2f} (raw={evidence_raw})")
print(f"Score reduction: {all_score - evidence_score:.2f}")

# ================================================================
# 3. FABRICATION ALERT QUALITY
# ================================================================
print("\n" + "=" * 70)
print("3. FABRICATION ALERT QUALITY")
print("=" * 70)

fabrications = []
with open(f"{DATA}/fabrication_alerts.csv") as f:
    for row in csv.DictReader(f):
        fabrications.append(row)

# Check: are these cross-topic (noise) or Baltic-relevant?
fab_relevant = 0
fab_noise = 0
fab_noise_examples = []

for fa in fabrications:
    title = ((fa.get('root_title', '') or '') + ' ' + (fa.get('down_title', '') or '')).lower()
    if any(k in title for k in baltic_keywords + ['эстон', 'нато', 'nato']):
        fab_relevant += 1
    elif any(k in title for k in security_keywords):
        fab_relevant += 1  # Security-relevant even if not Baltic
    else:
        fab_noise += 1
        if len(fab_noise_examples) < 10:
            fab_noise_examples.append(
                f"  score={fa['fabrication_score']} views={fa.get('down_views',0)}: "
                f"{(fa.get('root_title',''))[:70]}")

print(f"\nTotal fabrication alerts: {len(fabrications)}")
print(f"Baltic/security relevant: {fab_relevant}")
print(f"Irrelevant (general Russia/Ukraine/Iran news): {fab_noise}")
if fab_noise_examples:
    print(f"\nIrrelevant fabrication alerts inflating CTI:")
    for ex in fab_noise_examples:
        print(ex)

# ================================================================
# 4. COMPOSITE: WHAT WOULD HONEST CTI LOOK LIKE?
# ================================================================
print("\n" + "=" * 70)
print("4. HONEST CTI — what if we only counted real threats?")
print("=" * 70)

# Current FIMI breakdown
current_fimi = {
    'campaigns': all_score,
    'fabrication': min(sum(
        float(f['fabrication_score']) * math.log10(max(int(f.get('down_views', 0) or 0), 1) + 1) *
        (1.5 if f.get('certainty_escalation') == 't' else 1) *
        (1.2 if f.get('emotional_amplification') == 't' else 1)
        for f in fabrications if float(f.get('fabrication_score', 0)) >= 3
    ) / 5, 100) * (8 / TOTAL_WEIGHT),
    'laundering': current_score,
    'narratives': min(593 / 10, 100) * (4 / TOTAL_WEIGHT),
}
current_total = sum(current_fimi.values())

# Filtered FIMI
# For fabrication: only count Baltic/security relevant ones
fab_filtered_total = 0
for fa in fabrications:
    title = ((fa.get('root_title', '') or '') + ' ' + (fa.get('down_title', '') or '')).lower()
    if not (any(k in title for k in baltic_keywords) or any(k in title for k in security_keywords)):
        continue
    score = float(fa.get('fabrication_score', 0))
    if score < 3:
        continue
    views = int(fa.get('down_views', 0) or 0)
    cert = fa.get('certainty_escalation') == 't'
    emot = fa.get('emotional_amplification') == 't'
    impact = score * math.log10(max(views, 1) + 1)
    if cert: impact *= 1.5
    if emot: impact *= 1.2
    fab_filtered_total += impact

filtered_fimi = {
    'campaigns': evidence_score,
    'fabrication': min(fab_filtered_total / 5, 100) * (8 / TOTAL_WEIGHT),
    'laundering': filtered_score,
    'narratives': current_fimi['narratives'],  # keep as-is
}
filtered_total = sum(filtered_fimi.values())

print(f"\n{'Component':<15s} {'Current':>8s} {'Filtered':>8s} {'Δ':>8s}")
print("-" * 45)
for k in ['campaigns', 'fabrication', 'laundering', 'narratives']:
    delta = filtered_fimi[k] - current_fimi[k]
    print(f"{k:<15s} {current_fimi[k]:>8.2f} {filtered_fimi[k]:>8.2f} {delta:>+8.2f}")
print("-" * 45)
print(f"{'FIMI TOTAL':<15s} {current_total:>8.2f} {filtered_total:>8.2f} {filtered_total-current_total:>+8.2f}")

# What would CTI be?
# From history: hybrid ≈ 5, security ≈ 1, economic ≈ 1
other_components = 7.0  # typical hybrid + security + economic
current_cti = current_total + other_components
filtered_cti = filtered_total + other_components

print(f"\n  Other components (hybrid+security+economic): ~{other_components}")
print(f"  Current CTI:  {current_cti:.1f} → {'YELLOW' if current_cti >= 15.2 else 'GREEN'}")
print(f"  Filtered CTI: {filtered_cti:.1f} → {'YELLOW' if filtered_cti >= 15.2 else 'GREEN'}")

if filtered_cti < 15.2:
    print(f"\n  ✅ With noise removed, CTI drops to GREEN.")
else:
    print(f"\n  ⚠️  Still YELLOW even after filtering. FIMI threshold itself needs recalibration.")
    print(f"     FIMI ceiling is 25 points. With 4 components each contributing,")
    print(f"     it's structurally likely to exceed 15.2 whenever there's ANY activity.")

print(f"""
========================================
RECOMMENDATIONS
========================================

1. LAUNDERING SCORE IS BROKEN
   It counts {len(laundering)} events as 'laundering' including NHL scores,
   Soyuz launches, and a teacher beating a student with a dildo.
   Only {relevant} of {len(laundering)} ({100-noise_pct:.0f}%) are Baltic/security relevant.
   FIX: Filter by region relevance, or raise category_count threshold to >=3.

2. CAMPAIGNS WITHOUT EVIDENCE INFLATE THE SCORE
   {len(high_empty)} HIGH-severity campaigns have no evidence or signals.
   FIX: Only count campaigns with detection_method + signal_count > 0.

3. FABRICATION ALERTS INCLUDE GLOBAL NOISE
   {fab_noise} of {len(fabrications)} alerts are about Iran, domestic Russia, etc.
   FIX: Filter fabrication alerts by region/relevance before scoring.

4. THRESHOLD WAS NEVER RECALIBRATED
   YELLOW=15.2 was tuned when CTI only had signal z-scores.
   Adding 4 FIMI sub-components made the score structurally inflate.
   FIX: Either raise YELLOW threshold or cap FIMI sub-components lower.
""")
