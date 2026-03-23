#!/usr/bin/env python3
"""
09. System Health Audit — what needs fixing?
==============================================

Comprehensive audit of collectors, data quality, campaigns,
and public-facing output.
"""
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# We'll use the signal_daily_counts data we already have
daily = defaultdict(lambda: defaultdict(int))
with open(f"{DATA}/signal_daily_counts.csv") as f:
    for row in csv.DictReader(f):
        daily[row['source_type']][row['day']] += int(row['count'])

campaigns = []
with open(f"{DATA}/campaigns_full.csv") as f:
    for row in csv.DictReader(f):
        campaigns.append(row)

# ================================================================
# 1. DEAD COLLECTORS
# ================================================================
print("=" * 70)
print("1. DEAD COLLECTORS (no data in last 3 days)")
print("=" * 70)

# From the freshness scan we know these are dead:
dead = {
    "sanctions":      ("no MAX date at all", "CTI weight: 0"),
    "milwatch":       ("dead since Mar 15", "was military base watchlist"),
    "osint_milbase":  ("dead since Mar 20", "was Perplexity-based milbase OSINT"),
    "ru_legislation": ("dead since Mar 20", "Russian legislative tracking"),
    "gdelt":          ("dead since Mar 20", "CTI weight: 4 — IMPACTS SCORE"),
    "youtube":        ("dead since Mar 20", "separate from youtube_transcript which works"),
    "telegram":       ("dead since Mar 20", "legacy? telegram_channel works"),
    "defense_rss":    ("dead since Mar 20", "NATO/defense RSS feeds"),
    "notam":          ("dead since Mar 20", "airspace notices"),
    "embassy":        ("dead since Mar 20", "embassy activity tracker"),
    "railway":        ("1 signal ever", "experimental?"),
    "seismic":        ("1 signal ever", "experimental?"),
    "conflict":       ("dead since Mar 20", "ACLED-like conflict data"),
}

print(f"\n  {'Source':20s} {'Status':25s} {'Notes'}")
print("  " + "-" * 75)
for src, (status, notes) in sorted(dead.items()):
    cti_w = "⚠️" if src in ("gdelt", "adsb", "firms") else "  "
    print(f"  {cti_w}{src:18s} {status:25s} {notes}")

print(f"\n  TOTAL: {len(dead)} dead source types")
print(f"  Of these, only 'gdelt' has a CTI weight (4 points).")
print(f"  The rest don't affect the threat score but waste DB space.")

# ================================================================
# 2. SIGNAL VOLUME ANOMALIES
# ================================================================
print("\n" + "=" * 70)
print("2. SIGNAL VOLUME ANOMALIES (active collectors)")
print("=" * 70)

for st in sorted(daily.keys()):
    if st in dead:
        continue
    counts = sorted(daily[st].items())
    if len(counts) < 5:
        continue
    
    values = [c for _, c in counts]
    mean = sum(values) / len(values)
    if len(values) > 1:
        std = (sum((v - mean)**2 for v in values) / (len(values)-1)) ** 0.5
    else:
        std = 0
    cv = std / mean * 100 if mean > 0 else 0
    
    last_day, last_count = counts[-1]
    z_last = (last_count - mean) / max(std, 1)
    
    flag = ""
    if cv > 100:
        flag = "⚠️  HIGH VARIANCE"
    if z_last > 3:
        flag += " 📈 SPIKE"
    if z_last < -2:
        flag += " 📉 DROP"
    
    if flag or cv > 50:
        print(f"\n  {st}: mean={mean:.0f}/day, CV={cv:.0f}%, last_day z={z_last:+.1f} {flag}")

# ================================================================
# 3. CAMPAIGN QUALITY ASSESSMENT
# ================================================================
print("\n" + "=" * 70)
print("3. CAMPAIGN QUALITY")
print("=" * 70)

active = [c for c in campaigns if c['status'] == 'ACTIVE']
resolved = [c for c in campaigns if c['status'] == 'RESOLVED']

# Quality tiers
tier1 = [c for c in active if c.get('detection_method') == 'framing_analysis'
         and int(c['signal_count']) >= 5 and c.get('event_fact')]
tier2 = [c for c in active if c.get('detection_method') 
         and int(c['signal_count']) > 0 and c not in tier1]
tier3 = [c for c in active if c not in tier1 and c not in tier2]

print(f"\n  Active: {len(active)}, Resolved: {len(resolved)}")
print(f"\n  Tier 1 — Framing analysis + evidence + signals: {len(tier1)}")
for c in tier1:
    print(f"    [{c['severity']}] {c['name'][:70]} ({c['signal_count']} sigs)")

print(f"\n  Tier 2 — Has detection method + signals: {len(tier2)}")
for c in tier2:
    print(f"    [{c['severity']}] {c['name'][:70]} ({c['signal_count']} sigs, {c.get('detection_method','')})")

