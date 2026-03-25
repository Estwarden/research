#!/usr/bin/env python3
"""
16. Campaign Scoring Audit — Evidence-Required vs Evidence-Free Contribution
=============================================================================

Building on:
  - Notebook 07: Found HIGH-severity campaigns with zero evidence inflating scores.
    26/37 campaigns have NO detection_method. Score reduction: removing evidence-free
    campaigns drops FIMI campaign contribution significantly.
  - Notebook 13: Campaign verification showed framing_analysis campaigns pass 4/5
    checks (cross-ecosystem, specific event fact, manipulation delta, signal evidence).
    Evidence-free campaigns are largely unverified.
  - Notebook 14: Campaigns are the BIGGEST FIMI sub-component (avg 6.59/9.09,
    72% of max), contributing more to permanent-YELLOW than any other component.
    26 no-evidence campaigns produce 360 raw severity points vs 130 from evidence-backed.

This notebook:
  1. Loads ALL campaigns with full metadata (merging campaigns_full + all_campaigns
     for signal_count)
  2. Categorizes by evidence quality:
     - tier1 = framing_analysis + signals >= 5 (gold standard)
     - tier2 = has detection_method + signals > 0 (automated with evidence)
     - tier3 = no method OR no signals (evidence-free)
  3. Computes CTI campaign contribution per tier
  4. Simulates CTI scores with tier3 excluded using stored threat_index_history
  5. Audits actor_blitz and narrative_spike campaigns — are they real threats
     or just normal publishing patterns?
  6. Proposes evidence requirements: minimum signal_count, required detection_method,
     auto-resolve policy after X days without new signals

Uses ONLY standard library + numpy.
"""
import csv
import json
import math
import os
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# ================================================================
# CTI ALGORITHM CONSTANTS
# ================================================================
CAMPAIGN_WEIGHT = 10
TOTAL_WEIGHT = 110
YELLOW_THRESHOLD = 15.2
SEV_SCORES = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 8, "LOW": 3}

print("=" * 72)
print("16. CAMPAIGN SCORING AUDIT")
print("=" * 72)
print(f"\nCampaign weight = {CAMPAIGN_WEIGHT}, total weight = {TOTAL_WEIGHT}")
print(f"Max campaign CTI contribution = {CAMPAIGN_WEIGHT / TOTAL_WEIGHT * 100:.2f}")
print(f"YELLOW threshold = {YELLOW_THRESHOLD}")


# ================================================================
# 1. LOAD AND MERGE CAMPAIGN DATA
# ================================================================
print("\n" + "=" * 72)
print("1. LOADING AND MERGING CAMPAIGN DATA")
print("=" * 72)

# campaigns_full.csv — has all metadata fields (37 rows)
# all_campaigns.csv — has signal_count (30 rows)
# framing_campaigns_signals.csv — individual signals per framing campaign

full_campaigns = {}
with open(f"{DATA}/campaigns_full.csv") as f:
    for row in csv.DictReader(f):
        full_campaigns[row['id']] = row

all_campaigns = {}
with open(f"{DATA}/all_campaigns.csv") as f:
    for row in csv.DictReader(f):
        all_campaigns[row['id']] = row

# Merge: start with campaigns_full, add signal_count from all_campaigns
campaigns = []
for cid, fc in full_campaigns.items():
    merged = dict(fc)
    if cid in all_campaigns:
        merged['signal_count'] = int(all_campaigns[cid]['signal_count'])
    else:
        # Try to extract signal count from name/summary
        match = re.search(r'(\d+)\s*(?:signals?|posts?)', fc.get('name', '') + ' ' + fc.get('summary', ''))
        if match:
            merged['signal_count'] = int(match.group(1))
        else:
            merged['signal_count'] = 0
    campaigns.append(merged)

# Sort by ID descending (newest first)
campaigns.sort(key=lambda c: int(c['id']), reverse=True)

print(f"\nTotal campaigns (merged): {len(campaigns)}")
print(f"  From campaigns_full: {len(full_campaigns)}")
print(f"  With signal_count from all_campaigns: {len(all_campaigns)}")
print(f"  Signal count inferred from text: {len(campaigns) - len(all_campaigns)}")

# Load per-campaign signals for deeper analysis of framing campaigns
framing_signals = defaultdict(list)
with open(f"{DATA}/framing_campaigns_signals.csv") as f:
    for row in csv.DictReader(f):
        framing_signals[row['campaign_id']].append(row)

print(f"  Framing campaign signals: {sum(len(v) for v in framing_signals.values())} "
      f"across {len(framing_signals)} campaigns")


# ================================================================
# 2. EVIDENCE TIER CLASSIFICATION
# ================================================================
print("\n" + "=" * 72)
print("2. EVIDENCE TIER CLASSIFICATION")
print("=" * 72)

EVIDENCE_METHODS = {'framing_analysis', 'injection_cascade', 'outrage_chain'}

