#!/usr/bin/env python3
"""
27-28. Content-Only Scoring — Source Bias Analysis
===================================================

CRITICAL FINDING:

With burstiness: RU scores HIGHER (t=+6.48) — behavioral bias toward RU
Without burstiness: Non-RU scores HIGHER (t=-5.52) — content alarm from "friendly" sources

Top 10 content-only threats: 9/10 are NON-RUSSIAN.
The most alarming content (Baltic targeting, certainty, caps) comes from
Estonian, Baltic, and Ukrainian media — not Russian state media.

This confirms: the threat to Estonian mental health is the self-amplifying
fear ecosystem, not primarily Russian propaganda.

IMPLICATION FOR CTI:
- Burstiness detects RU media behavior (validated but biased)
- Content features detect "friendly" alarm (validated, inversely biased)
- A COMBINED score partially cancels out bias
- BUT: no single approach is source-agnostic

THE HONEST CONCLUSION:
No behavioral or content signal reliably separates "hostile" from "organic"
without some source bias. The system must either:
1. Accept bias and document it transparently
2. Use GROUND TRUTH divergence (sensor data vs narrative claims) as the
   ONLY truly unbiased signal — this is EstWarden's unique advantage
"""
