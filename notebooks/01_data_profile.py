# %% [markdown]
# # 01 — Data Profile
# Shape the raw dataset into a working daily matrix aligned with indicator labels.
#
# **Output:** `daily_matrix.parquet` — every other notebook loads this.

# %%
import json, os
import numpy as np
import pandas as pd

DATA = os.environ.get("ESTWARDEN_DATA", "../data")

def load(f):
    out = []
    for line in open(f"{DATA}/{f}"):
        try: out.append(json.loads(line.strip()))
        except: pass
    return out

media = load("media_signals.jsonl")
military = load("military_signals.jsonl")
economic = load("economic_signals.jsonl")
environmental = load("environmental_signals.jsonl")
indicators = load("indicators.jsonl")
tags = load("narrative_tags.jsonl")
campaigns = load("campaigns.jsonl")

all_sigs = media + military + economic + environmental
print(f"Signals: {len(all_sigs):,d}")
print(f"Indicators: {len(indicators)} across {len(set(i['report_date'] for i in indicators))} days")
print(f"Narrative tags: {len(tags)},  Campaigns: {len(campaigns)}")

# %% [markdown]
# ## Build daily signal counts per source (2026 only)

# %%
df_sig = pd.DataFrame(all_sigs)
df_sig["date"] = pd.to_datetime(df_sig["published_at"], errors="coerce").dt.date
df_sig = df_sig[df_sig["date"] >= pd.Timestamp("2026-01-01").date()].copy()

# Pivot: rows=date, columns=source_type, values=count
daily = df_sig.groupby(["date", "source_type"]).size().unstack(fill_value=0)
daily.index = pd.to_datetime(daily.index)
print(f"Daily matrix: {daily.shape[0]} days × {daily.shape[1]} sources")
print(f"Range: {daily.index.min().date()} → {daily.index.max().date()}")
print()
daily.sum().sort_values(ascending=False)

# %% [markdown]
# ## Source activity heatmap

# %%
import matplotlib.pyplot as plt
import seaborn as sns

fig, ax = plt.subplots(figsize=(16, 8))
# Normalize per-source for heatmap
normed = daily.div(daily.max()).fillna(0)
sns.heatmap(normed.T, cmap="YlOrRd", ax=ax, xticklabels=7)
ax.set_title("Daily Signal Volume (normalized per source)")
ax.set_ylabel("")
plt.tight_layout()
plt.savefig("source_heatmap.png", dpi=150)
plt.show()

# %% [markdown]
# ## Build indicator labels

# %%
STATUS = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}
df_ind = pd.DataFrame(indicators)
df_ind["status_num"] = df_ind["status"].map(STATUS)
df_ind["report_date"] = pd.to_datetime(df_ind["report_date"])

# Per-date: max status per category + yellow count
label_pivot = df_ind.pivot_table(index="report_date", columns="category",
                                  values="status_num", aggfunc="max", fill_value=0)
label_pivot["n_yellow"] = (label_pivot >= 1).sum(axis=1)
label_pivot["is_elevated"] = (label_pivot["n_yellow"] > 0).astype(int)

# Yellow labels per date
yellow_labels = df_ind[df_ind["status_num"] >= 1].groupby("report_date")["label"].apply(list)
label_pivot["yellow_labels"] = yellow_labels

print(f"YELLOW+ days: {label_pivot['is_elevated'].sum()} / {len(label_pivot)}")
print(f"\nYELLOW indicator frequency:")
all_ylabels = df_ind[df_ind["status_num"] >= 1]["label"].value_counts()
print(all_ylabels.to_string())

# %% [markdown]
# ## Align and save

# %%
# Join signal counts with labels
combined = daily.join(label_pivot[["n_yellow", "is_elevated"]], how="inner")
combined["n_yellow"] = combined["n_yellow"].fillna(0).astype(int)
combined["is_elevated"] = combined["is_elevated"].fillna(0).astype(int)
combined["total"] = daily.loc[combined.index].sum(axis=1)

# Add category columns
for cat in label_pivot.columns:
    if cat not in ("n_yellow", "is_elevated", "yellow_labels"):
        combined[f"cat_{cat}"] = label_pivot[cat].reindex(combined.index).fillna(0).astype(int)

combined.to_parquet("daily_matrix.parquet")
combined.to_csv("daily_matrix.csv")
print(f"Saved daily_matrix.parquet: {combined.shape}")
print(f"Sources: {list(daily.columns)}")
print(f"\nDescriptive stats:")
combined.describe().round(1)
