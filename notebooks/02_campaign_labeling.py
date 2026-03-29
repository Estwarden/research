#!/usr/bin/env python3
"""
02. Campaign Labeling Pipeline

Creates a template for manual campaign review and labeling.
Output: data/labeled_campaigns.csv for human analysts to fill in.
"""

import csv
import os
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, '..', 'data')

print("=" * 80)
print("Campaign Labeling Pipeline")
print("=" * 80)

# Load all campaigns
print("\nLoading campaigns from all_campaigns.csv...")
campaigns = []

with open(f"{DATA_DIR}/all_campaigns.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        campaigns.append(row)

print(f"Loaded {len(campaigns)} campaigns")

# Display summary
print("\n" + "-" * 80)
print("Campaign Summary")
print("-" * 80)
print(f"{'ID':<6} {'Severity':<10} {'Signals':<8} {'Detected':<20} {'Name':<40}")
print("-" * 80)

for c in campaigns[:20]:  # Show first 20
    detected = c.get("detected_at", "")[:19] if c.get("detected_at") else ""
    name = c.get("name", "")[:38]
    print(f"{c.get('id', ''):<6} {c.get('severity', ''):<10} {c.get('signal_count', ''):<8} "
          f"{detected:<20} {name:<40}")

if len(campaigns) > 20:
    print(f"... and {len(campaigns) - 20} more campaigns")

print("-" * 80)

# Create labeling template
print("\nCreating labeled_campaigns.csv template...")

output_fields = [
    "campaign_id",
    "name",
    "severity",
    "signal_count",
    "detected_at",
    "summary",
    "is_hostile_confirmed",  # TRUE/FALSE/UNKNOWN
    "notes",
    "labeled_by",
    "labeled_at",
]

with open(f"{DATA_DIR}/labeled_campaigns.csv", "w", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=output_fields)
    writer.writeheader()
    
    for c in campaigns:
        # Extract summary (truncated to 200 chars)
        summary = ""
        if "event_fact" in c and c["event_fact"]:
            summary = c["event_fact"][:200]
        elif "state_framing" in c and c["state_framing"]:
            summary = c["state_framing"][:200]
        
        writer.writerow({
            "campaign_id": c.get("id", ""),
            "name": c.get("name", ""),
            "severity": c.get("severity", ""),
            "signal_count": c.get("signal_count", ""),
            "detected_at": c.get("detected_at", ""),
            "summary": summary,
            "is_hostile_confirmed": "UNKNOWN",
            "notes": "",
            "labeled_by": "",
            "labeled_at": "",
        })

print(f"✅ Created: {DATA_DIR}/labeled_campaigns.csv")
print(f"   {len(campaigns)} campaigns pre-filled, all marked as UNKNOWN")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("""
1. Open data/labeled_campaigns.csv in a spreadsheet tool
2. For each campaign, review the summary and signals
3. Set is_hostile_confirmed to:
   - TRUE: Confirmed hostile information operation
   - FALSE: Benign or misclassified
   - UNKNOWN: Requires more investigation
4. Add notes explaining your reasoning
5. Fill in labeled_by (your name/ID) and labeled_at (timestamp)
6. Save the file for use in downstream analysis

This labeled dataset will be used to:
- Validate detection algorithms
- Compute precision/recall metrics
- Train supervised ML models
- Calibrate confidence thresholds
""")
