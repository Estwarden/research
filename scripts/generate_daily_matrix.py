#!/usr/bin/env python3
"""
Generate daily_matrix from signals_50d.csv

Creates a daily matrix of signal counts per source_type.
Output: data/daily_matrix.csv (rows=dates, columns=source_types)
"""

import csv
from collections import defaultdict
from datetime import datetime

DATA_DIR = "../data"

print("Loading signals_50d.csv...")

# Build daily counts: {date: {source_type: count}}
daily_counts = defaultdict(lambda: defaultdict(int))
source_types = set()

with open(f"{DATA_DIR}/signals_50d.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            pub_date = datetime.fromisoformat(row["published_at"].replace("+00", ""))
            date_key = pub_date.date().isoformat()
        except:
            continue
        
        source_type = row["source_type"]
        daily_counts[date_key][source_type] += 1
        source_types.add(source_type)

# Sort dates and source types
dates = sorted(daily_counts.keys())
source_types = sorted(source_types)

print(f"Found {len(dates)} days, {len(source_types)} source types")

# Write matrix
with open(f"{DATA_DIR}/daily_matrix.csv", "w") as f:
    # Header
    f.write("date," + ",".join(source_types) + "\n")
    
    # Rows
    for date in dates:
        counts = [str(daily_counts[date].get(st, 0)) for st in source_types]
        f.write(date + "," + ",".join(counts) + "\n")

print(f"✅ Written: {DATA_DIR}/daily_matrix.csv")
print(f"   Shape: {len(dates)} days × {len(source_types)} sources")
