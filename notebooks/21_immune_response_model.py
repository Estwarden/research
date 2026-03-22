# EXPERIMENTS 14-15: Cognitive Immune Response Model
#
# DETECTION SPEED:
# - State campaigns detected in 5.9h average
# - Only 19% caught before cascade peak
# - Cascade peaks faster than detection
#
# EARLY WARNING (2h):
# - Category velocity 2x higher for coordinated (best early signal)
# - Early prediction: 20% precision, 64% recall
# - Too imprecise for autonomous action
#
# TWO-STAGE IMMUNE RESPONSE:
#
# Stage 1 — INNATE (0-2h):
#   Signal: category velocity > 2x baseline
#   Action: pre-compute context, prepare response
#   Confidence: LOW (20% precision)
#   No public action — internal alert only
#
# Stage 2 — ADAPTIVE (2-6h):
#   Signal: sync burst (≥3 cats in 2h) + cross-lingual
#   Action: inject context into information space
#   Confidence: HIGH (90% precision)
#   Public action — automated context/pre-bunking
#
# Like biological immune system:
#   Innate = fast, imprecise, buys time
#   Adaptive = slow, precise, neutralizes
#
# KEY METRIC: 90% precision at confirmation stage
# means 1 in 10 responses is wrong.
# For democratic society: acceptable error rate.
#
# OPEN PROBLEM: Can we make Stage 1 faster and more precise?
# Needs: more channels monitored, higher frequency scraping,
# real-time embedding comparison.
