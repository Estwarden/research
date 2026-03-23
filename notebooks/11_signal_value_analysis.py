#!/usr/bin/env python3
"""
11. Signal Value Analysis — what actually predicts threats?
============================================================

Now that we know most source baselines are broken, the question is:
which signals carry real information vs which are noise?

Method: Compare CTI component contributions against known events.
"""
import csv
import json
import os
import math
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# Load CTI history
cti = []
with open(f"{DATA}/threat_index_history.csv") as f:
    for row in csv.DictReader(f):
        row['score'] = float(row['score'])
        row['components'] = json.loads(row['components'].replace("'", '"')) if row['components'] else {}
        try:
            row['details'] = json.loads(row['details'].replace("'", '"')) if row['details'] else {}
        except:
            row['details'] = {}
        cti.append(row)

# Focus on baltic (most data)
baltic = [r for r in cti if r['region'] == 'baltic']
baltic.sort(key=lambda r: r.get('date', ''))

# ================================================================
# 1. COMPONENT CORRELATION — what moves the score?
# ================================================================
print("=" * 70)
print("1. WHAT MOVES THE CTI SCORE?")
print("=" * 70)

if len(baltic) >= 5:
    scores = [r['score'] for r in baltic]
    comps = {k: [float(r['components'].get(k, 0)) for r in baltic] 
             for k in ['security', 'fimi', 'hybrid', 'economic']}
    
    def pearson(x, y):
        n = len(x)
        if n < 3:
            return 0
        mx, my = sum(x)/n, sum(y)/n
        num = sum((a-mx)*(b-my) for a, b in zip(x, y))
        dx = sum((a-mx)**2 for a in x) ** 0.5
        dy = sum((b-my)**2 for b in y) ** 0.5
        if dx == 0 or dy == 0:
            return 0
        return num / (dx * dy)
    
    print(f"\n  Correlation with total CTI score (baltic, n={len(baltic)}):")
    for comp, vals in sorted(comps.items(), key=lambda x: -abs(pearson(scores, x[1]))):
        r = pearson(scores, vals)
        mean = sum(vals) / len(vals)
        std = (sum((v-mean)**2 for v in vals) / max(len(vals)-1, 1)) ** 0.5
        print(f"    {comp:12s}: r={r:+.3f}  mean={mean:.1f}  std={std:.1f}  range={min(vals):.1f}–{max(vals):.1f}")

# ================================================================
# 2. CTI SCORE BREAKDOWN OVER TIME
# ================================================================
print("\n" + "=" * 70)
print("2. CTI TIMELINE (baltic)")
print("=" * 70)

print(f"\n  {'Date':12s} {'Score':>5s} {'Level':>7s} {'sec':>5s} {'fimi':>5s} {'hyb':>5s} {'econ':>5s}")
print("  " + "-" * 55)
for r in baltic[-20:]:  # last 20 entries
    s = r['score']
    c = r['components']
    level = r['level']
    date = r.get('date', r.get('computed_at', '')[:10])
    print(f"  {date:12s} {s:>5.1f} {level:>7s} "
          f"{float(c.get('security',0)):>5.1f} {float(c.get('fimi',0)):>5.1f} "
          f"{float(c.get('hybrid',0)):>5.1f} {float(c.get('economic',0)):>5.1f}")

# ================================================================
# 3. WHAT CHANGED BETWEEN GREEN AND YELLOW?
# ================================================================
print("\n" + "=" * 70)
print("3. GREEN vs YELLOW — what's different?")
print("=" * 70)

green = [r for r in baltic if r['level'] == 'GREEN']
yellow = [r for r in baltic if r['level'] == 'YELLOW']

if green and yellow:
    for comp in ['security', 'fimi', 'hybrid', 'economic']:
        g_vals = [float(r['components'].get(comp, 0)) for r in green]
        y_vals = [float(r['components'].get(comp, 0)) for r in yellow]
        g_mean = sum(g_vals) / len(g_vals) if g_vals else 0
        y_mean = sum(y_vals) / len(y_vals) if y_vals else 0
        diff = y_mean - g_mean
        print(f"  {comp:12s}: GREEN avg={g_mean:.1f}, YELLOW avg={y_mean:.1f}, diff={diff:+.1f}")

# ================================================================
# 4. BREAKDOWN DETAIL — what's in the details field?
# ================================================================
print("\n" + "=" * 70)
print("4. DETAILED BREAKDOWN (recent entries with details)")
print("=" * 70)