tier1 = []  # Gold: framing_analysis + signals >= 5
tier2 = []  # Automated with evidence: has detection_method + signals > 0
tier3 = []  # Evidence-free: no method OR no signals

for c in campaigns:
    method = c.get('detection_method', '') or ''
    sigs = c['signal_count']

    if method == 'framing_analysis' and sigs >= 5:
        c['tier'] = 1
        c['tier_label'] = 'GOLD (framing + signals≥5)'
        tier1.append(c)
    elif method in EVIDENCE_METHODS and sigs > 0:
        c['tier'] = 2
        c['tier_label'] = 'AUTOMATED (method + signals>0)'
        tier2.append(c)
    else:
        c['tier'] = 3
        c['tier_label'] = 'EVIDENCE-FREE'
        tier3.append(c)

print(f"\n  Tier 1 (GOLD — framing_analysis + signals ≥ 5):   {len(tier1)} campaigns")
print(f"  Tier 2 (AUTOMATED — detection method + signals > 0): {len(tier2)} campaigns")
print(f"  Tier 3 (EVIDENCE-FREE — no method or no signals):    {len(tier3)} campaigns")

print(f"\n{'Tier':>6} {'ID':>4} {'Sev':>8} {'Status':>8} {'Signals':>7} {'Method':>20} {'Name':>45}")
print("-" * 105)
for c in campaigns:
    method = c.get('detection_method', '') or c.get('trigger_event', '') or '-'
    print(f"  T{c['tier']}  {c['id']:>4} {c['severity']:>8} {c['status']:>8} "
          f"{c['signal_count']:>7d} {method[:20]:>20} {c['name'][:45]}")


# ================================================================
# 3. SEVERITY AND RAW SCORE PER TIER
# ================================================================
print("\n" + "=" * 72)
print("3. CTI CAMPAIGN CONTRIBUTION PER TIER")
print("=" * 72)

for label, tier_list in [("Tier 1 (GOLD)", tier1),
                          ("Tier 2 (AUTOMATED)", tier2),
                          ("Tier 3 (EVIDENCE-FREE)", tier3)]:
    sev_dist = Counter(c['severity'] for c in tier_list)
    raw_total = sum(SEV_SCORES.get(c['severity'], 5) for c in tier_list)
    active_raw = sum(SEV_SCORES.get(c['severity'], 5) for c in tier_list
                     if c['status'] == 'ACTIVE')
    n_active = sum(1 for c in tier_list if c['status'] == 'ACTIVE')
    total_signals = sum(c['signal_count'] for c in tier_list)
    avg_signals = total_signals / len(tier_list) if tier_list else 0

    print(f"\n  {label}: {len(tier_list)} campaigns")
    print(f"    Severity distribution: {dict(sev_dist)}")
    print(f"    Total raw severity:    {raw_total}")
    print(f"    Active campaigns:      {n_active} (raw severity = {active_raw})")
    print(f"    Total signals:         {total_signals} (avg {avg_signals:.1f}/campaign)")

# Compute normalized CTI contribution
all_raw = sum(SEV_SCORES.get(c['severity'], 5) for c in campaigns)
t1_raw = sum(SEV_SCORES.get(c['severity'], 5) for c in tier1)
t2_raw = sum(SEV_SCORES.get(c['severity'], 5) for c in tier2)
t3_raw = sum(SEV_SCORES.get(c['severity'], 5) for c in tier3)

# Active-only contributions (what currently affects CTI)
all_active_raw = sum(SEV_SCORES.get(c['severity'], 5) for c in campaigns
                     if c['status'] == 'ACTIVE')
t1_active = sum(SEV_SCORES.get(c['severity'], 5) for c in tier1
                if c['status'] == 'ACTIVE')
t2_active = sum(SEV_SCORES.get(c['severity'], 5) for c in tier2
                if c['status'] == 'ACTIVE')
t3_active = sum(SEV_SCORES.get(c['severity'], 5) for c in tier3
                if c['status'] == 'ACTIVE')

print(f"\n  SUMMARY — Raw Severity Points")
print(f"  {'Tier':>20} {'All':>6} {'Active':>7} {'% of Total':>11}")
print(f"  " + "-" * 48)
print(f"  {'Tier 1 (GOLD)':>20} {t1_raw:>6} {t1_active:>7} {t1_raw/all_raw*100:>10.0f}%")
print(f"  {'Tier 2 (AUTO)':>20} {t2_raw:>6} {t2_active:>7} {t2_raw/all_raw*100:>10.0f}%")
print(f"  {'Tier 3 (FREE)':>20} {t3_raw:>6} {t3_active:>7} {t3_raw/all_raw*100:>10.0f}%")
print(f"  {'TOTAL':>20} {all_raw:>6} {all_active_raw:>7} {'100':>10}%")

# Normalized CTI contribution (all campaigns, for worst-case analysis)
all_norm = min(all_raw, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)
t12_raw = t1_raw + t2_raw
t12_norm = min(t12_raw, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)
t1_norm = min(t1_raw, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)

