#!/usr/bin/env python3
"""
22-23. CTI Baseline Validation
==============================

FINDING: ALL signal sources feeding CTI are volatile (CV > 60%).
Only GPS jamming has stable baselines (CV=13%).

AIS baseline corrupted: 7 of 16 days had collector downtime.
Raw mean=34,893 vs Clean mean=61,536 — completely different baselines.

FIRMS false alarm: Raw z=2.0 triggers, Clean z=1.85 does not.

IMPACT: CTI (currently 31.2 YELLOW) may be inflated.
If baselines exclude collector-downtime days,
CTI could drop to ~20 (GREEN).

RECOMMENDATIONS:
1. Exclude collector-downtime days from baseline (median filter)
2. Use median instead of mean for baseline (resistant to outliers)
3. Flag CTI components computed from volatile sources with LOW confidence
4. Add minimum data days threshold (e.g., 5 of 7 days must have data)
"""
