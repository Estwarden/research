# %% [markdown]
# # 07 — Disinformation Campaign Detection
#
# Research notebook for developing event-based campaign detection.
# Uses real signal data from EstWarden (14 days, ~30K signals).
#
# **Pipeline under investigation:**
# ```
# signals → relevance gate → embedding → clustering → framing analysis → campaign
# ```
#
# **Research questions:**
# 1. What embedding model gives best cross-lingual event clustering?
# 2. What cosine threshold optimally groups "same event" signals?
# 3. Can we detect manufactured outrage chains structurally?
# 4. Can we classify hostile framing without LLM (cheap proxy features)?

# %%
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter, defaultdict
from datetime import timedelta

DATA = os.environ.get("ESTWARDEN_DATA", "../data")

# %% [markdown]
# ## 1. Load & Profile Signal Data

# %%
df = pd.read_csv(f"{DATA}/signals_14d.csv", parse_dates=["published_at"])
sources = pd.read_csv(f"{DATA}/media_sources.csv")
clusters = pd.read_csv(f"{DATA}/clusters.csv")
framings = pd.read_csv(f"{DATA}/framings.csv")

print(f"Signals: {len(df):,}")
print(f"Date range: {df.published_at.min().date()} to {df.published_at.max().date()}")
print(f"Source types: {df.source_type.nunique()}")
print(f"Feeds: {df.feed_handle.nunique()}")
print(f"Categories: {df.category.nunique()}")
print(f"With embeddings: {df.has_embedding.sum():,}")
print(f"Clusters: {len(clusters)}")
print(f"Framings: {len(framings)}")

# %%
# Signal volume by category
cat_counts = df.groupby("category").size().sort_values(ascending=False)
fig, ax = plt.subplots(figsize=(10, 5))
cat_counts.head(15).plot.barh(ax=ax, color="steelblue")
ax.set_xlabel("Signals (14 days)")
ax.set_title("Signal Volume by Source Category")
plt.tight_layout()
plt.savefig("signal_categories.png", dpi=150)
plt.show()

# %% [markdown]
# ## 2. Relevance Gate Analysis
#
# How much noise does each source category produce?
# What % of signals from each category are actually Baltic-security-relevant?

# %%
# Define region and topic keyword patterns (same as Go relevance gate)
import re

REGION_RE = re.compile(
    r'(?i)эстон|eesti|estonia|tallinn|таллин|нарва|narva|'
    r'латв|latvij|latvia|riga|рига|'
    r'литв|lietuv|lithuania|vilnius|вильн|'
    r'балт|baltic|прибалт|'
    r'калинин|kaliningrad|псков|pskov|петербург|petersburg|'
    r'беларус|belarus|лукашенк|мурманск|murmansk|'
    r'финлянд|finland|helsinki|польш|poland'
)

TOPIC_RE = re.compile(
    r'(?i)военн|military|войск|оборон|defen|ракет|missile|ядерн|nuclear|'
    r'airspace|безопасност|security|разведк|intelligence|санкци|sanction|'
    r'кибер|cyber|парламент|parliament|президент|president|министр|minister|'
    r'правительств|government|выбор|election|дипломат|diplomat|визов|visa|'
    r'гражданств|citizen|пропаганд|дезинформ|влиян|influence|'
    r'границ|border|мигр|migra|беженц|refugee|русскоязычн|'
    r'протест|protest|сепарат|republic|энерг|energy|газопровод|pipeline|'
    r'nato|нато|article.5|русофоб|гибридн'
)

AUTO_PASS = {'government', 'counter_disinfo', 'defense_osint'}

def is_relevant(row):
    """Python replica of the Go relevance gate."""
    cat = str(row.get("category", ""))
    if cat in AUTO_PASS:
        return True
    text = str(row.get("title", "")) + " " + str(row.get("content", ""))[:500]
    has_region = bool(REGION_RE.search(text))
    has_topic = bool(TOPIC_RE.search(text))
    return has_region and has_topic

