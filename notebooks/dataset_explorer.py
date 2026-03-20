# %% [markdown]
# # Dataset Explorer
# Load and explore the EstWarden Baltic Security Dataset.
# Download from: https://github.com/Estwarden/dataset

# %%
import json
from collections import Counter, defaultdict
from datetime import datetime

# Load the dataset files (download from Estwarden/dataset repo)
DATA_DIR = "../data"  # or wherever you cloned the dataset

def load_jsonl(filename):
    signals = []
    with open(f"{DATA_DIR}/{filename}") as f:
        for line in f:
            try: signals.append(json.loads(line.strip()))
            except: pass
    return signals

# %% [markdown]
# ## Load all datasets

# %%
media = load_jsonl("media_signals.jsonl")
military = load_jsonl("military_signals.jsonl")
economic = load_jsonl("economic_signals.jsonl")
environmental = load_jsonl("environmental_signals.jsonl")
tags = load_jsonl("narrative_tags.jsonl")
reports = load_jsonl("daily_reports.jsonl")
campaigns = load_jsonl("campaigns.jsonl")
indicators = load_jsonl("indicators.jsonl")

all_signals = media + military + economic + environmental

print(f"Media:         {len(media):>7,d} signals")
print(f"Military:      {len(military):>7,d} signals")
print(f"Economic:      {len(economic):>7,d} signals")
print(f"Environmental: {len(environmental):>7,d} signals")
print(f"TOTAL:         {len(all_signals):>7,d} signals")
print(f"")
print(f"Narrative tags:  {len(tags):>5,d}")
print(f"Daily reports:   {len(reports):>5,d}")
print(f"Campaigns:       {len(campaigns):>5,d}")
print(f"Indicators:      {len(indicators):>5,d}")

# %% [markdown]
# ## Source type distribution

# %%
sources = Counter(s.get("source_type", "?") for s in all_signals)
print("Source type distribution:\n")
for src, cnt in sources.most_common(20):
    pct = cnt / len(all_signals) * 100
    bar = "█" * int(pct)
    print(f"  {src:25s} {cnt:>6,d} ({pct:5.1f}%) {bar}")

# %% [markdown]
# ## Temporal coverage

# %%
daily = defaultdict(int)
for s in all_signals:
    pub = s.get("published_at", "")
    if pub and len(pub) >= 10:
        daily[pub[:10]] += 1

dates = sorted(daily.keys())
print(f"Date range: {dates[0]} → {dates[-1]}")
print(f"Days with data: {len(dates)}")
print(f"Total signals/day: min={min(daily.values())}, max={max(daily.values())}, avg={sum(daily.values())//len(daily)}")

# Show busiest days
print("\nBusiest days:")
for date, count in sorted(daily.items(), key=lambda x: -x[1])[:5]:
    print(f"  {date}: {count:,d} signals")

# %% [markdown]
# ## Narrative tag analysis

# %%
codes = {"N1": "Russophobia/Persecution", "N2": "War Escalation Panic",
         "N3": "Aid = Theft", "N4": "Delegitimization", "N5": "Isolation/Victimhood"}

tag_counts = Counter(t.get("code", "?") for t in tags)
print("Narrative classifications:\n")
for code in ["N1", "N2", "N3", "N4", "N5"]:
    cnt = tag_counts.get(code, 0)
    print(f"  {code} {codes[code]:30s} {cnt:>4d} tags")

# Confidence distribution
confs = [t.get("confidence", 0) for t in tags]
if confs:
    print(f"\nConfidence: min={min(confs):.2f}, max={max(confs):.2f}, avg={sum(confs)/len(confs):.2f}")

# %% [markdown]
# ## Campaign analysis

# %%
print("Detected influence campaigns:\n")
for c in sorted(campaigns, key=lambda x: x.get("detected_at", "")):
    print(f"  [{c.get('severity', '?'):8s}] {c.get('name', '?')}")
    if c.get("summary"):
        print(f"           {c['summary'][:120]}")
    print()

# %% [markdown]
# ## Daily threat reports

# %%
print("Daily CTI scores:\n")
for r in sorted(reports, key=lambda x: x.get("date", "")):
    level = r.get("cti_level", "?")
    score = r.get("cti_score", 0)
    emoji = {"GREEN": "🟢", "YELLOW": "🟡", "ORANGE": "🟠", "RED": "🔴"}.get(level, "⚪")
    print(f"  {r.get('date', '?')} {emoji} {level:8s} {score:5.1f}/100")

# %% [markdown]
# ## Geographic distribution (signals with coordinates)

# %%
geo = [(s.get("latitude"), s.get("longitude"), s.get("source_type"))
       for s in all_signals
       if s.get("latitude") and s.get("longitude")]
print(f"Signals with coordinates: {len(geo):,d} / {len(all_signals):,d}")

geo_sources = Counter(g[2] for g in geo)
print("\nBy source:")
for src, cnt in geo_sources.most_common():
    print(f"  {src:20s} {cnt:>6,d}")
