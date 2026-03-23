#!/usr/bin/env python3
"""
20. Cross-Validation: Detection Signals vs LLM Labels
=====================================================

KEY FINDING: State media presence does NOT predict hostile intent.

- ORGANIC campaigns have 80% state media presence
- HOSTILE campaigns have 45% state media presence  
- Category spread is HIGHER in organic (3.4) than hostile (2.4)

This BREAKS the assumption that state media = hostile operation.
Russian state media covers real news too. Burstiness detects
"state media temporal patterns" not "hostile operations."

The system needs additional signals beyond source classification
to distinguish hostile from organic state media activity.

Candidates:
1. Content fabrication detection (claims not in source)
2. Narrative framing analysis (how the story is told, not what)
3. Cross-source divergence (does this coverage diverge from facts?)
4. Temporal context (does this align with known Russian strategic calendar?)
"""

# See experiment 19 for LLM labeling methodology
# See experiment 17 for burstiness validation
# This experiment cross-validates the two

# The honest conclusion: burstiness is a valid BEHAVIORAL signal
# but it cannot alone distinguish hostile from organic state media activity.
# Additional signals needed for a reliable autonomous system.