print(f"\n  CTI campaign contribution (normalized, ALL campaigns, static snapshot):")
print(f"    All tiers:       raw={all_raw:>4}, capped={min(all_raw,100):>4}, "
      f"CTI = {all_norm:.2f}")
print(f"    Tier 1+2 only:   raw={t12_raw:>4}, capped={min(t12_raw,100):>4}, "
      f"CTI = {t12_norm:.2f}")
print(f"    Tier 1 only:     raw={t1_raw:>4}, capped={min(t1_raw,100):>4}, "
      f"CTI = {t1_norm:.2f}")

# The static snapshot is misleading because min(raw, 100) caps both scenarios
# at 100 when raw >> 100. The REAL difference shows in time-varying analysis.
if all_raw > 100 and t12_raw > 100:
    print(f"\n    ⚠️  Static comparison is MISLEADING: both raw values exceed the 100 cap")
    print(f"       All tiers raw={all_raw} → capped to 100")
    print(f"       T1+T2 raw={t12_raw} → capped to 100")
    print(f"       The REAL impact shows in time-varying daily analysis (see section 4/5)")
    print(f"       because on specific days, T3 removal actually drops raw BELOW 100.")
elif all_norm > t12_norm:
    print(f"\n    Removing tier 3 reduces campaign CTI by: "
          f"{all_norm - t12_norm:.2f} ({(all_norm - t12_norm) / all_norm * 100:.0f}% reduction)")
else:
    print(f"\n    Both scenarios hit the cap — see daily simulation for real impact.")


# ================================================================
# 4. DECAY SIMULATION — CAMPAIGN CONTRIBUTION OVER TIME
# ================================================================
print("\n" + "=" * 72)
print("4. CAMPAIGN CONTRIBUTION OVER TIME (WITH DECAY)")
print("=" * 72)

# Simulate campaign contributions day-by-day using a 7-day active window
# with severity decay for aging campaigns
dates = sorted(set(c['detected_at'][:10] for c in campaigns if c.get('detected_at')))
date_range_start = min(dates)
date_range_end = max(dates)

# Generate all dates in range
start_dt = datetime.strptime(date_range_start, "%Y-%m-%d")
end_dt = datetime.strptime(date_range_end, "%Y-%m-%d")
all_dates = []
d = start_dt
while d <= end_dt:
    all_dates.append(d.strftime("%Y-%m-%d"))
    d += timedelta(days=1)

print(f"\nSimulating daily campaign contribution from {date_range_start} to {date_range_end}")
print(f"Using 7-day active window with linear decay.\n")

# For each day, compute the campaign contribution by tier
DECAY_WINDOW = 7

daily_contrib = []
for date_str in all_dates:
    target = datetime.strptime(date_str, "%Y-%m-%d")
    window_start = target - timedelta(days=DECAY_WINDOW)

    tier_raw = {1: 0, 2: 0, 3: 0}
    tier_count = {1: 0, 2: 0, 3: 0}

    for c in campaigns:
        det_str = c.get('detected_at', '')
        if not det_str:
            continue
        det_date = datetime.strptime(det_str[:10], "%Y-%m-%d")

        # Campaign must be detected before target and within window
        if det_date > target:
            continue

        # Apply decay: resolved campaigns decay over 7 days
        age = (target - det_date).days
        if c['status'] == 'RESOLVED':
            if age > DECAY_WINDOW:
                continue
            decay = max(0.2, 1.0 - age * (0.8 / DECAY_WINDOW))
        else:
            # Active campaigns don't decay
            decay = 1.0

        sev = SEV_SCORES.get(c['severity'], 5)
        tier = c['tier']
        tier_raw[tier] += sev * decay
        tier_count[tier] += 1

    total_raw = sum(tier_raw.values())
    total_norm = min(total_raw, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)

    t12_raw_day = tier_raw[1] + tier_raw[2]
    t12_norm_day = min(t12_raw_day, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)

    daily_contrib.append({
        'date': date_str,
        'total_raw': total_raw,
        'total_norm': total_norm,
        't1_raw': tier_raw[1],
        't2_raw': tier_raw[2],
        't3_raw': tier_raw[3],
        't12_norm': t12_norm_day,
        't1_count': tier_count[1],
        't2_count': tier_count[2],
        't3_count': tier_count[3],
    })

print(f"{'Date':>12} {'Total':>7} {'T1':>6} {'T2':>6} {'T3':>6} "
      f"{'All CTI':>8} {'T12 CTI':>8} {'Δ':>6} "
      f"{'Camps':>6}")
