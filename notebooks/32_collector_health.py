#!/usr/bin/env python3
"""
32. Collector Health Monitoring — Data Freshness Dashboard for Research
========================================================================

Building on:
  - Notebook 09: Found 12 dead collectors since Mar 15-20
  - Notebook 10: Baseline stability — ADS-B CV=140%, AIS CV=109%
  - Notebook 17: Robust baselines recommended per source
  - Notebook 18: Weight recalibration with dead collector handling

This notebook:
  1. Loads signal_daily_counts.csv (90-day window from prod export)
  2. Computes data coverage % per source per week for the full window
  3. Identifies which sources went dead and when (death date)
  4. Computes what % of CTI weight is covered by live sources vs dead
  5. Outputs a health matrix: week × source_type with GREEN/YELLOW/RED
  6. Proposes DEGRADED flag: if live-weight < 70% of total-weight, mark DEGRADED

Designed to be rerunnable monthly — just refresh data/signal_daily_counts.csv
from prod and rerun.

Uses ONLY standard library + numpy.
"""
import csv
import json
import math
import os
from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta, date

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

# ================================================================
# PRODUCTION CTI WEIGHTS (signal sources only — FIMI handled separately)
# ================================================================
from cti_constants import (
    SIGNAL_WEIGHTS as CTI_SIGNAL_WEIGHTS, TOTAL_WEIGHT as TOTAL_CTI_WEIGHT,
    CAMPAIGN_WEIGHT, FABRICATION_WEIGHT, LAUNDERING_WEIGHT,
    NARRATIVE_WEIGHT, GPSJAM_SEV_WEIGHT,
)
FIMI_WEIGHTS = {
    "campaigns": CAMPAIGN_WEIGHT, "fabrication": FABRICATION_WEIGHT,
    "laundering": LAUNDERING_WEIGHT, "narratives": NARRATIVE_WEIGHT,
    "gpsjam_sev": GPSJAM_SEV_WEIGHT,
}
TOTAL_SIGNAL_WEIGHT = sum(CTI_SIGNAL_WEIGHTS.values())  # 72

# Non-CTI sources we still care about for situational awareness
SA_SOURCES = {
    "telegram_channel", "rss_security", "balloon", "defense_rss", "notam",
    "youtube", "youtube_transcript", "deepstate", "osint_perplexity",
    "sentinel", "satellite_analysis", "radiation", "space_weather",
    "embassy", "milwatch", "osint_milbase", "ru_legislation", "breaking",
    "mastodon", "conflict", "stats",
}

# Death threshold: if a source has 0 signals for this many consecutive days
# at the END of the observation window, it's considered dead
DEATH_CONSECUTIVE_DAYS = 3
# Weekly coverage: minimum days with data to be considered "healthy"
HEALTHY_DAYS_PER_WEEK = 5  # 5/7 = 71%
DEGRADED_DAYS_PER_WEEK = 3  # 3/7 = 43%

print("=" * 78)
print("32. COLLECTOR HEALTH MONITORING — DATA FRESHNESS DASHBOARD")
print("=" * 78)

# ================================================================
# 1. LOAD DATA
# ================================================================
print("\n" + "=" * 78)
print("1. LOADING SIGNAL DAILY COUNTS")
print("=" * 78)

# source_type -> {date_str: count}
daily_counts = defaultdict(dict)
all_dates = set()

csv_path = os.path.join(DATA, 'signal_daily_counts.csv')
if not os.path.exists(csv_path):
    print(f"\n  ERROR: {csv_path} not found.")
    print("  Run R-001 first to export data from production.")
    raise SystemExit(1)

with open(csv_path) as f:
    reader = csv.DictReader(f)
    for row in reader:
        dt = row['date']
        st = row['source_type']
        cnt = int(row['signal_count'])
        daily_counts[st][dt] = cnt
        all_dates.add(dt)

all_dates_sorted = sorted(all_dates)
date_min = all_dates_sorted[0]
date_max = all_dates_sorted[-1]

