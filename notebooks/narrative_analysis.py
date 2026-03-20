# %% [markdown]
# # Narrative Classification Analysis
# Analyze the distribution and trends of information operation narratives (N1-N5).

# %%
import json
import urllib.request

API = "https://estwarden.eu"

def api(path):
    with urllib.request.urlopen(f"{API}{path}", timeout=15) as r:
        return json.loads(r.read())

CODES = {
    "N1": "Russophobia / Persecution",
    "N2": "War Escalation Panic",
    "N3": "Aid = Theft",
    "N4": "Delegitimization",
    "N5": "Isolation / Victimhood",
}

# %% [markdown]
# ## Current narrative activity (30 days)

# %%
data = api("/api/influence/narratives?days=30")
narratives = data if isinstance(data, list) else data.get("narratives", [])

print("Narrative Activity (last 30 days):\n")
for n in sorted(narratives, key=lambda x: x.get("count", 0), reverse=True):
    code = n.get("code", "?")
    count = n.get("count", 0)
    name = CODES.get(code, "Unknown")
    bar = "█" * min(count // 5, 40)
    print(f"  {code} {name:30s} {count:5d}  {bar}")

# %% [markdown]
# ## Active campaigns

# %%
campaigns = api("/api/influence/campaigns?days=30")
if isinstance(campaigns, dict):
    campaigns = campaigns.get("campaigns", [])

print(f"\nActive Campaigns ({len(campaigns)}):\n")
for c in campaigns:
    print(f"  [{c.get('severity', '?'):8s}] {c.get('name', '?')}")
    if c.get("summary"):
        print(f"           {c['summary'][:120]}")
    print()

# %% [markdown]
# ## Today's report context

# %%
report = api("/api/today")
print(f"Date: {report.get('date', '?')}")
print(f"Level: {report.get('threat_level', report.get('level', '?'))}")
print(f"\n{report.get('summary', 'No summary')}")