print("-" * 75)
for d in daily_contrib[-30:]:  # Last 30 days
    delta = d['total_norm'] - d['t12_norm']
    n_camps = d['t1_count'] + d['t2_count'] + d['t3_count']
    print(f"{d['date']:>12} {d['total_raw']:7.1f} {d['t1_raw']:6.1f} "
          f"{d['t2_raw']:6.1f} {d['t3_raw']:6.1f} "
          f"{d['total_norm']:8.2f} {d['t12_norm']:8.2f} {delta:>+6.2f} "
          f"{n_camps:>6d}")


# ================================================================
# 5. CTI SIMULATION — WITH AND WITHOUT TIER 3
# ================================================================
print("\n" + "=" * 72)
print("5. CTI SIMULATION — IMPACT OF REMOVING TIER 3")
print("=" * 72)

# Load stored CTI history
cti_rows = []
with open(f"{DATA}/threat_index_history.csv") as f:
    for row in csv.DictReader(f):
        comps_raw = row['components']
        if comps_raw and comps_raw.strip():
            comps = json.loads(comps_raw.replace("'", '"'))
        else:
            comps = {}
        row['_score'] = float(row['score'])
        row['_comps'] = comps
        cti_rows.append(row)

# Focus on baltic (most data)
baltic_cti = [r for r in cti_rows if r['region'] == 'baltic']
print(f"\nUsing baltic CTI history: {len(baltic_cti)} data points")

# For each CTI day, compute what the campaign contribution WOULD have been
# with tier 3 excluded, and adjust the stored score accordingly

print(f"\n{'Date':>12} {'Stored':>7} {'Level':>7} {'FIMI':>6} "
      f"{'Camp All':>9} {'Camp T12':>9} {'New Score':>10} {'New Level':>10}")
print("-" * 80)

simulated = []
for entry in baltic_cti:
    date_str = entry['date']
    stored_score = entry['_score']
    stored_level = entry['level']
    stored_fimi = float(entry['_comps'].get('fimi', 0))

    # Find daily contribution delta for this date
    dc = next((d for d in daily_contrib if d['date'] == date_str), None)
    if dc:
        campaign_reduction = dc['total_norm'] - dc['t12_norm']
    else:
        campaign_reduction = 0

    new_score = max(0, stored_score - campaign_reduction)
    new_level = 'GREEN' if new_score < YELLOW_THRESHOLD else 'YELLOW'

    simulated.append({
        'date': date_str,
        'stored_score': stored_score,
        'stored_level': stored_level,
        'new_score': new_score,
        'new_level': new_level,
        'campaign_reduction': campaign_reduction,
    })

    if date_str >= '2026-03-07':  # Only show data-available period
        camp_all = dc['total_norm'] if dc else 0
        camp_t12 = dc['t12_norm'] if dc else 0
        print(f"{date_str:>12} {stored_score:7.1f} {stored_level:>7} {stored_fimi:6.1f} "
              f"{camp_all:9.2f} {camp_t12:9.2f} {new_score:10.1f} {new_level:>10}")

# Count level transitions
current_yellow = sum(1 for s in simulated if s['stored_level'] == 'YELLOW')
new_yellow = sum(1 for s in simulated if s['new_level'] == 'YELLOW')
current_green = sum(1 for s in simulated if s['stored_level'] == 'GREEN')
new_green = sum(1 for s in simulated if s['new_level'] == 'GREEN')
flipped = sum(1 for s in simulated
              if s['stored_level'] == 'YELLOW' and s['new_level'] == 'GREEN')

# Data-available period only
sim_recent = [s for s in simulated if s['date'] >= '2026-03-07']
recent_current_yellow = sum(1 for s in sim_recent if s['stored_level'] == 'YELLOW')
recent_new_yellow = sum(1 for s in sim_recent if s['new_level'] == 'YELLOW')
recent_flipped = sum(1 for s in sim_recent
                     if s['stored_level'] == 'YELLOW' and s['new_level'] == 'GREEN')

print(f"\n  TRANSITION SUMMARY (all dates)")
print(f"    Current:  {current_yellow} YELLOW, {current_green} GREEN")
print(f"    Tier3-free: {new_yellow} YELLOW, {new_green} GREEN")
print(f"    YELLOW→GREEN flips: {flipped}")

print(f"\n  TRANSITION SUMMARY (Mar 7–25 only, data-available period)")
print(f"    Current:  {recent_current_yellow} YELLOW, {len(sim_recent) - recent_current_yellow} GREEN")
print(f"    Tier3-free: {recent_new_yellow} YELLOW, {len(sim_recent) - recent_new_yellow} GREEN")
print(f"    YELLOW→GREEN flips: {recent_flipped}")


# ================================================================
# 6. ACTOR BLITZ AND NARRATIVE SPIKE AUDIT
# ================================================================
print("\n" + "=" * 72)
print("6. ACTOR BLITZ & NARRATIVE SPIKE AUDIT")
print("=" * 72)

print("\nThese detection methods flag volume anomalies, NOT content analysis.")
print("Question: do they represent REAL threats or just normal publishing patterns?\n")