# Build full date range (fill gaps)
d_start = datetime.strptime(date_min, '%Y-%m-%d').date()
d_end = datetime.strptime(date_max, '%Y-%m-%d').date()
full_dates = []
d = d_start
while d <= d_end:
    full_dates.append(d.isoformat())
    d += timedelta(days=1)

all_sources = sorted(daily_counts.keys())
n_days = len(full_dates)

print(f"\n  Date range: {date_min} → {date_max} ({n_days} days)")
print(f"  Sources found: {len(all_sources)}")
print(f"  Total rows in CSV: {sum(len(v) for v in daily_counts.values())}")

# ================================================================
# 2. PER-SOURCE SUMMARY & DEATH DETECTION
# ================================================================
print("\n" + "=" * 78)
print("2. SOURCE HEALTH SUMMARY")
print("=" * 78)

class SourceHealth:
    """Health metrics for a single source."""
    def __init__(self, name, counts_by_date, full_dates):
        self.name = name
        self.counts_by_date = counts_by_date
        self.full_dates = full_dates
        self.n_total_days = len(full_dates)

        # Days with data
        self.active_dates = sorted(d for d, c in counts_by_date.items() if c > 0)
        self.n_active_days = len(self.active_dates)

        # Daily values for active days
        self.values = [counts_by_date.get(d, 0) for d in full_dates]
        self.active_values = [c for c in self.values if c > 0]

        # Coverage
        self.coverage_pct = self.n_active_days / max(self.n_total_days, 1) * 100

        # First and last signal
        self.first_seen = self.active_dates[0] if self.active_dates else None
        self.last_seen = self.active_dates[-1] if self.active_dates else None

        # Stats (on active days only)
        if self.active_values:
            arr = np.array(self.active_values, dtype=float)
            self.mean = float(np.mean(arr))
            self.median = float(np.median(arr))
            self.std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
            self.cv = self.std / self.mean * 100 if self.mean > 0 else 0.0
            self.total = int(np.sum(arr))
            self.p25 = float(np.percentile(arr, 25))
            self.p75 = float(np.percentile(arr, 75))
        else:
            self.mean = self.median = self.std = self.cv = 0.0
            self.total = 0
            self.p25 = self.p75 = 0.0

        # Death detection: count consecutive zero days at end of window
        self.trailing_zero_days = 0
        for d in reversed(full_dates):
            if counts_by_date.get(d, 0) == 0:
                self.trailing_zero_days += 1
            else:
                break

        # Death date: the day after the last signal
        self.is_dead = self.trailing_zero_days >= DEATH_CONSECUTIVE_DAYS
        if self.is_dead and self.last_seen:
            ld = datetime.strptime(self.last_seen, '%Y-%m-%d').date()
            self.death_date = (ld + timedelta(days=1)).isoformat()
        else:
            self.death_date = None

        # CTI weight
        self.cti_weight = CTI_SIGNAL_WEIGHTS.get(name, 0)
        self.is_cti_source = name in CTI_SIGNAL_WEIGHTS

    @property
    def status_emoji(self):
        if not self.first_seen:
            return "⬛"  # never seen
        if self.is_dead:
            return "💀"
        if self.coverage_pct >= 70:
            return "🟢"
        if self.coverage_pct >= 40:
            return "🟡"
        return "🔴"


# Build health objects
sources = {}
for st in all_sources:
    sources[st] = SourceHealth(st, daily_counts[st], full_dates)

# Also check for CTI sources that have ZERO data (not in CSV at all)
for st in CTI_SIGNAL_WEIGHTS:
    if st not in sources:
        sources[st] = SourceHealth(st, {}, full_dates)

# Sort: CTI sources first by weight desc, then non-CTI by total desc
cti_sources = sorted(
    [s for s in sources.values() if s.is_cti_source],
    key=lambda s: -s.cti_weight
)
sa_sources = sorted(
    [s for s in sources.values() if not s.is_cti_source],
    key=lambda s: -s.total
)

print(f"\n  CTI-WEIGHTED SOURCES (affect threat score):")
print(f"  {'Source':20s} {'Weight':>6s} {'Days':>5s} {'Cover%':>7s} {'Mean/d':>8s} {'CV%':>6s} "
      f"{'Last Seen':>12s} {'Trail0':>6s} {'Status'}")
