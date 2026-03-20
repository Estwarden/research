#!/usr/bin/env python3
"""Download fresh dataset from EstWarden public API."""
import json, urllib.request, os

API = "https://estwarden.eu"
UA = {"User-Agent": "EstWarden-Research/1.0"}
DIR = os.path.dirname(os.path.abspath(__file__))

def fetch(path):
    req = urllib.request.Request(f"{API}{path}", headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

print("Downloading from EstWarden API...")

data = fetch("/api/threat-index/history")
with open(f"{DIR}/daily_reports.jsonl", "w") as f:
    for d in (data if isinstance(data, list) else data.get("history", [])):
        f.write(json.dumps(d) + "\n")
print(f"  daily_reports: {len(data)} entries")

print("Done. For full signal dump, use the admin export or pg_dump.")
