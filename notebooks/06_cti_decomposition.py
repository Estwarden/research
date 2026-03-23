#!/usr/bin/env python3
"""
06. CTI Decomposition — What's driving permanent YELLOW?
=========================================================

Question: Every region is stuck at YELLOW (~30-34). Why?

Approach: Replay the CTI algorithm on exported data, decompose each
component, identify what's miscalibrated.
"""
import csv
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# === CTI ALGORITHM (from compute_threat_index.py) ===
SIGNAL_WEIGHTS = {
    "gpsjam": 12, "adsb": 10, "acled": 8, "firms": 8,
    "ais": 6, "telegram": 6, "rss": 4, "gdelt": 4,
    "energy": 6, "business": 4, "ioda": 4,
}
CAMPAIGN_WEIGHT = 10
FABRICATION_WEIGHT = 8
LAUNDERING_WEIGHT = 6
NARRATIVE_WEIGHT = 4
GPSJAM_SEV_WEIGHT = 10
TOTAL_WEIGHT = sum(SIGNAL_WEIGHTS.values()) + CAMPAIGN_WEIGHT + FABRICATION_WEIGHT + LAUNDERING_WEIGHT + NARRATIVE_WEIGHT + GPSJAM_SEV_WEIGHT
YELLOW_THRESHOLD = 15.2

print(f"TOTAL_WEIGHT = {TOTAL_WEIGHT}")
print(f"YELLOW threshold = {YELLOW_THRESHOLD}")
print()

# ================================================================
# 1. THREAT INDEX HISTORY — decompose stored components
# ================================================================
print("=" * 70)
print("1. THREAT INDEX HISTORY")
print("=" * 70)

cti_rows = []
with open(f"{DATA}/threat_index_history.csv") as f:
    for row in csv.DictReader(f):
        row['score'] = float(row['score'])
        row['components'] = json.loads(row['components'].replace("'", '"')) if row['components'] else {}
        cti_rows.append(row)

# Group by region
by_region = defaultdict(list)
for r in cti_rows:
    by_region[r['region']].append(r)

print(f"\nRegions: {list(by_region.keys())}")
print(f"Total entries: {len(cti_rows)}")

for region in sorted(by_region.keys()):
    entries = by_region[region]
    scores = [e['score'] for e in entries]
    levels = [e['level'] for e in entries]
    green_pct = levels.count('GREEN') / len(levels) * 100
    yellow_pct = levels.count('YELLOW') / len(levels) * 100
    
    # Get component averages
    comp_sums = defaultdict(float)
    for e in entries:
        for k, v in e['components'].items():
            comp_sums[k] += float(v)
    comp_avgs = {k: v/len(entries) for k, v in comp_sums.items()}
    
    print(f"\n  {region}: {len(entries)} entries, "
          f"score {min(scores):.1f}–{max(scores):.1f}, "
          f"avg {sum(scores)/len(scores):.1f}")
    print(f"    GREEN: {green_pct:.0f}%  YELLOW: {yellow_pct:.0f}%")
    print(f"    Avg components: " + 
          " | ".join(f"{k}={v:.1f}" for k, v in sorted(comp_avgs.items())))

# ================================================================
# 2. CAMPAIGN ANALYSIS — are these real?
# ================================================================
print("\n" + "=" * 70)
print("2. CAMPAIGNS — what's driving the campaign score?")
print("=" * 70)

campaigns = []
with open(f"{DATA}/campaigns_full.csv") as f:
    for row in csv.DictReader(f):
        campaigns.append(row)

print(f"\nTotal campaigns: {len(campaigns)}")

# Severity distribution
sev_counts = defaultdict(int)
status_counts = defaultdict(int)
method_counts = defaultdict(int)
for c in campaigns:
    sev_counts[c['severity']] += 1
    status_counts[c['status']] += 1
    method_counts[c.get('detection_method', 'unknown')] += 1

print(f"By severity: {dict(sev_counts)}")
print(f"By status: {dict(status_counts)}")
print(f"By method: {dict(method_counts)}")

# Show each campaign
print(f"\n{'Sev':>8s} {'Status':>8s} {'Sigs':>4s} {'Method':>20s}  Name")
print("-" * 100)
for c in campaigns:
    print(f"{c['severity']:>8s} {c['status']:>8s} {c['signal_count']:>4s} "
          f"{c.get('detection_method','?'):>20s}  {c['name'][:80]}")