print("  " + "-" * 100)

for s in cti_sources:
    trail_str = f"{s.trailing_zero_days}d" if s.trailing_zero_days > 0 else "-"
    last = s.last_seen or "NEVER"
    status = "DEAD" if s.is_dead else ("NEVER" if not s.first_seen else "LIVE")
    print(f"  {s.name:20s} {s.cti_weight:>6d} {s.n_active_days:>5d} {s.coverage_pct:>6.1f}% "
          f"{s.mean:>8.1f} {s.cv:>5.0f}% {last:>12s} {trail_str:>6s} {s.status_emoji} {status}")

print(f"\n  NON-CTI SOURCES (situational awareness):")
print(f"  {'Source':25s} {'Days':>5s} {'Cover%':>7s} {'Mean/d':>8s} {'Last Seen':>12s} {'Status'}")
print("  " + "-" * 80)

for s in sa_sources:
    if s.total == 0:
        continue
    last = s.last_seen or "NEVER"
    status = "DEAD" if s.is_dead else "LIVE"
    print(f"  {s.name:25s} {s.n_active_days:>5d} {s.coverage_pct:>6.1f}% "
          f"{s.mean:>8.1f} {last:>12s} {s.status_emoji} {status}")

# ================================================================
# 3. DEAD COLLECTORS — DETAILED ANALYSIS
# ================================================================
print("\n" + "=" * 78)
print("3. DEAD COLLECTOR INVENTORY")
print("=" * 78)

dead_cti = [s for s in cti_sources if s.is_dead or not s.first_seen]
dead_sa = [s for s in sa_sources if s.is_dead and s.total > 0]
all_dead = dead_cti + dead_sa

if not all_dead:
    print("\n  No dead collectors detected!")
else:
    print(f"\n  {len(all_dead)} dead source types detected:")
    print(f"\n  {'Source':20s} {'CTI_W':>5s} {'Last Signal':>12s} {'Death Date':>12s} "
          f"{'Days Dead':>9s} {'Total Sigs':>10s} {'Notes'}")
    print("  " + "-" * 95)

    for s in sorted(all_dead, key=lambda x: -(x.cti_weight or 0)):
        death = s.death_date or "NEVER HAD DATA"
        last = s.last_seen or "NEVER"
        days_dead = s.trailing_zero_days
        w_str = str(s.cti_weight) if s.cti_weight > 0 else "-"

        notes = ""
        if s.cti_weight > 0:
            notes = f"⚠️  AFFECTS CTI ({s.cti_weight}pts)"
        elif s.name in ("milwatch", "osint_milbase"):
            notes = "military intelligence gap"
        elif s.name in ("defense_rss", "notam", "embassy"):
            notes = "NATO/defense awareness gap"
        elif s.name in ("conflict",):
            notes = "ACLED-like conflict tracking"
        elif s.name in ("railway", "seismic"):
            notes = "experimental (1 signal ever)"
        elif s.name in ("telegram",):
            notes = "legacy? telegram_channel works"
        elif s.name in ("youtube",):
            notes = "youtube_transcript still active"

        print(f"  {s.name:20s} {w_str:>5s} {last:>12s} {death:>12s} "
              f"{days_dead:>9d} {s.total:>10d} {notes}")

# ================================================================
# 4. CTI WEIGHT COVERAGE — LIVE vs DEAD
# ================================================================
print("\n" + "=" * 78)
print("4. CTI WEIGHT COVERAGE ANALYSIS")
print("=" * 78)

# Per-day: which CTI sources have data?
print(f"\n  Computing daily CTI weight coverage across {n_days} days...\n")

daily_weight_coverage = []  # (date, live_weight, dead_weight, pct)

for dt in full_dates:
    live_w = 0
    dead_w = 0
    for st, w in CTI_SIGNAL_WEIGHTS.items():
        s = sources.get(st)
        if s and s.counts_by_date.get(dt, 0) > 0:
            live_w += w
        else:
            dead_w += w
    pct = live_w / TOTAL_SIGNAL_WEIGHT * 100
    daily_weight_coverage.append((dt, live_w, dead_w, pct))

