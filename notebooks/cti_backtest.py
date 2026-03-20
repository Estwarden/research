# %% [markdown]
# # CTI Backtest
# Backtest the Composite Threat Index against the EstWarden public API.
# Analyzes historical threat scores and validates weighting.

# %%
import json
import urllib.request
import matplotlib.pyplot as plt
from datetime import datetime

API = "https://estwarden.eu"

def api(path):
    with urllib.request.urlopen(f"{API}{path}", timeout=15) as r:
        return json.loads(r.read())

# %% [markdown]
# ## Load 90-day threat history

# %%
history = api("/api/history?days=90")
if isinstance(history, dict):
    history = history.get("history", [])

dates = [h["date"] for h in history]
scores = [h.get("score", 0) for h in history]
levels = [h.get("level", "GREEN") for h in history]

print(f"Loaded {len(dates)} days of data")
print(f"Score range: {min(scores):.1f} — {max(scores):.1f}")
print(f"Mean: {sum(scores)/len(scores):.1f}")

# %% [markdown]
# ## Plot threat trend

# %%
fig, ax = plt.subplots(figsize=(14, 5))

colors = {"GREEN": "#22c55e", "YELLOW": "#eab308", "ORANGE": "#f97316", "RED": "#ef4444"}
bar_colors = [colors.get(l, "#6b7280") for l in levels]

ax.bar(range(len(dates)), scores, color=bar_colors, width=0.8)
ax.set_ylabel("CTI Score")
ax.set_title("Baltic Composite Threat Index — 90 Day History")
ax.set_ylim(0, 100)
ax.axhline(y=25, color="gray", linestyle="--", alpha=0.3, label="YELLOW threshold")
ax.axhline(y=50, color="gray", linestyle="--", alpha=0.3, label="ORANGE threshold")
ax.axhline(y=75, color="gray", linestyle="--", alpha=0.3, label="RED threshold")

# X-axis: show every 7th date
tick_pos = list(range(0, len(dates), 7))
ax.set_xticks(tick_pos)
ax.set_xticklabels([dates[i] for i in tick_pos], rotation=45, ha="right", fontsize=8)

plt.tight_layout()
plt.savefig("cti_history.png", dpi=150)
plt.show()
print("Saved: cti_history.png")

# %% [markdown]
# ## Level distribution

# %%
from collections import Counter
dist = Counter(levels)
print("Level distribution:")
for level in ["GREEN", "YELLOW", "ORANGE", "RED"]:
    count = dist.get(level, 0)
    pct = count / len(levels) * 100
    print(f"  {level:8s}: {count:3d} days ({pct:.1f}%)")

# %% [markdown]
# ## Volatility analysis

# %%
changes = [abs(scores[i] - scores[i-1]) for i in range(1, len(scores))]
print(f"Daily change — mean: {sum(changes)/len(changes):.2f}, max: {max(changes):.2f}")

level_changes = sum(1 for i in range(1, len(levels)) if levels[i] != levels[i-1])
print(f"Level changes: {level_changes} in {len(levels)} days")