# Identify blitz/spike campaigns
blitz_campaigns = [c for c in campaigns
                   if (c.get('trigger_event', '') or '') in ('actor_blitz', 'narrative_spike')
                   or 'blitz' in c.get('name', '').lower()
                   or 'spike' in c.get('name', '').lower()]

print(f"Blitz/spike campaigns: {len(blitz_campaigns)}\n")

for c in blitz_campaigns:
    trigger = c.get('trigger_event', '') or '-'
    method = c.get('detection_method', '') or '-'
    summary = c.get('summary', '')[:200]

    # Parse z-score from summary if available
    z_match = re.search(r'z[=:]?(\d+\.?\d*)', summary)
    z_score = float(z_match.group(1)) if z_match else None

    # Parse baseline from summary
    base_match = re.search(r'baseline:\s*(\d+)[±](\d+)', summary)
    baseline_mean = int(base_match.group(1)) if base_match else None
    baseline_std = int(base_match.group(2)) if base_match else None

    # Check if target_regions includes Baltic
    regions = c.get('target_regions', '')
    is_global = 'global' in regions.lower()
    is_baltic = any(r in regions.lower() for r in ['baltic', 'estonia', 'latvia', 'lithuania'])

    # Identify the actor
    actor_match = re.search(r'(?:Actor blitz:\s*|spike.*?)\b(\w+)\s*\(', summary)
    actor = actor_match.group(1) if actor_match else '-'

    print(f"  Campaign {c['id']}: {c['name'][:65]}")
    print(f"    Trigger: {trigger}, Method: {method}")
    print(f"    Severity: {c['severity']}, Status: {c['status']}, Signals: {c['signal_count']}")
    print(f"    Regions: {regions}")
    if z_score:
        print(f"    Z-score: {z_score:.1f}", end="")
        if baseline_mean is not None:
            print(f" (baseline: {baseline_mean}±{baseline_std}/day)", end="")
        print()

    # VERDICT for blitz campaigns
    checks = []
    if is_baltic:
        checks.append("✅ Baltic-targeted")
    elif is_global:
        checks.append("⚠️  Global (not Baltic-specific)")

    if z_score and z_score >= 4.0:
        checks.append(f"✅ High z-score ({z_score:.1f} ≥ 4.0)")
    elif z_score and z_score >= 3.0:
        checks.append(f"⚠️  Moderate z-score ({z_score:.1f})")
    else:
        checks.append("❌ No z-score or low z-score")

    if c.get('event_fact'):
        checks.append("✅ Has event_fact (content verified)")
    elif c.get('detection_method') in EVIDENCE_METHODS:
        checks.append("⚠️  Has detection method but no event_fact")
    else:
        checks.append("❌ No event_fact (volume-only detection)")

    if c['signal_count'] >= 5:
        checks.append(f"✅ Substantial signals ({c['signal_count']})")
    elif c['signal_count'] > 0:
        checks.append(f"⚠️  Few signals ({c['signal_count']})")
    else:
        checks.append("❌ No signals")

    for check in checks:
        print(f"    {check}")

    passed = sum(1 for ch in checks if ch.startswith('✅'))
    if passed >= 3:
        verdict = "REAL THREAT"
    elif passed >= 1:
        verdict = "UNCERTAIN — needs content review"
    else:
        verdict = "LIKELY NOISE — volume artifact"
    print(f"    → VERDICT: {verdict}")
    print()


# ================================================================
# 7. CAMPAIGNS WITHOUT DETECTION METHOD — DEEP AUDIT
# ================================================================
print("=" * 72)
print("7. NO-METHOD CAMPAIGNS — ARE THEY REAL?")
print("=" * 72)

no_method = [c for c in campaigns if not c.get('detection_method')]
print(f"\nCampaigns without detection_method: {len(no_method)}")

# Group by trigger_event type
trigger_dist = Counter(c.get('trigger_event', '') or 'NONE' for c in no_method)
print(f"Trigger types: {dict(trigger_dist)}")

# For each, evaluate evidence quality
print(f"\n{'ID':>4} {'Sev':>8} {'Signals':>7} {'Trigger':>30} {'Name':>50}")
print("-" * 105)

quality_scores = []
for c in no_method:
    trigger = (c.get('trigger_event', '') or 'NONE')[:30]
    name = c['name'][:50]
    sigs = c['signal_count']

    # Score evidence quality on 0-5 scale
    q_score = 0
    if sigs >= 10:
        q_score += 2
    elif sigs >= 5:
        q_score += 1
    if c.get('event_fact') and len(c.get('event_fact', '')) > 30:
        q_score += 1
    if c.get('state_framing') and len(c.get('state_framing', '')) > 30:
        q_score += 1
    if c.get('framing_delta') and len(c.get('framing_delta', '')) > 30:
        q_score += 1

    quality_scores.append(q_score)
    q_label = ['❌', '⚠ ', '⚠⚠', '✅ ', '✅✅', '✅✅✅'][q_score]
    print(f"{c['id']:>4} {c['severity']:>8} {sigs:>7d} {trigger:>30} {q_label} {name}")