df["relevant"] = df.apply(is_relevant, axis=1)

# Relevance rate by category
relevance = df.groupby("category").agg(
    total=("id", "count"),
    relevant=("relevant", "sum")
).assign(rate=lambda x: (x.relevant / x.total * 100).round(1))
relevance = relevance.sort_values("total", ascending=False)
print(relevance.to_string())

# %%
# What passes the gate?
passed = df[df.relevant]
print(f"\nGate: {len(passed):,} / {len(df):,} pass ({len(passed)/len(df)*100:.1f}%)")
print(f"By category:")
print(passed.groupby("category").size().sort_values(ascending=False).head(10))

# %% [markdown]
# ## 3. Cross-Lingual Event Clustering
#
# **Question**: What cosine similarity threshold best groups "same event" signals?
#
# We need to compare signals in RU, EN, ET, LV, LT about the same story.
# Using embeddings, we find pairs of signals with high cosine similarity
# and manually verify if they're about the same event.

# %%
# For this analysis we need embeddings. If not available locally,
# we use title-based deduplication as a proxy.
#
# Proxy method: group by normalized title prefix (first 40 chars, lowercased, stripped)
# This catches exact duplicates and near-duplicates within the same language.

passed_text = passed[passed.source_type.isin(["rss", "telegram", "telegram_channel"])].copy()

def normalize_title(t):
    """Crude normalization — strips non-alphanumeric, lowercase, first 40 chars."""
    t = str(t).lower()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:40]

passed_text["title_key"] = passed_text.title.apply(normalize_title)

# Find title clusters with 2+ signals
title_groups = passed_text.groupby("title_key").filter(lambda g: len(g) >= 2)
title_clusters = passed_text.groupby("title_key").agg(
    count=("id", "count"),
    categories=("category", lambda x: list(set(x))),
    feeds=("feed_handle", lambda x: list(set(x.dropna()))),
    first=("published_at", "min"),
    last=("published_at", "max"),
).sort_values("count", ascending=False)

print(f"Title-based clusters with 2+ signals: {len(title_clusters)}")
print(f"Signals in clusters: {title_clusters['count'].sum()}")
print(f"\nTop clusters:")
print(title_clusters.head(15).to_string())

# %% [markdown]
# ## 4. Source Mixing Analysis
#
# **Key question**: Which events get coverage from BOTH state and trusted media?
# These are the events where framing comparison is possible.

# %%
has_ru_state = {'russian_state', 'ru_state', 'ru_proxy'}
has_trusted = {'estonian_media', 'baltic_media', 'finnish_media', 'polish_media',
               'government', 'counter_disinfo', 'russian_independent', 'trusted'}

title_clusters["has_ru_state"] = title_clusters.categories.apply(
    lambda cats: bool(set(cats) & has_ru_state))
title_clusters["has_trusted"] = title_clusters.categories.apply(
    lambda cats: bool(set(cats) & has_trusted))

mixed = title_clusters[title_clusters.has_ru_state & title_clusters.has_trusted]
print(f"\nMixed-source clusters (state + trusted): {len(mixed)}")
if len(mixed) > 0:
    print(mixed.head(10).to_string())

state_only = title_clusters[title_clusters.has_ru_state & ~title_clusters.has_trusted]
trusted_only = title_clusters[~title_clusters.has_ru_state & title_clusters.has_trusted]
print(f"State-only clusters: {len(state_only)}")
print(f"Trusted-only clusters: {len(trusted_only)}")

# %% [markdown]
# ## 5. Manufactured Outrage Chain Detection
#
# **Hypothesis**: Russian state media creates outrage chains:
# 1. Original event report
# 2. Official reaction (quoting Duma member, senator, etc.)
# 3. Expert outrage
# 4. Editorial summary
# All from same outlet, within 24 hours, about the same topic.

