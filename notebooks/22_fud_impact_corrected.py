# EXPERIMENT 16b: CORRECTED Fear Measurement
#
# FLAWED measurement (16): 12.6% fear, declining
#   Error: included milwatch/gdelt/defense_rss as "fear content"
#   These are military industry news — "missile contract" ≠ fear
#
# CORRECTED measurement (16b): 8% fear, STABLE
#   Excluded defense sources (1,980 signals, 51% contain military terms — expected)
#   Public-facing signals only: 21,291
#
# KEY FINDING:
#   Baltic-specific fear: ~0% (9 out of 21,291 signals)
#   General fear: 8% (global conflicts — Iran, Ukraine war)
#
# FEAR BY SOURCE (corrected):
#   counter_disinfo: 38.5%  ← irony: anti-disinfo channels spread fear
#   ukraine_media:   32.1%  ← covering actual war
#   rss (misc):      28.6%
#   trusted:         26.3%
#   defense_osint:   19.6%  ← expected (military analysis)
#   russian_indep:   16.9%
#   ru_proxy:        13.7%
#   russian_state:    9.0%  ← lower than most categories
#   estonian_media:   5.8%  ← lowest among news media
#   baltic_media:     4.3%
#
# LESSONS:
# 1. Defense/military reporting is NOT fear content — must be classified separately
# 2. Keyword matching without context produces inflated fear scores
# 3. Russian state media produces LESS fear than Ukrainian and "trusted" media
# 4. Baltic-specific fear is negligible in current data
# 5. The real fear comes from global conflict coverage, not targeted campaigns