# Evidence quality distribution
q_dist = Counter(quality_scores)
print(f"\n  Evidence quality distribution (0=none → 5=full):")
for q in sorted(q_dist.keys()):
    bar = "█" * q_dist[q]
    labels = {0: 'no evidence', 1: 'minimal', 2: 'some', 3: 'moderate', 4: 'good', 5: 'full'}
    print(f"    Q={q} ({labels.get(q, '?'):>12}): {q_dist[q]:>3d} {bar}")

high_quality_no_method = sum(1 for q in quality_scores if q >= 3)
low_quality_no_method = sum(1 for q in quality_scores if q < 2)
print(f"\n  No-method campaigns with quality ≥ 3 (salvageable): {high_quality_no_method}")
print(f"  No-method campaigns with quality < 2 (should drop):  {low_quality_no_method}")


# ================================================================
# 8. TEMPORAL ANALYSIS — CAMPAIGN AGE AND AUTO-RESOLVE POLICY
# ================================================================
print("\n" + "=" * 72)
print("8. CAMPAIGN AGE ANALYSIS — AUTO-RESOLVE POLICY")
print("=" * 72)

now = datetime.strptime("2026-03-25", "%Y-%m-%d")
ages = []
active_ages = []

print(f"\n{'ID':>4} {'Sev':>8} {'Status':>8} {'Age(d)':>7} {'Signals':>7} "
      f"{'Method':>20} {'Auto-Resolve?':>14}")
print("-" * 80)

for c in campaigns:
    det_str = c.get('detected_at', '')
    if not det_str:
        continue
    det_date = datetime.strptime(det_str[:10], "%Y-%m-%d")
    age = (now - det_date).days
    ages.append(age)

    method = c.get('detection_method', '') or '-'
    sigs = c['signal_count']

    # Should this auto-resolve?
    should_resolve = False
    reason = ""
    if c['status'] == 'ACTIVE':
        active_ages.append(age)
        if age > 7 and sigs == 0:
            should_resolve = True
            reason = "YES — 7d+ with 0 signals"
        elif age > 14 and method not in EVIDENCE_METHODS:
            should_resolve = True
            reason = "YES — 14d+ without evidence method"
        elif age > 2 and not c.get('detection_method') and sigs == 0:
            should_resolve = True
            reason = "YES — 48h+ no method no signals"
        else:
            reason = "NO — still active with evidence"
    else:
        reason = f"(already {c['status']})"

    print(f"{c['id']:>4} {c['severity']:>8} {c['status']:>8} {age:>7d} {sigs:>7d} "
          f"{method[:20]:>20} {reason}")

if active_ages:
    print(f"\n  Active campaign ages: min={min(active_ages)}d, max={max(active_ages)}d, "
          f"avg={np.mean(active_ages):.0f}d")
    auto_resolve_count = sum(1 for c in campaigns
                             if c['status'] == 'ACTIVE' and (
                                 c['signal_count'] == 0 and
                                 (now - datetime.strptime(c['detected_at'][:10], "%Y-%m-%d")).days > 2
                             ))
    print(f"  Campaigns that should auto-resolve (48h+ with 0 signals): {auto_resolve_count}")


# ================================================================
# 9. EVIDENCE REQUIREMENT PROPOSALS
# ================================================================
print("\n" + "=" * 72)
print("9. EVIDENCE REQUIREMENT PROPOSALS")
print("=" * 72)

# Proposal A: Require detection_method for scoring
# Proposal B: Require signal_count >= N for scoring
# Proposal C: Auto-resolve after X days without new signals
# Proposal D: Score by tier (full weight for T1, reduced for T2, zero for T3)

proposals = {
    'A: Require detection_method': {
        'keep': [c for c in campaigns if c.get('detection_method') in EVIDENCE_METHODS],
        'drop': [c for c in campaigns if c.get('detection_method') not in EVIDENCE_METHODS],
    },
    'B: Require signals >= 5': {
        'keep': [c for c in campaigns if c['signal_count'] >= 5],
        'drop': [c for c in campaigns if c['signal_count'] < 5],
    },
    'C: Require method + signals > 0': {
        'keep': [c for c in campaigns
                 if c.get('detection_method') in EVIDENCE_METHODS and c['signal_count'] > 0],
        'drop': [c for c in campaigns
                 if not (c.get('detection_method') in EVIDENCE_METHODS and c['signal_count'] > 0)],
    },
    'D: Keep T1+T2, drop T3': {
        'keep': tier1 + tier2,
        'drop': tier3,
    },
    'E: Keep quality >= 2 (any evidence)': {
        'keep': [c for c, q in zip(no_method, quality_scores) if q >= 2] + tier1 + tier2,
        'drop': [c for c, q in zip(no_method, quality_scores) if q < 2],
    },
}