# %%
# Look for chains: same feed, 3+ signals in 24h, same title_key prefix
state_signals = passed_text[passed_text.category.isin(has_ru_state)].copy()
state_signals = state_signals.sort_values(["feed_handle", "published_at"])

chains = []
for feed, group in state_signals.groupby("feed_handle"):
    if len(group) < 3:
        continue
    # Sliding window: find bursts of 3+ signals within 24h
    times = group.published_at.values
    titles = group.title.values
    for i in range(len(times)):
        window = group[(group.published_at >= times[i]) & 
                       (group.published_at <= times[i] + np.timedelta64(24, 'h'))]
        if len(window) >= 3:
            # Check if they share topic (first 20 chars of normalized title)
            keys = window.title.apply(lambda t: normalize_title(t)[:20])
            key_counts = keys.value_counts()
            for key, cnt in key_counts.items():
                if cnt >= 3 and len(key) > 10:
                    chain_signals = window[keys == key]
                    chains.append({
                        "feed": feed,
                        "topic_key": key,
                        "count": cnt,
                        "titles": list(chain_signals.title.values[:5]),
                        "spread_hours": (chain_signals.published_at.max() - 
                                        chain_signals.published_at.min()).total_seconds() / 3600,
                    })

# Deduplicate chains
seen = set()
unique_chains = []
for c in chains:
    key = (c["feed"], c["topic_key"])
    if key not in seen:
        seen.add(key)
        unique_chains.append(c)

print(f"Potential outrage chains: {len(unique_chains)}")
for c in unique_chains[:10]:
    print(f"\n  {c['feed']} — {c['count']} signals in {c['spread_hours']:.1f}h")
    for t in c["titles"][:3]:
        print(f"    → {t[:80]}")

# %% [markdown]
# ## 6. Framing Delta Features (Cheap Proxy)
#
# Can we detect hostile framing without an LLM call?
# 
# **Features to explore:**
# - Emotional language markers (СРОЧНО, !!!, 🔴, BREAKING)
# - Quote attribution patterns (anonymous vs named)
# - Headline verb aggressiveness
# - Russian state media coverage lag (do they wait to add spin?)

# %%
# Emotional markers in state vs trusted media
EMOTIONAL_RE = re.compile(r'СРОЧНО|BREAKING|URGENT|!!!|⚡⚡|🔴🔴|МОЛНИЯ|ТЕРМІНОВО')
HEDGE_RE = re.compile(r'по данным|сообщает|как стало известно|according to|reportedly|sources say')

for cat_group, label in [(has_ru_state, "State"), (has_trusted, "Trusted")]:
    subset = passed_text[passed_text.category.isin(cat_group)]
    if len(subset) == 0:
        continue
    emo_rate = subset.title.apply(lambda t: bool(EMOTIONAL_RE.search(str(t)))).mean()
    hedge_rate = subset.apply(
        lambda r: bool(HEDGE_RE.search(str(r.title) + " " + str(r.content)[:200])), axis=1
    ).mean()
    print(f"{label:8s}: emotional={emo_rate*100:.1f}%  hedging={hedge_rate*100:.1f}%  n={len(subset)}")

# %% [markdown]
# ## 7. Next Steps
#
# Based on findings from this notebook:
#
# 1. **Embedding model comparison** — test multilingual-e5-large vs gemini-embedding-001
#    on manually labeled event pairs (need ~200 labeled pairs)
#
# 2. **Clustering threshold sweep** — plot precision/recall for cosine 0.70-0.95
#
# 3. **Outrage chain detector** — if chains found above, build a structural detector
#    that doesn't need embeddings or LLM
#
# 4. **Framing classifier** — if emotional/hedge features differ significantly,
#    train a lightweight classifier on LLM is_hostile labels
#
# 5. **Temporal coordination metric** — compare inter-arrival times of state vs
#    trusted media for the same events. If Russian state media is significantly more
#    synchronized, that's a coordination signal.
