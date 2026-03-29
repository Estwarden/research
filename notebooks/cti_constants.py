"""
Canonical CTI (Composite Threat Index) constants from production.

Source: compute_threat_index.py in the main EstWarden repo.
Import this instead of copy-pasting weights into each notebook.
"""

SIGNAL_WEIGHTS = {
    "gpsjam": 12, "adsb": 10, "acled": 8, "firms": 8,
    "ais": 6, "telegram": 6, "rss": 4, "gdelt": 4,
    "energy": 6, "business": 4, "ioda": 4,
}

CAMPAIGN_WEIGHT = 10
FABRICATION_WEIGHT = 8
LAUNDERING_WEIGHT = 6
NARRATIVE_WEIGHT = 4
GPSJAM_SEV_WEIGHT = 10

TOTAL_WEIGHT = (
    sum(SIGNAL_WEIGHTS.values())
    + CAMPAIGN_WEIGHT + FABRICATION_WEIGHT
    + LAUNDERING_WEIGHT + NARRATIVE_WEIGHT
    + GPSJAM_SEV_WEIGHT
)  # = 110

YELLOW_THRESHOLD = 15.2

SEV_SCORES = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 8, "LOW": 3}