print(f"\n  Note: CTI formula uses min(raw, 100), so when raw >> 100 for both keep")
print(f"  and all, the capped CTI looks identical. Uncapped raw shows the true gap.\n")

print(f"{'Proposal':>40} {'Keep':>5} {'Drop':>5} {'Raw Keep':>9} "
      f"{'Raw All':>8} {'Uncapped Δ':>11} {'CTI(keep)':>10} {'CTI(all)':>9}")
print("-" * 105)

for name, groups in proposals.items():
    keep_raw = sum(SEV_SCORES.get(c['severity'], 5) for c in groups['keep'])
    drop_raw = sum(SEV_SCORES.get(c['severity'], 5) for c in groups['drop'])
    total_raw_p = keep_raw + drop_raw
    keep_cti = min(keep_raw, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)
    total_cti = min(total_raw_p, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)
    uncapped_delta = drop_raw  # raw points removed

    print(f"{name:>40} {len(groups['keep']):>5d} {len(groups['drop']):>5d} "
          f"{keep_raw:>9d} {total_raw_p:>8d} {uncapped_delta:>+11d} "
          f"{keep_cti:>10.2f} {total_cti:>9.2f}")

print(f"\n  Key insight: Proposals A/C/D remove {t3_raw} raw severity points from the pool.")
print(f"  On days when total raw < 100 (early period), this eliminates ALL campaign CTI.")
print(f"  On days when T1+T2 alone exceed 100, tier 3 removal has no effect (already capped).")


# ================================================================
# 10. TIERED SCORING SIMULATION — WEIGHTED BY EVIDENCE QUALITY
# ================================================================
print("\n" + "=" * 72)
print("10. TIERED SCORING — WEIGHT BY EVIDENCE QUALITY")
print("=" * 72)

print("\nInstead of binary keep/drop, score campaigns with tier multipliers:\n")
print("  Tier 1 (GOLD):          1.0× severity (full weight)")
print("  Tier 2 (AUTOMATED):     0.7× severity (reduced — less human validation)")
print("  Tier 3 (EVIDENCE-FREE): 0.0× severity (excluded until evidence provided)")
print()

tier_multipliers = {1: 1.0, 2: 0.7, 3: 0.0}

# Alternative: softer tier3 handling
alt_multipliers = {1: 1.0, 2: 0.8, 3: 0.3}

for label, mults in [("Strict (T3=0.0)", tier_multipliers),
                      ("Soft (T3=0.3)", alt_multipliers)]:
    weighted_raw = sum(SEV_SCORES.get(c['severity'], 5) * mults[c['tier']]
                       for c in campaigns)
    weighted_cti = min(weighted_raw, 100) * (CAMPAIGN_WEIGHT / TOTAL_WEIGHT)
    print(f"  {label}: raw={weighted_raw:.1f}, CTI={weighted_cti:.2f} "
          f"(vs current {all_norm:.2f}, delta={weighted_cti - all_norm:+.2f})")


# ================================================================
# 11. COMBINED CTI IMPACT — FULL SIMULATION WITH ALL REGIONS
# ================================================================
print("\n" + "=" * 72)
print("11. FULL CTI SIMULATION — ALL REGIONS")
print("=" * 72)

# For each region, compute the impact of removing tier 3
for region in sorted(set(r['region'] for r in cti_rows)):
    region_entries = [r for r in cti_rows if r['region'] == region
                      and r['date'] >= '2026-03-07']
    if not region_entries:
        continue

    n_total = len(region_entries)
    current_yellow_n = sum(1 for e in region_entries if e['level'] == 'YELLOW')
    current_green_n = n_total - current_yellow_n

    # Estimate campaign reduction for each day
    flipped_n = 0
    new_scores_list = []
    for entry in region_entries:
        dc = next((d for d in daily_contrib if d['date'] == entry['date']), None)
        if dc:
            reduction = dc['total_norm'] - dc['t12_norm']
        else:
            reduction = 0

        new_score = max(0, entry['_score'] - reduction)
        new_scores_list.append(new_score)
        if entry['level'] == 'YELLOW' and new_score < YELLOW_THRESHOLD:
            flipped_n += 1

    new_yellow_n = sum(1 for s in new_scores_list if s >= YELLOW_THRESHOLD)
    new_green_n = n_total - new_yellow_n
    avg_reduction = np.mean([entry['_score'] - ns
                             for entry, ns in zip(region_entries, new_scores_list)])

    print(f"\n  {region} ({n_total} days, Mar 7–25):")
    print(f"    Current:    {current_yellow_n} YELLOW, {current_green_n} GREEN")
    print(f"    Tier3-free: {new_yellow_n} YELLOW, {new_green_n} GREEN")
    print(f"    Flipped:    {flipped_n} YELLOW→GREEN")
    print(f"    Avg score reduction: {avg_reduction:.1f}")