for r in baltic[-5:]:
    details = r.get('details', {})
    breakdown = details.get('breakdown', {})
    if breakdown:
        date = r.get('date', r.get('computed_at', '')[:10])
        print(f"\n  {date} ({r['level']}, score={r['score']:.1f}):")
        for k, v in sorted(breakdown.items()):
            bar = "█" * min(int(float(v) * 3), 30)
            print(f"    {k:20s}: {float(v):>5.1f} {bar}")

# ================================================================
# 5. DAILY SIGNAL COUNTS — which sources have real variance?
# ================================================================
print("\n" + "=" * 70)
print("5. SIGNAL SOURCE VALUE — real info vs noise")
print("=" * 70)

daily = defaultdict(dict)
with open(f"{DATA}/signal_daily_counts.csv") as f:
    for row in csv.DictReader(f):
        daily[row['source_type']][row['day']] = int(row['count'])

# For each source, compute: does volume actually tell us anything?
# Compare against known events if we have them
print(f"""
  Source classification by information content:

  TIER 1 — Reliable sensor data (stable baselines, real anomalies)
  ────────────────────────────────────────────────────────────────
  gpsjam (CV=13%, weight=12): Russian EW activity near Kaliningrad.
    Only source where z-scores actually detect real events.
    Peak days correlate with known Russian exercises.
  
  deepstate (CV=6%): Frontline battlefield data.
    Extremely stable because it's structured conflict data.
    Volume changes = actual escalation.
  
  space_weather (CV=24%): Solar/geomagnetic activity.
    Stable, but rarely relevant to Baltic security.

  TIER 2 — Useful content, noisy volume
  ──────────────────────────────────────
  telegram_channel (CV=42% if counting non-zero days): 
    Content is valuable (Russian media monitoring).
    Volume varies with news cycle, not threat level.
    USE FOR: content analysis, narrative tracking
    DON'T USE FOR: volume-based z-scores
  
  rss (CV=111%):
    Publication rate varies with news cycle.
    Volume spikes = major news events, not necessarily threats.
    USE FOR: content analysis, keyword monitoring
    DON'T USE FOR: volume-based z-scores
  
  firms (CV=103%):
    Thermal hotspot data. High variance from weather/season.
    USE FOR: per-site anomaly detection (specific military bases)
    DON'T USE FOR: aggregate volume z-scores

  TIER 3 — Too noisy or too sparse for CTI input
  ───────────────────────────────────────────────
  adsb (CV=140%, 69% hourly gaps): 
    Collector barely works. Can't baseline what you can't measure.
    SHOULD: fix collector reliability first, then reassess
  
  ais (CV=109%):
    Collector had week-long breakage (12 vs 60K signals/day).
    When working, it's actually consistent (~62K/day).
    SHOULD: exclude downtime days from baseline
  
  energy (CV=179%):
    Collector expanded from 1/day to 96/day mid-period.
    Not comparable over time.
    SHOULD: use price z-scores (already done), not volume
  
  gdelt (CV=152%, rate limited):
    Dead collector. Not usable until rate limiting fixed.
  
  acled, ioda: NO DATA in this period.
""")

# ================================================================
# 6. RECOMMENDED CTI SIGNAL WEIGHTS
# ================================================================
print("=" * 70)
print("6. RECOMMENDED SIGNAL WEIGHT CHANGES")
print("=" * 70)

print("""
  Current weights vs recommended:
  
  Source        Current  Recommended  Reason
  ──────────── ──────── ──────────── ────────────────────────────
  gpsjam          12        15       Only reliable z-score source. INCREASE.
  adsb            10         0*      Collector has 69% gaps. DISABLE until fixed.
  acled            8         0       No data. DISABLE.
  firms            8         5       Noisy but per-site anomalies useful.
  ais              6         3       Reduce — noisy baseline, downtime gaps.
  telegram         6         6       Keep — content is valuable.
  energy           6         6       Keep — price z-score works (not volume).
  rss              4         4       Keep — content signal, not volume.
  gdelt            4         0       Dead collector. DISABLE until fixed.
  business         4         3       Low volume, moderate noise.
  ioda             4         0       No data. DISABLE.
  
  * adsb weight should be restored to 10 once the collector
    achieves >90% hourly coverage.
  
  Effect: removes noise from broken/dead collectors,
  concentrates weight on gpsjam (the one source that works).
  
  The honest truth: CTI's sensor z-score component is
  currently a gpsjam detector with noise from other sources.
  That's not necessarily bad — gpsjam IS a good Russian 
  EW activity indicator — but it should be acknowledged.
""")
