#!/usr/bin/env python3
"""
28-29. Narrative-Sensor Divergence
===================================

CONCEPT: Compare narrative threat claims vs sensor reality.
Source-agnostic by design — doesn't care WHO makes the claim.

RESULT: Divergence ranges from -71 to +24.
BUT: swings are dominated by AIS collector reliability,
not actual threat changes.

CONCLUSION: The divergence metric is the RIGHT approach
but requires STABLE sensor baselines first.

Dependencies:
1. Fix AIS baseline (experiment 22-23)
2. Fix collector downtime exclusion
3. THEN divergence becomes meaningful

This is the correct PRIMARY signal for CTI v2,
but it can't be implemented until sensor reliability is fixed.
"""
