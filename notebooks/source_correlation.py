# %% [markdown]
# # Source Correlation Analysis
# Examine how different signal sources correlate with each other and with the CTI score.
# This helps validate and optimize the CTI source weights.

# %%
import json
import urllib.request
from datetime import datetime

API = "https://estwarden.eu"

def api(path):
    with urllib.request.urlopen(f"{API}{path}", timeout=15) as r:
        return json.loads(r.read())

# %% [markdown]
# ## Load threat history and analyze score components

# %%
history = api("/api/history?days=60")
if isinstance(history, dict):
    history = history.get("history", [])

print(f"Loaded {len(history)} days")

# Current weights (from CTI methodology)
WEIGHTS = {
    "gpsjam": 20, "adsb": 15, "acled": 15, "firms": 15,
    "ais": 10, "telegram": 10, "rss": 5, "gdelt": 5, "ioda": 5,
}

print("\nCurrent CTI Weights:")
for source, weight in sorted(WEIGHTS.items(), key=lambda x: -x[1]):
    print(f"  {source:12s} {weight:2d}%")

# %% [markdown]
# ## Score distribution analysis

# %%
scores = [h.get("score", 0) for h in history]

if scores:
    import statistics
    print(f"Mean:   {statistics.mean(scores):.1f}")
    print(f"Median: {statistics.median(scores):.1f}")
    print(f"StdDev: {statistics.stdev(scores):.1f}")
    print(f"Min:    {min(scores):.1f}")
    print(f"Max:    {max(scores):.1f}")
    
    # Check if scores cluster near certain thresholds
    buckets = {"GREEN (0-24)": 0, "YELLOW (25-49)": 0, "ORANGE (50-74)": 0, "RED (75-100)": 0}
    for s in scores:
        if s < 25: buckets["GREEN (0-24)"] += 1
        elif s < 50: buckets["YELLOW (25-49)"] += 1
        elif s < 75: buckets["ORANGE (50-74)"] += 1
        else: buckets["RED (75-100)"] += 1
    
    print("\nScore distribution:")
    for bucket, count in buckets.items():
        pct = count / len(scores) * 100
        print(f"  {bucket}: {count} days ({pct:.0f}%)")
