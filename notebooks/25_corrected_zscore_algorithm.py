#!/usr/bin/env python3
"""
25-26. Corrected Z-Score Algorithm
====================================

TESTED 3 methods:
1. Classic z (mean + std): inflated by downtime days
2. Robust z (median + MAD): too sensitive, z=74 on some sources
3. IQR-based z (median + IQR): best balance, z range 0-9

RECOMMENDED: IQR-based with:
- Downtime filter: exclude days < 10% of median
- Minimum 5 clean days required
- IQR floor at 20% of median
- Cap z-scores at ±5
- Flag LOW confidence when < 7 clean days

Results:
- Classic: 1 alert  (likely under-detecting due to inflated variance)
- IQR: 4 alerts (energy, milwatch, telegram_channel, firms)

The IQR method detects MORE anomalies because it isn't fooled by
downtime-inflated variance. Classic z with high variance masks real anomalies.
"""