# Summary stats
coverages = [pct for _, _, _, pct in daily_weight_coverage]
cov_arr = np.array(coverages)

print(f"  Signal weight total: {TOTAL_SIGNAL_WEIGHT} (gpsjam=12, adsb=10, acled=8, firms=8, ...)")
print(f"  FIMI weight total: {sum(FIMI_WEIGHTS.values())} (always computed from campaigns/narratives)")
print(f"  Combined CTI weight: {TOTAL_CTI_WEIGHT}")
print(f"\n  Daily signal-weight coverage over {n_days} days:")
print(f"    Mean:   {np.mean(cov_arr):>5.1f}%")
print(f"    Median: {np.median(cov_arr):>5.1f}%")
print(f"    Min:    {np.min(cov_arr):>5.1f}%  (on {daily_weight_coverage[int(np.argmin(cov_arr))][0]})")
print(f"    Max:    {np.max(cov_arr):>5.1f}%  (on {daily_weight_coverage[int(np.argmax(cov_arr))][0]})")
print(f"    <50%:   {int(np.sum(cov_arr < 50))} days")
print(f"    <70%:   {int(np.sum(cov_arr < 70))} days")

# Current status (most recent 3 days)
recent = daily_weight_coverage[-3:]
print(f"\n  Most recent 3 days:")
for dt, lw, dw, pct in recent:
    sources_live = [st for st in CTI_SIGNAL_WEIGHTS
                    if sources.get(st) and sources[st].counts_by_date.get(dt, 0) > 0]
    sources_dead = [st for st in CTI_SIGNAL_WEIGHTS if st not in sources_live]
    print(f"    {dt}: live_weight={lw}/{TOTAL_SIGNAL_WEIGHT} ({pct:.0f}%)  "
          f"live=[{', '.join(sources_live)}]  dead=[{', '.join(sources_dead)}]")

# ================================================================
# 5. WEEKLY HEALTH MATRIX
# ================================================================
print("\n" + "=" * 78)
print("5. WEEKLY HEALTH MATRIX")
print("=" * 78)

# Build ISO weeks
weeks = OrderedDict()  # week_label -> [dates]
for dt_str in full_dates:
    d = datetime.strptime(dt_str, '%Y-%m-%d').date()
    iso_yr, iso_wk, _ = d.isocalendar()
    wk_label = f"{iso_yr}-W{iso_wk:02d}"
    if wk_label not in weeks:
        weeks[wk_label] = []
    weeks[wk_label].append(dt_str)

# Sources to show in matrix (CTI + key SA sources)
matrix_sources_cti = [st for st in sorted(CTI_SIGNAL_WEIGHTS.keys(),
                                           key=lambda x: -CTI_SIGNAL_WEIGHTS[x])]
# Add high-value SA sources
matrix_sources_sa = ["telegram_channel", "rss_security", "balloon",
                     "deepstate", "sentinel", "radiation"]
matrix_sources = matrix_sources_cti + [s for s in matrix_sources_sa if s in sources]

def week_health(source_name, week_dates):
    """Classify weekly health: 🟢 healthy, 🟡 degraded, 🔴 dead, ⬛ no data expected."""
    s = sources.get(source_name)
    if not s or not s.first_seen:
        return "⬛", 0

    # Count days with data in this week
    days_with_data = sum(1 for d in week_dates
                         if s.counts_by_date.get(d, 0) > 0)
    total_days = len(week_dates)
    total_signals = sum(s.counts_by_date.get(d, 0) for d in week_dates)

    # Was the source even expected to be active this week?
    first = s.first_seen
    last = s.last_seen
    week_start = week_dates[0]
    week_end = week_dates[-1]

    if week_end < first:
        return "⬛", 0  # source didn't exist yet

    if days_with_data == 0:
        return "🔴", 0  # expected data, got nothing
    elif days_with_data >= HEALTHY_DAYS_PER_WEEK:
        return "🟢", total_signals
    elif days_with_data >= DEGRADED_DAYS_PER_WEEK:
        return "🟡", total_signals
    else:
        return "🔴", total_signals

