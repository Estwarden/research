#!/usr/bin/env python3
"""
13. Campaign Verification — are framing_analysis campaigns real?
=================================================================

The CTI trusts campaigns detected by framing_analysis as real info ops.
This notebook examines the actual signals to check if the detections
are genuine hostile framing or just normal editorial differences.
"""
import csv
import os
from collections import defaultdict, Counter

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# Load campaign signals
campaigns = defaultdict(lambda: {
    'name': '', 'severity': '', 'event_fact': '', 
    'state_framing': '', 'framing_delta': '', 'signals': []
})

with open(f"{DATA}/framing_campaigns_signals.csv") as f:
    for row in csv.DictReader(f):
        cid = row['campaign_id']
        campaigns[cid]['name'] = row['name']
        campaigns[cid]['severity'] = row['severity']
        campaigns[cid]['event_fact'] = row.get('event_fact', '')
        campaigns[cid]['state_framing'] = row.get('state_framing', '')
        campaigns[cid]['framing_delta'] = row.get('framing_delta', '')
        campaigns[cid]['signals'].append(row)

print("=" * 70)
print(f"FRAMING ANALYSIS CAMPAIGNS: {len(campaigns)} total")
print("=" * 70)

for cid in sorted(campaigns.keys(), key=int):
    c = campaigns[cid]
    sigs = c['signals']
    
    # Analyze signal composition
    categories = Counter(s.get('category', '') for s in sigs)
    sources = Counter(s.get('source_type', '') for s in sigs)
    channels = Counter(s.get('channel', '') for s in sigs if s.get('channel'))
    
    has_state = any('ru_state' in s.get('category', '') or 'russian_state' in s.get('category', '') 
                     for s in sigs)
    has_trusted = any('trusted' in s.get('category', '') for s in sigs)
    has_proxy = any('ru_proxy' in s.get('category', '') for s in sigs)
    
    # Time span
    dates = sorted(s['published_at'][:10] for s in sigs if s.get('published_at'))
    span_days = 0
    if len(dates) >= 2:
        from datetime import datetime
        d1 = datetime.strptime(dates[0], '%Y-%m-%d')
        d2 = datetime.strptime(dates[-1], '%Y-%m-%d')
        span_days = (d2 - d1).days
    
    print(f"\n{'─' * 70}")
    print(f"Campaign {cid}: {c['name'][:70]}")
    print(f"  Severity: {c['severity']}, Signals: {len(sigs)}, Span: {span_days}d")
    print(f"  Categories: {dict(categories)}")
    print(f"  Sources: {dict(sources)}")
    if channels:
        print(f"  Top channels: {dict(channels.most_common(5))}")
    
    # Show the framing analysis
    if c['event_fact']:
        print(f"\n  FACT: {c['event_fact'][:120]}")
    if c['state_framing']:
        print(f"  STATE FRAMING: {c['state_framing'][:120]}")
    if c['framing_delta']:
        print(f"  DELTA: {c['framing_delta'][:120]}")
    
    # Verification checklist
    checks = []
    
    # 1. Does it have both state and non-state sources? (cross-ecosystem)
    if has_state and (has_trusted or has_proxy):
        checks.append("✅ Cross-ecosystem: state + other categories present")
    elif has_state:
        checks.append("⚠️  Only state media signals — could be normal coverage")
    else:
        checks.append("❌ No state media signals — not a state framing campaign")
    
    # 2. Is the event fact specific and verifiable?
    if c['event_fact'] and len(c['event_fact']) > 30:
        checks.append("✅ Event fact is specific and stated")
    else:
        checks.append("⚠️  Event fact is vague or missing")
    
    # 3. Is the framing delta meaningful?
    delta = c.get('framing_delta', '')
    if delta and any(w in delta.lower() for w in ['fabricat', 'omit', 'hedge', 'doubt', 'manufactur', 'selectively']):
        checks.append("✅ Framing delta describes specific manipulation")
    elif delta and len(delta) > 50:
        checks.append("⚠️  Framing delta exists but may be normal editorial difference")
    else:
        checks.append("❌ No meaningful framing delta")
    
    # 4. Signal count — is there enough evidence?
    if len(sigs) >= 5:
        checks.append(f"✅ Sufficient evidence ({len(sigs)} signals)")
    elif len(sigs) >= 2:
        checks.append(f"⚠️  Limited evidence ({len(sigs)} signals)")
    else:
        checks.append(f"❌ Insufficient evidence ({len(sigs)} signal)")
    
    # 5. Is it Baltic-relevant?
    baltic_keywords = ['эстон', 'латв', 'литв', 'балт', 'нато', 'nato', 'baltic', 
                       'estonia', 'latvia', 'lithuania', 'tallinn', 'riga', 'vilnius']
    all_text = ' '.join(s.get('signal_title', '') for s in sigs).lower()
    if any(k in all_text for k in baltic_keywords):
        checks.append("✅ Baltic/NATO relevant content")
    else:
        checks.append("⚠️  No Baltic keywords in signal titles")
    
    for check in checks:
        print(f"  {check}")
    
    # Overall verdict
    passed = sum(1 for c in checks if c.startswith('✅'))
    total = len(checks)
    if passed >= 4:
        print(f"\n  VERDICT: ✅ LIKELY REAL ({passed}/{total} checks passed)")
    elif passed >= 2:
        print(f"\n  VERDICT: ⚠️  PLAUSIBLE but weak ({passed}/{total} checks passed)")
    else:
        print(f"\n  VERDICT: ❌ LIKELY FALSE POSITIVE ({passed}/{total} checks passed)")

# ================================================================
# SUMMARY
# ================================================================
print("\n" + "=" * 70)
print("CAMPAIGN DETECTION QUALITY SUMMARY")
print("=" * 70)

verdicts = {"LIKELY REAL": 0, "PLAUSIBLE": 0, "FALSE POSITIVE": 0}
for cid in campaigns:
    c = campaigns[cid]
    sigs = c['signals']
    has_state = any('ru_state' in s.get('category', '') or 'russian_state' in s.get('category', '')
                     for s in sigs)
    has_other = any('trusted' in s.get('category', '') or 'ru_proxy' in s.get('category', '')
                     for s in sigs)
    delta = c.get('framing_delta', '')
    has_manip = delta and any(w in delta.lower() for w in ['fabricat', 'omit', 'hedge', 'doubt', 'manufactur', 'selectively'])
    
    score = 0
    if has_state and has_other: score += 1
    if c['event_fact'] and len(c['event_fact']) > 30: score += 1
    if has_manip: score += 1
    if len(sigs) >= 5: score += 1
    
    all_text = ' '.join(s.get('signal_title', '') for s in sigs).lower()
    if any(k in all_text for k in ['эстон', 'латв', 'литв', 'балт', 'нато', 'nato']): score += 1
    
    if score >= 4:
        verdicts["LIKELY REAL"] += 1
    elif score >= 2:
        verdicts["PLAUSIBLE"] += 1
    else:
        verdicts["FALSE POSITIVE"] += 1

print(f"\n  LIKELY REAL:     {verdicts['LIKELY REAL']}")
print(f"  PLAUSIBLE:       {verdicts['PLAUSIBLE']}")
print(f"  FALSE POSITIVE:  {verdicts['FALSE POSITIVE']}")
print(f"  TOTAL:           {sum(verdicts.values())}")
