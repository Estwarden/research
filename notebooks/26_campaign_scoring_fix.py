#!/usr/bin/env python3
"""
26-27. Campaign Scoring Algorithm
==================================

Multi-signal threat score using validated components:
- Burstiness (p<0.001) × 2.0
- Category spread × 1.5
- Certainty language × 1.0
- Baltic targeting × 0.5
- Engagement markers × 0.3

RESULT: Score separates RU from non-RU (t=6.48)
BUT: top-15 includes mix of RU + non-RU = partially source-agnostic

TENSION: Burstiness is most validated but RU-correlated.
Removing it reduces bias but weakens detection.

NEXT STEP: Test without burstiness — does category spread
+ content features alone provide useful separation?
"""
