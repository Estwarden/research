# EXPERIMENT 13: Compound Behavioral Pattern Detector
#
# Pattern A: Synchronized burst (≥3 categories in 2h window)
#   → 85% precision, 16% recall
#
# Pattern B: Cross-lingual amplification (Cyrillic + Latin, ≥3 categories)
#   → 50% precision, 13% recall
#
# Compound (A+B): 90% precision, 13% recall
#
# KEY: High precision is critical for autonomous systems.
# 90% precision means 1 in 10 flags is wrong.
# This is actionable without human review.
#
# Trade-off: Low recall means we miss subtle coordination.
# Solution: multiple detection layers with different sensitivity.
