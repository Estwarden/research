#!/usr/bin/env python3
"""
23-24. CTI Reliability Assessment
==================================

FINDING: Only 10% of CTI (GPS jamming) is computed from reliable inputs.

| Component      | Weight | Reliable? | Issue                          |
|----------------|--------|-----------|--------------------------------|
| Signal z-scores| 72%    | ❌        | Volatile baselines, downtime   |
| Campaigns      | 14%    | 🟡        | 7% organic inflation           |
| Narrative vol  | 8%     | ❌        | Keyword-based, single tag      |
| GPS jamming    | 10%    | ✅        | Stable CV=13%, clear signal    |

Current CTI: 31.2 (YELLOW) — likely inflated.
With corrected baselines + campaign filtering, may be ~20 (GREEN).

FIXES NEEDED:
1. Signal z-scores: exclude downtime days, use median, min 5/7 data days
2. Campaigns: filter by LLM-validated hostile label only
3. Narrative volume: replace keyword matching with embedding-based
4. GPS jamming: keep as-is (reliable)
5. Add confidence intervals to CTI output
"""
