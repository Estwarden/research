# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 17. Three-Axis Source Classification — Experiment Results
#
# **Date:** 2026-03-23
# **Data:** EstWarden signals_14d (23K signals), PLMSE reference (16 cascades)
#
# ## Validated Results
#
# ### Experiment 1: PLMSE on reference data
# - Political vs disaster cascade slopes: p < 0.001, Cohen's d = 3.0 (LARGE)
# - Threshold classifier: 87.5% accuracy
# - **CONFIRMED: PLMSE separates political from organic on Twitter data**
#
# ### Experiment 1b: PLMSE per source category (our data)
# - unverified_anonymous: 0.528 (most propaganda-like)
# - unverified_commentator: 0.532
# - ru_proxy: 0.652
# - defense_osint: 0.949 (most organic)
# - ukraine_media: 0.969
# - **CONFIRMED: Correctly ranks source categories without content analysis**
#
# ### Experiment 2: Claim drift on Bild map signals
# - 0/7 fabricating channels present in our data
# - **FAILED: Watchlist gap prevents testing. We don't collect the channels that fabricated.**
#
# ### Experiment 3: Campaign label validation
# - All 30 campaigns labeled UNKNOWN
# - **FAILED: No ground truth labels for supervised learning**
#
# ### Experiment 4: PLMSE per cluster
# - State vs non-state: t = 0.42, NOT significant
# - **FAILED: Doesn't work at individual cluster level (too few signals per cluster)**
#
# ### Experiment 5: Engagement farming markers
# - ru_proxy: 3.87 (highest engagement farming score)
# - unverified_anonymous: 3.67
# - defense_osint: 0.79 (lowest)
# - Correlation with PLMSE: r = -0.44 (negative — high engagement = low diversity)
# - **CONFIRMED: Engagement markers distinguish clickbait from organic**
#
# ### Experiment 6: Three-axis independence test
# - PLMSE × Engagement: r = -0.44 (related)
# - PLMSE × Threat rate: r = +0.29 (INDEPENDENT)
# - Engagement × Threat rate: r = +0.07 (INDEPENDENT)
# - **CONFIRMED: Three axes measure different behavioral dimensions**
#
# ## Three-Axis Classification
#
# | Category | PLMSE | Engage | Threat% | Class |
# |----------|-------|--------|---------|-------|
# | ru_proxy | 0.652 | 2.02 | 5.1% | HERDING |
# | unverified_anonymous | 0.528 | 2.29 | 6.0% | HERDING |
# | unverified_commentator | 0.532 | 1.48 | 7.8% | PSYOP_CANDIDATE |
# | estonian_media | 0.650 | 0.59 | 3.2% | STATE_NARRATIVE |
# | defense_osint | 0.949 | 0.79 | 1.4% | ORGANIC |
# | ru_state | 0.976 | 0.65 | 3.0% | ORGANIC |
# | ukraine_media | 0.969 | 0.51 | 19.6% | ORGANIC |
#
# ## Key Insight: Engagement × Threat Independence
#
# Engagement farming and threat-claiming are ORTHOGONAL (r = 0.07).
# This means we CAN distinguish:
# - Channels claiming threats FOR engagement (herding) — high both
# - Channels claiming threats WITHOUT engagement optimization (psyop) — high threat, low engage
# - Channels covering real threats organically — high threat, organic vocabulary
#
# ## Blockers
# 1. No ground truth labels on campaigns
# 2. Missing fabricator channels from watchlist
# 3. PLMSE works at aggregate but not per-cluster level
# 4. Small-market media (Estonian, Finnish) creates false positives on PLMSE axis
#
# ## Open Question (no existing literature)
# Three modes of content convergence (psyop vs herding vs organic) produce
# identical temporal/content signals. The three-axis approach is a first attempt
# at separation. Needs validation on labeled data.