# Truncate source names for display
def trunc(s, n=8):
    return s[:n] if len(s) > n else s

# Print matrix header
hdr = f"  {'Week':>10s} |"
for st in matrix_sources:
    hdr += f" {trunc(st, 6):>6s}"
hdr += " | W_cov%"
print(f"\n{hdr}")
print("  " + "-" * (len(hdr) - 2))

for wk_label, wk_dates in weeks.items():
    row = f"  {wk_label:>10s} |"

    # Compute weight coverage for this week
    wk_live_w = 0
    for st in CTI_SIGNAL_WEIGHTS:
        days_w_data = sum(1 for d in wk_dates
                          if sources.get(st) and sources[st].counts_by_date.get(d, 0) > 0)
        if days_w_data > 0:
            wk_live_w += CTI_SIGNAL_WEIGHTS[st]

    for st in matrix_sources:
        emoji, _ = week_health(st, wk_dates)
        row += f"  {emoji}   "

    wk_pct = wk_live_w / TOTAL_SIGNAL_WEIGHT * 100
    row += f" | {wk_pct:>5.0f}%"
    print(row)

print(f"\n  Legend: 🟢 ≥{HEALTHY_DAYS_PER_WEEK}d/wk  🟡 {DEGRADED_DAYS_PER_WEEK}-{HEALTHY_DAYS_PER_WEEK-1}d/wk  "
      f"🔴 <{DEGRADED_DAYS_PER_WEEK}d/wk  ⬛ not expected")

# ================================================================
# 6. DEGRADED MODE PROPOSAL
# ================================================================
print("\n" + "=" * 78)
print("6. DEGRADED MODE PROPOSAL")
print("=" * 78)

DEGRADED_THRESHOLD = 0.70  # 70% of signal weight must be live

# How many days would be DEGRADED?
degraded_days = [(dt, pct) for dt, _, _, pct in daily_weight_coverage
                 if pct < DEGRADED_THRESHOLD * 100]

print(f"""
  PROPOSAL: Mark CTI as DEGRADED when live signal weight < {DEGRADED_THRESHOLD*100:.0f}%
  
  The CTI score has {TOTAL_SIGNAL_WEIGHT} points of signal weight across
  {len(CTI_SIGNAL_WEIGHTS)} source types. If >30% of that weight has no
  data in the past 24 hours, the score is unreliable — a low score might
  mean "everything is fine" or "we're blind to threats."
  
  Implementation:
    live_weight = Σ(w_i for each source with signals in last 24h)
    coverage = live_weight / {TOTAL_SIGNAL_WEIGHT}
    if coverage < {DEGRADED_THRESHOLD}: flag = DEGRADED
  
  Current status:""")

# Current live weight (last day in data)
last_day = full_dates[-1]
current_live_w = 0
current_dead = []
for st, w in CTI_SIGNAL_WEIGHTS.items():
    s = sources.get(st)
    if s and s.counts_by_date.get(last_day, 0) > 0:
        current_live_w += w
    else:
        current_dead.append((st, w))

current_pct = current_live_w / TOTAL_SIGNAL_WEIGHT * 100

print(f"    Date: {last_day}")
print(f"    Live signal weight: {current_live_w}/{TOTAL_SIGNAL_WEIGHT} ({current_pct:.1f}%)")
if current_dead:
    print(f"    Missing sources: {', '.join(f'{st}({w})' for st, w in current_dead)}")
print(f"    Status: {'🟢 NORMAL' if current_pct >= DEGRADED_THRESHOLD * 100 else '⚠️  DEGRADED'}")

print(f"""
  Historical analysis ({n_days} days):
    Days that would be DEGRADED: {len(degraded_days)}/{n_days} ({len(degraded_days)/n_days*100:.0f}%)""")

