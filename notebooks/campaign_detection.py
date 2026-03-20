# %% [markdown]
# # Campaign Detection Analysis
# Explore how influence campaigns are detected from signal patterns.
# Uses the EstWarden public dataset.

# %%
import json
from collections import defaultdict, Counter
from datetime import datetime, timedelta

DATA_DIR = "../data"

def load_jsonl(f):
    return [json.loads(l) for l in open(f"{DATA_DIR}/{f}") if l.strip()]

# %%
media = load_jsonl("media_signals.jsonl")
tags = load_jsonl("narrative_tags.jsonl")
campaigns = load_jsonl("campaigns.jsonl")

print(f"Media signals: {len(media):,}")
print(f"Narrative tags: {len(tags):,}")
print(f"Campaigns: {len(campaigns):,}")

# %% [markdown]
# ## Signal volume over time by source

# %%
daily_by_source = defaultdict(lambda: defaultdict(int))
for s in media:
    pub = s.get("published_at", "")[:10]
    src = s.get("source_type", "?")
    if pub and pub >= "2025-01-01":
        daily_by_source[pub][src] += 1

dates = sorted(daily_by_source.keys())
print(f"Date range: {dates[0]} → {dates[-1]}")
print(f"\nDaily volume (last 14 days):")
for d in dates[-14:]:
    counts = daily_by_source[d]
    total = sum(counts.values())
    top = ", ".join(f"{k}={v}" for k,v in sorted(counts.items(), key=lambda x:-x[1])[:3])
    print(f"  {d}: {total:>4d} signals ({top})")

# %% [markdown]
# ## Narrative spikes — potential campaign indicators

# %%
# Group tags by date
tag_by_date = defaultdict(list)
for t in tags:
    created = t.get("created_at", "")[:10]
    if created:
        tag_by_date[created].append(t.get("code", "?"))

print("Narrative tag volume by date:\n")
for date in sorted(tag_by_date.keys()):
    codes = Counter(tag_by_date[date])
    total = len(tag_by_date[date])
    breakdown = " ".join(f"{c}={n}" for c, n in codes.most_common())
    print(f"  {date}: {total:>3d} tags — {breakdown}")

# %% [markdown]
# ## Z-score spike detection
# Detect days where narrative volume is >2 standard deviations above the 7-day mean.

# %%
import statistics

daily_totals = {d: len(codes) for d, codes in tag_by_date.items()}
dates_sorted = sorted(daily_totals.keys())

print("Anomalous narrative days (z > 2.0):\n")
for i in range(7, len(dates_sorted)):
    window = [daily_totals.get(dates_sorted[j], 0) for j in range(i-7, i)]
    mean = statistics.mean(window)
    stddev = statistics.stdev(window) if len(window) > 1 else 1
    current = daily_totals.get(dates_sorted[i], 0)
    z = (current - mean) / max(stddev, 1)
    if z > 2.0:
        print(f"  {dates_sorted[i]}: {current} tags (z={z:.1f}, mean={mean:.1f})")

# %% [markdown]
# ## Cross-source coordination
# Check if multiple sources spike on the same day (coordination signal).

# %%
print("Days with multi-source spikes:\n")
for d in dates[-30:]:
    counts = daily_by_source.get(d, {})
    if len(counts) >= 3:
        above_avg = sum(1 for src, cnt in counts.items() if cnt > 5)
        if above_avg >= 2:
            srcs = ", ".join(f"{k}={v}" for k,v in sorted(counts.items(), key=lambda x:-x[1])[:4])
            print(f"  {d}: {above_avg} sources active — {srcs}")

# %% [markdown]
# ## Known campaigns vs detected patterns

# %%
print("Known campaigns:\n")
for c in campaigns:
    detected = c.get("detected_at", "")[:10]
    print(f"  {detected} [{c.get('severity','?'):8s}] {c.get('name','?')}")
    if c.get("summary"):
        print(f"           {c['summary'][:150]}")
    print()