# ================================================================
# 3. FABRICATION ALERTS — legitimate or noise?
# ================================================================
print("\n" + "=" * 70)
print("3. FABRICATION ALERTS — are these real fabrications?")
print("=" * 70)

fabrications = []
with open(f"{DATA}/fabrication_alerts.csv") as f:
    for row in csv.DictReader(f):
        fabrications.append(row)

print(f"\nTotal alerts: {len(fabrications)}")

# Score distribution
score_counts = defaultdict(int)
for fa in fabrications:
    s = int(float(fa['fabrication_score']))
    score_counts[s] += 1
print(f"Score distribution: {dict(sorted(score_counts.items()))}")

# Category flow
flows = defaultdict(int)
for fa in fabrications:
    flow = f"{fa['root_category']} → {fa['down_category']}"
    flows[flow] += 1
print(f"\nCategory flows (root → amplifier):")
for flow, count in sorted(flows.items(), key=lambda x: -x[1]):
    print(f"  {count:>3d}× {flow}")

# Compute total fabrication FIMI contribution
fab_total = 0
for fa in fabrications:
    score = float(fa['fabrication_score'])
    views = int(fa['down_views']) if fa['down_views'] else 0
    cert = fa['certainty_escalation'] == 't'
    emot = fa['emotional_amplification'] == 't'
    if score < 3:
        continue
    impact = score * math.log10(max(views, 1) + 1)
    if cert: impact *= 1.5
    if emot: impact *= 1.2
    fab_total += impact

fab_score = min(fab_total / 5, 100) * (FABRICATION_WEIGHT / TOTAL_WEIGHT)
print(f"\nFabrication FIMI contribution: {fab_score:.2f} / {25}")

# ================================================================
# 4. NARRATIVE ORIGINS — is laundering score legit?
# ================================================================
print("\n" + "=" * 70)
print("4. NARRATIVE ORIGINS — laundering signal or noise?")
print("=" * 70)

origins = []
with open(f"{DATA}/narrative_origins.csv") as f:
    for row in csv.DictReader(f):
        origins.append(row)

print(f"\nTotal narrative origins: {len(origins)}")

# State origins with cross-category spread
state_origins = [o for o in origins if o['is_state_origin'] == 't']
laundering = [o for o in state_origins if int(o['category_count']) >= 2]
print(f"State-origin: {len(state_origins)}")
print(f"State-origin with category_count >= 2 (= laundering): {len(laundering)}")

launder_score = min(len(laundering), 100) * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)
print(f"Laundering FIMI contribution: {launder_score:.2f} / {25}")

# What categories are being "laundered"?
cat_counts = defaultdict(int)
for o in laundering:
    cats = o.get('categories', '').strip('{}').split(',')
    for c in cats:
        c = c.strip()
        if c:
            cat_counts[c] += 1

print(f"\nTop laundered category combinations:")
for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1])[:15]:
    print(f"  {count:>4d}× {cat}")

# Who is doing the "laundering"?
source_counts = defaultdict(int)
for o in laundering:
    source_counts[o.get('first_category', 'unknown')] += 1
print(f"\nLaundering first-mover categories:")
for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
    print(f"  {count:>4d}× {src}")

# ================================================================
# 5. SIGNAL Z-SCORES — are baselines stable?
# ================================================================
print("\n" + "=" * 70)
print("5. SIGNAL DAILY COUNTS — baseline stability")
print("=" * 70)

daily = defaultdict(lambda: defaultdict(int))
with open(f"{DATA}/signal_daily_counts.csv") as f:
    for row in csv.DictReader(f):
        day = row['day']
        st = row['source_type']
        daily[st][day] += int(row['count'])

for st in sorted(SIGNAL_WEIGHTS.keys()):
    if st not in daily:
        print(f"\n  {st}: NO DATA")
        continue
    counts = list(daily[st].values())
    if not counts:
        continue
    mean = sum(counts) / len(counts)
    if len(counts) > 1:
        variance = sum((x - mean)**2 for x in counts) / (len(counts) - 1)
        std = variance ** 0.5
    else:
        std = 0
    cv = std / mean * 100 if mean > 0 else 0
    weight = SIGNAL_WEIGHTS[st]
    print(f"\n  {st} (weight={weight}): {len(counts)} days, "
          f"mean={mean:.0f}, std={std:.0f}, CV={cv:.0f}%")
    
    # Show last 7 days
    days_sorted = sorted(daily[st].keys())[-7:]
    for d in days_sorted:
        c = daily[st][d]
        z = (c - mean) / max(std, 1)
        bar = "█" * min(int(abs(z) * 5), 30)
        print(f"    {d}: {c:>8d}  z={z:+.2f} {bar}")