if degraded_days:
    print(f"    Worst periods:")
    # Group consecutive degraded days
    runs = []
    current_run = [degraded_days[0]]
    for i in range(1, len(degraded_days)):
        prev_date = datetime.strptime(degraded_days[i-1][0], '%Y-%m-%d').date()
        curr_date = datetime.strptime(degraded_days[i][0], '%Y-%m-%d').date()
        if (curr_date - prev_date).days <= 1:
            current_run.append(degraded_days[i])
        else:
            runs.append(current_run)
            current_run = [degraded_days[i]]
    runs.append(current_run)

    for run in sorted(runs, key=lambda r: -len(r))[:5]:
        start = run[0][0]
        end = run[-1][0]
        avg_pct = np.mean([p for _, p in run])
        print(f"      {start} → {end} ({len(run)} days, avg coverage {avg_pct:.0f}%)")

# ================================================================
# 7. DATA COVERAGE TIMELINE (TEXT-BASED SPARKLINE)
# ================================================================
print("\n" + "=" * 78)
print("7. DAILY COVERAGE TIMELINE (last 30 days)")
print("=" * 78)

sparkline_chars = " ▁▂▃▄▅▆▇█"

# Last 30 days (or all if < 30)
timeline_dates = full_dates[-30:]

print(f"\n  {'Date':>12s} {'Cover%':>7s} {'Live':>4s}/{TOTAL_SIGNAL_WEIGHT} {'Bar'}")
print("  " + "-" * 55)

for dt in timeline_dates:
    live_w = 0
    for st, w in CTI_SIGNAL_WEIGHTS.items():
        s = sources.get(st)
        if s and s.counts_by_date.get(dt, 0) > 0:
            live_w += w
    pct = live_w / TOTAL_SIGNAL_WEIGHT * 100

    # Sparkline bar (max 20 chars)
    bar_len = int(pct / 100 * 20)
    bar = "█" * bar_len + "░" * (20 - bar_len)

    flag = ""
    if pct < DEGRADED_THRESHOLD * 100:
        flag = " ⚠️  DEGRADED"
    elif pct < 85:
        flag = " ⚡ partial"

    print(f"  {dt:>12s} {pct:>6.0f}% {live_w:>4d}/{TOTAL_SIGNAL_WEIGHT} {bar}{flag}")

# ================================================================
# 8. SOURCE LIFECYCLE TIMELINE
# ================================================================
print("\n" + "=" * 78)
print("8. SOURCE LIFECYCLE — WHEN DID SOURCES START AND STOP?")
print("=" * 78)

# Sort all sources by first_seen date
lifecycle = sorted(
    [(s.name, s.first_seen, s.last_seen, s.is_dead, s.cti_weight, s.n_active_days, s.total)
     for s in sources.values() if s.first_seen],
    key=lambda x: x[1]
)

print(f"\n  {'Source':25s} {'First Seen':>12s} {'Last Seen':>12s} {'Active':>6s} "
      f"{'Total':>8s} {'CTI_W':>5s} {'Lifespan'}")
print("  " + "-" * 95)