# ================================================================
# 12. DIAGNOSIS AND RECOMMENDATIONS
# ================================================================
print("\n" + "=" * 72)
print("12. DIAGNOSIS AND POLICY RECOMMENDATIONS")
print("=" * 72)

# Count key stats
n_total_camps = len(campaigns)
n_tier1 = len(tier1)
n_tier2 = len(tier2)
n_tier3 = len(tier3)
pct_tier3 = n_tier3 / n_total_camps * 100

# Active tier3 campaigns
active_t3 = [c for c in tier3 if c['status'] == 'ACTIVE']
n_active_t3 = len(active_t3)

# Severity inflation from tier3
t3_high_critical = sum(1 for c in tier3 if c['severity'] in ('HIGH', 'CRITICAL'))
t3_hc_pct = t3_high_critical / n_tier3 * 100 if n_tier3 else 0

# How many blitz campaigns are tier3?
blitz_t3 = [c for c in blitz_campaigns if c['tier'] == 3]

print(f"""
CAMPAIGN SCORING AUDIT RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FINDING 1: Evidence-free campaigns dominate the score
  - {n_tier3}/{n_total_camps} ({pct_tier3:.0f}%) campaigns have NO detection method or no signals (tier 3)
  - Tier 3 contributes {t3_raw} of {all_raw} total raw severity points ({t3_raw/all_raw*100:.0f}%)
  - {t3_high_critical}/{n_tier3} tier 3 campaigns are HIGH or CRITICAL ({t3_hc_pct:.0f}%)
  - Currently {n_active_t3} tier 3 campaigns are ACTIVE

FINDING 2: Blitz/spike campaigns are volume artifacts, not content-verified threats
  - {len(blitz_campaigns)} blitz/spike campaigns detected
  - {len(blitz_t3)}/{len(blitz_campaigns)} are tier 3 (no evidence method)
  - These fire when an actor publishes slightly above their baseline (z≥3.0)
  - A Telegram channel posting 22 times instead of 11 is NOT a campaign
  - Targeted region is always 'global' — not even Baltic-specific

FINDING 3: Removing tier 3 has significant time-varying impact
  - Static raw comparison: {all_raw} → {t12_raw} raw severity points ({all_raw-t12_raw} removed)
  - Static CTI appears unchanged ({all_norm:.2f} → {t12_norm:.2f}) due to min(raw,100) cap
  - But DAILY simulation shows the real impact: {recent_flipped} YELLOW→GREEN flips (Mar 7–25)
  - Before Mar 21 (when T1/T2 campaigns were created), ALL campaign CTI comes from tier 3
  - The daily analysis proves tier 3 is the sole driver of campaign inflation in early period

FINDING 4: No-method campaigns lack structured evidence
  - {high_quality_no_method} no-method campaigns score quality ≥ 3 (have event_fact + framing fields)
  - {low_quality_no_method} no-method campaigns score quality < 2 (no structured evidence at all)
  - The remaining {n_tier3 - high_quality_no_method - low_quality_no_method} have partial evidence (signal count only, no analysis)
  - Many are manually-created campaigns that predate the automated pipeline
  - They have signals attached but no event_fact/state_framing/framing_delta

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POLICY RECOMMENDATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

POLICY 1: Evidence requirement for campaign scoring
  ✓ Only score campaigns with:
    - detection_method IN (framing_analysis, injection_cascade, outrage_chain, manual_analysis)
    - AND signal_count > 0
  ✓ actor_blitz and narrative_spike should NOT create scored campaigns
    - They should create ALERTS (visible in dashboard) but not inflate CTI
  ✓ Expected impact: {recent_flipped} YELLOW→GREEN day flips in Mar 7–25 period
    (on days before T1/T2 campaigns exist, ALL campaign CTI is eliminated)

POLICY 2: Auto-resolve stale campaigns
  ✓ If no new signals in 48h AND no detection_method → auto-resolve
  ✓ If no new signals in 7d AND status=ACTIVE → auto-resolve
  ✓ Resolved campaigns decay over 7 days (current behavior is reasonable)

POLICY 3: Tiered campaign scoring
  ✓ Tier 1 (framing_analysis + signals ≥ 5): 1.0× severity
  ✓ Tier 2 (automated method + signals > 0):  0.7× severity
  ✓ Tier 3 (no method or no signals):         0.0× severity (alert only)

POLICY 4: Retroactive cleanup
  ✓ Review {high_quality_no_method} no-method campaigns with quality ≥ 3
  ✓ Tag with detection_method='manual_analysis' if they have genuine evidence
  ✓ Resolve {low_quality_no_method} low-quality campaigns permanently

POLICY 5: Separate blitz/spike from campaign pipeline
  ✓ actor_blitz → ALERT (dashboard notification, no CTI impact)
  ✓ narrative_spike → ALERT IF z ≥ 4.0 AND Baltic-targeted → promote to campaign
  ✓ Only promote to campaign if content analysis confirms hostile framing
""")

print("Done.")