print(f"\n  Tier 3 — No method or no signals (noise/placeholders): {len(tier3)}")
for c in tier3:
    print(f"    [{c['severity']}] {c['name'][:70]} ({c['signal_count']} sigs)")

# ================================================================
# 4. REPORT QUALITY — did it degrade?
# ================================================================
print("\n" + "=" * 70)
print("4. DAILY REPORT QUALITY")
print("=" * 70)

# From the DB query we know:
reports = [
    ("2026-03-14", "YELLOW", 21.7, 285, 27660),
    ("2026-03-15", "GREEN",  13.8, 227, 29446),
    ("2026-03-16", "YELLOW", 16.1, 313, 30567),
    ("2026-03-17", "YELLOW", 16.3, 305, 31778),
    ("2026-03-18", "GREEN",  15.1, 385, 27644),
    ("2026-03-19", "YELLOW", 16.0, 423, 28534),
    ("2026-03-20", "YELLOW", 15.6, 446, 27824),
    ("2026-03-21", "YELLOW", 27.5, 200, 1136),
    ("2026-03-22", "YELLOW", 31.0, 198, 1134),
    ("2026-03-23", "YELLOW", 18.9, 199, 1135),
]

print(f"\n  {'Date':12s} {'Level':7s} {'Score':>5s} {'Summary':>7s} {'Intel':>7s} {'Quality'}")
print("  " + "-" * 60)
for date, level, score, summ_len, intel_len in reports:
    quality = "✅ LLM" if intel_len > 5000 else "❌ TEMPLATE"
    print(f"  {date:12s} {level:7s} {score:>5.1f} {summ_len:>7d} {intel_len:>7d} {quality}")

print("""
  Report quality COLLAPSED on March 21:
  - Before: LLM-generated summaries (300-450 chars) with rich raw_intel (27-31K chars)
  - After: Template sentences (198-200 chars) with minimal indicators (1.1K chars)
  
  The report generator switched from LLM analysis to template fill.
  This is the current report_generator.py design — it's template-only,
  no LLM call. The old LLM-generated reports were from a different
  version of the generator that was replaced.
""")

# ================================================================
# 5. ISSUES SUMMARY — PRIORITIZED
# ================================================================
print("=" * 70)
print("5. PRIORITIZED IMPROVEMENT LIST")
print("=" * 70)

print("""
  PRIORITY 1 — DATA QUALITY (affects everything downstream)
  ──────────────────────────────────────────────────────────
  
  a) 12 dead collectors since Mar 15-20.
     IMPACT: blind spots in defense_rss, GDELT, NOTAM, embassy, youtube.
     GDELT has CTI weight (4 pts) — dead source = missing z-score input.
     FIX: Diagnose which DAGs are broken. Many died on same day (Mar 20)
          suggesting a systemic failure (Dagu restart? permission issue?).
     
  b) 3 active campaigns are noise (no detection method, no evidence).
     IMPACT: inflates campaign count in reports/dashboard.
     FIX: Auto-resolve campaigns with no signals after 48h.
     
  c) Report summaries are template-only since Mar 21.
     IMPACT: public dashboard shows "Monday automated briefing" instead
     of actual analysis. The old reports had real LLM-generated assessments.
     FIX: Add LLM summary call back to report_generator.py,
          or build a separate briefing generator.

  PRIORITY 2 — DISPLAY / PUBLIC SURFACE
  ──────────────────────────────────────
  
  d) Report generator counts ALL active campaigns (10) for Influence
     indicator, but CTI only counts evidence-backed ones (8).
     IMPACT: Influence Activity shows ORANGE when it should be YELLOW.
     FIX: Apply same detection_method filter to report generator.
     
  e) Dashboard shows old CTI breakdown in cached indicator text.
     FIX: Cache flush + report regeneration (already done).

  PRIORITY 3 — ALGORITHMIC
  ─────────────────────────
  
  f) CTI 'hybrid' component (3-7 pts) comes mostly from AIS z-scores
     which have 114% CV — extremely noisy baselines.
     IMPACT: hybrid score fluctuates randomly.
     FIX: Use median instead of mean for AIS baseline, or
          exclude days with known collector downtime.
     
  g) ADS-B has 140% CV — same baseline noise issue.
     FIX: Same as AIS — median baseline + downtime exclusion.
     
  h) Campaigns don't auto-resolve. 11 active campaigns, some from
     Mar 21 with no new signals in 2 days.
     FIX: Auto-resolve campaigns with no new signals in 48h.

  PRIORITY 4 — CLEANUP
  ─────────────────────
  
  i) 12 dead source_types with no matching DAGs pollute the DB.
     FIX: Archive or delete signals from orphaned source types
          that will never collect again (railway, seismic, etc.)
     
  j) DAG naming doesn't match source_types:
     balloons→balloon, telegram-channels→telegram_channel, etc.
     Not a bug per se but confusing for debugging.
""")