for name, first, last, dead, w, days, total in lifecycle:
    f_dt = datetime.strptime(first, '%Y-%m-%d').date()
    l_dt = datetime.strptime(last, '%Y-%m-%d').date()
    span = (l_dt - f_dt).days + 1
    w_str = str(w) if w > 0 else "-"

    # Visual lifespan bar (one char per week, approx)
    weeks_span = max(1, span // 7)
    if dead:
        bar = "▓" * max(1, weeks_span) + "░" * max(0, 3)
        status = f"DEAD since ~{last}"
    else:
        bar = "▓" * max(1, weeks_span) + "▶"
        status = f"LIVE ({span}d span)"

    print(f"  {name:25s} {first:>12s} {last:>12s} {days:>5d}d "
          f"{total:>8d} {w_str:>5s} {bar} {status}")

# ================================================================
# 9. IMPACT ON CTI ACCURACY
# ================================================================
print("\n" + "=" * 78)
print("9. IMPACT ON CTI ACCURACY")
print("=" * 78)

# Load threat_index_history for correlation
tih_path = os.path.join(DATA, 'threat_index_history.csv')
threat_scores = {}  # date -> score
if os.path.exists(tih_path):
    with open(tih_path) as f:
        for row in csv.DictReader(f):
            if row['region'] == 'baltic':
                threat_scores[row['date']] = float(row['score'])

if threat_scores:
    print(f"\n  Cross-referencing CTI scores with data coverage ({len(threat_scores)} days)...")

    overlap_dates = sorted(set(threat_scores.keys()) & set(full_dates))
    if overlap_dates:
        scores = []
        coverages_overlap = []
        for dt in overlap_dates:
            scores.append(threat_scores[dt])
            live_w = 0
            for st, w in CTI_SIGNAL_WEIGHTS.items():
                s = sources.get(st)
                if s and s.counts_by_date.get(dt, 0) > 0:
                    live_w += w
            coverages_overlap.append(live_w / TOTAL_SIGNAL_WEIGHT * 100)

        scores_arr = np.array(scores)
        cov_overlap_arr = np.array(coverages_overlap)

        # Correlation between coverage and CTI score
        if len(scores_arr) > 2 and np.std(cov_overlap_arr) > 0 and np.std(scores_arr) > 0:
            corr = np.corrcoef(cov_overlap_arr, scores_arr)[0, 1]
        else:
            corr = float('nan')

        # Split into high-coverage vs low-coverage days
        median_cov = float(np.median(cov_overlap_arr))
        high_cov = scores_arr[cov_overlap_arr >= median_cov]
        low_cov = scores_arr[cov_overlap_arr < median_cov]

        print(f"\n    Overlap period: {overlap_dates[0]} → {overlap_dates[-1]} ({len(overlap_dates)} days)")
        print(f"    Coverage-Score correlation: r={corr:.3f}")
        print(f"    {'':>4s}{'High coverage (≥{:.0f}%)'.format(median_cov):>30s}  {'Low coverage (<{:.0f}%)'.format(median_cov):>30s}")
        print(f"    {'Mean CTI':>15s}: {np.mean(high_cov):>10.1f}  {np.mean(low_cov) if len(low_cov) > 0 else float('nan'):>10.1f}")
        print(f"    {'Median CTI':>15s}: {np.median(high_cov):>10.1f}  {np.median(low_cov) if len(low_cov) > 0 else float('nan'):>10.1f}")
        print(f"    {'N days':>15s}: {len(high_cov):>10d}  {len(low_cov):>10d}")

        print(f"""
    INTERPRETATION:
      {'Positive' if corr > 0.1 else 'Negative' if corr < -0.1 else 'Weak'} correlation (r={corr:.3f}) between coverage and CTI score.
      {'⚠️  Higher coverage → higher scores suggests the CTI partially measures data availability, not just threat.' if corr > 0.3 else ''}
      {'✅ Low correlation suggests CTI score is not dominated by collector health.' if abs(corr) < 0.3 else ''}
      {'⚠️  Negative correlation suggests blind spots may MASK elevated threat.' if corr < -0.3 else ''}""")
    else:
        print("    No overlapping dates between CTI history and signal counts.")
else:
    print("\n  No threat_index_history.csv available — skipping CTI correlation.")

# ================================================================
# 10. SUMMARY & RECOMMENDATIONS
# ================================================================
print("\n" + "=" * 78)
print("10. SUMMARY & RECOMMENDATIONS")
print("=" * 78)

n_dead_cti = len(dead_cti)
dead_cti_weight = sum(s.cti_weight for s in dead_cti)
n_dead_sa = len(dead_sa)
n_dead_total = len(all_dead)

print(f"""
  COLLECTOR HEALTH SUMMARY ({date_max}):
  
    Total source types in data:    {len(all_sources)}
    CTI-weighted sources:          {len(CTI_SIGNAL_WEIGHTS)} (total weight: {TOTAL_SIGNAL_WEIGHT})
    
    Dead CTI sources:              {n_dead_cti} (weight: {dead_cti_weight}/{TOTAL_SIGNAL_WEIGHT})
    Dead SA sources:               {n_dead_sa}
    Total dead:                    {n_dead_total}
    
    Current live CTI weight:       {current_live_w}/{TOTAL_SIGNAL_WEIGHT} ({current_pct:.0f}%)
    Current DEGRADED status:       {'YES' if current_pct < DEGRADED_THRESHOLD * 100 else 'NO'}
""")

# Detailed dead CTI sources
if dead_cti:
    print("  DEAD CTI SOURCES (directly affecting threat score):")
    for s in dead_cti:
        print(f"    💀 {s.name} (weight={s.cti_weight}) — "
              f"{'last seen ' + s.last_seen if s.last_seen else 'NEVER had data'}"
              f"{', dead since ~' + s.death_date if s.death_date else ''}")
    print()

print(f"""  RECOMMENDATIONS:
  
  1. DEGRADED FLAG: Implement CTI DEGRADED mode when live_weight < {DEGRADED_THRESHOLD*100:.0f}%
     of total signal weight ({int(TOTAL_SIGNAL_WEIGHT * DEGRADED_THRESHOLD)}/{TOTAL_SIGNAL_WEIGHT}).
     Current value: {current_pct:.0f}% → {'NORMAL' if current_pct >= DEGRADED_THRESHOLD * 100 else 'DEGRADED'}
     
     Implementation in Go:
       liveWeight := 0
       for source, weight := range ctiWeights {{
           if hasDataInLast24h(source) {{ liveWeight += weight }}
       }}
       if float64(liveWeight)/float64(totalWeight) < {DEGRADED_THRESHOLD} {{
           score.Flag = "DEGRADED"
       }}
  
  2. DEAD SOURCE REMOVAL: Sources with no data for >{DEATH_CONSECUTIVE_DAYS} days should
     have their CTI weight set to 0 automatically. This prevents the denominator
     from being inflated by sources that can't contribute.
     
     Dynamic weight formula:
       effective_weight(source) = base_weight × I(has_data_in_7d)
       total_weight = Σ effective_weight(source)
  
  3. COLLECTOR MONITORING: Run this notebook monthly or set up a cron check:
     - Alert if any CTI source has 0 signals for 48h
     - Alert if live_weight drops below {DEGRADED_THRESHOLD*100:.0f}%
     - Track collector death/recovery dates for post-mortem analysis
  
  4. BLIND SPOT AWARENESS: Dead collectors create unmonitored gaps.
     Current blind spots:""")

for s in dead_cti:
    domain = {
        "acled": "conflict events (kinetic activity, protests)",
        "gdelt": "global military news attention",
        "ioda": "internet outages / infrastructure disruption",
        "adsb": "military flight tracking",
        "firms": "thermal anomalies at military sites",
        "ais": "naval vessel tracking",
        "gpsjam": "GPS interference / electronic warfare",
        "telegram": "information operations volume",
        "rss": "media narrative temperature",
        "energy": "energy market disruption",
        "business": "economic/business signals",
    }.get(s.name, s.name)
    if s.is_dead or not s.first_seen:
        print(f"       - {s.name} ({s.cti_weight}pts): {domain}")

print()

# ================================================================
# EXPORT: Health summary JSON for programmatic use
# ================================================================
health_export = {
    "generated": date_max,
    "date_range": {"start": date_min, "end": date_max, "days": n_days},
    "cti_weight": {
        "total_signal": TOTAL_SIGNAL_WEIGHT,
        "total_fimi": sum(FIMI_WEIGHTS.values()),
        "total_cti": TOTAL_CTI_WEIGHT,
        "current_live": current_live_w,
        "current_pct": round(current_pct, 1),
        "degraded": current_pct < DEGRADED_THRESHOLD * 100,
    },
    "degraded_threshold": DEGRADED_THRESHOLD,
    "sources": {},
}

for s in sources.values():
    health_export["sources"][s.name] = {
        "cti_weight": s.cti_weight,
        "is_cti_source": s.is_cti_source,
        "first_seen": s.first_seen,
        "last_seen": s.last_seen,
        "active_days": s.n_active_days,
        "coverage_pct": round(s.coverage_pct, 1),
        "total_signals": s.total,
        "mean_daily": round(s.mean, 1),
        "cv_pct": round(s.cv, 1),
        "is_dead": s.is_dead,
        "death_date": s.death_date,
        "trailing_zero_days": s.trailing_zero_days,
    }

export_path = os.path.join(OUTPUT, 'collector_health.json')
with open(export_path, 'w') as f:
    json.dump(health_export, f, indent=2)
print(f"  Health summary exported to: {export_path}")
print()