# ================================================================
# 6. FIMI DECOMPOSITION — what's eating 24.6 of 25 points?
# ================================================================
print("\n" + "=" * 70)
print("6. FIMI BUDGET — where 24.6/25 comes from")
print("=" * 70)

# Using latest data
sev_scores = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 8, "LOW": 3}
camp_total = 0
recent_campaigns = [c for c in campaigns 
                    if c.get('detected_at', '') > (datetime.utcnow() - timedelta(days=7)).isoformat()]
for c in recent_campaigns:
    base = sev_scores.get(c['severity'], 5)
    if c['status'] == 'ACTIVE':
        decay = 1.0
    else:
        decay = 0.5  # most are 1-2 days old
    camp_total += base * decay

campaign_fimi = min(camp_total, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)
narrative_fimi = min(593 / 10, 100) * (NARRATIVE_WEIGHT / TOTAL_WEIGHT)

print(f"\n  Campaigns:    {campaign_fimi:>6.2f}  ({len(recent_campaigns)} campaigns in 7d, raw={camp_total:.0f})")
print(f"  Fabrication:  {fab_score:>6.2f}  ({len([f for f in fabrications if float(f['fabrication_score'])>=3])} alerts scoring 3+)")
print(f"  Laundering:   {launder_score:>6.2f}  ({len(laundering)} state-origin cross-category events, CAPPED at 100)")
print(f"  Narratives:   {narrative_fimi:>6.2f}  (593 tags in 7d)")
print(f"  ─────────────────────")
total_fimi = campaign_fimi + fab_score + launder_score + narrative_fimi
print(f"  FIMI TOTAL:   {total_fimi:>6.2f}  / 25.0 max")
print(f"\n  YELLOW threshold: {YELLOW_THRESHOLD}")
print(f"  FIMI alone exceeds YELLOW by: {total_fimi - YELLOW_THRESHOLD:.1f}")

# ================================================================
# 7. DIAGNOSIS
# ================================================================
print("\n" + "=" * 70)
print("7. DIAGNOSIS")
print("=" * 70)

print("""
FIMI alone ({:.1f}) exceeds the YELLOW threshold ({}).
Even with security/hybrid/economic all at ZERO, CTI will be YELLOW.

Root causes:
""".format(total_fimi, YELLOW_THRESHOLD))

if campaign_fimi > 5:
    print(f"  1. CAMPAIGNS ({campaign_fimi:.1f}): {len(recent_campaigns)} campaigns in 7 days is a LOT.")
    print(f"     Most are 'actor_blitz' detections. These may be normal activity flagged as campaigns.")
    actor_blitz = [c for c in recent_campaigns if 'blitz' in c.get('name', '').lower()]
    framing = [c for c in recent_campaigns if c.get('detection_method') == 'framing_analysis']
    print(f"     Actor blitz: {len(actor_blitz)}, Framing analysis: {len(framing)}, Other: {len(recent_campaigns)-len(actor_blitz)-len(framing)}")

if launder_score > 3:
    print(f"\n  2. LAUNDERING ({launder_score:.1f}): {len(laundering)} events in 7d, but score is CAPPED at 100.")
    print(f"     147 events means the score was already maxed out at 100.")
    print(f"     Question: is 'state origin reaching 2+ categories' actually laundering")
    print(f"     or is it just Russian state media covering news that other outlets also cover?")

if fab_score > 3:
    print(f"\n  3. FABRICATION ({fab_score:.1f}): {len(fabrications)} alerts, most score 4-10.")
    print(f"     All comparing ru_state→ru_proxy flows. Need to verify these are actual")
    print(f"     fabrication (added claims) vs just normal editorial differences.")

print(f"\n  4. THRESHOLD: YELLOW={YELLOW_THRESHOLD} was calibrated on old CTI with only signal z-scores.")
print(f"     The new algorithm added 4 new FIMI components (campaigns, fabrication,")
print(f"     laundering, narratives) that weren't in the calibration data.")
print(f"     The threshold was never recalibrated after these additions.")
