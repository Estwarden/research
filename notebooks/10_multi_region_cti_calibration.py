"""
Notebook 10: Multi-Region CTI Calibration

Research Question:
------------------
Are the current Composite Threat Index (CTI) thresholds optimal for each region?
We now have per-country threat scores (Estonia, Latvia, Lithuania, broader Baltic).
This notebook investigates whether:
  - Different regions exhibit different baseline threat levels
  - Optimal detection thresholds should be region-specific
  - Classification accuracy improves with region-aware calibration

Methodology:
------------
1. Load historical CTI scores segmented by target_regions
2. Analyze distribution differences across regions (mean, variance, percentiles)
3. Compute region-specific ROC curves and optimal thresholds
4. Compare false positive/negative rates for global vs. regional thresholds
5. Recommend calibrated thresholds per region

Expected Output:
----------------
- Table: optimal_thresholds_by_region.csv (region, threshold_low, threshold_medium, threshold_high)
- Plot: ROC curves overlaid by region
- Metric: improvement in precision/recall vs. global threshold baseline
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import roc_curve, auc, precision_recall_curve

# Configuration
DATA_DIR = "../data"
OUTPUT_DIR = "../output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# 1. Load Data
# ============================================================================
print("Loading campaigns and signals data...")

# Load campaigns with target_regions
campaigns = pd.read_csv(f"{DATA_DIR}/campaigns.csv", parse_dates=["detected_at"])
all_campaigns = pd.read_csv(f"{DATA_DIR}/all_campaigns.csv", parse_dates=["detected_at"])

# TODO: Load CTI time series (if exists) or reconstruct from signals + scoring logic
# signals = pd.read_csv(f"{DATA_DIR}/signals_50d.csv", parse_dates=["published_at"])

print(f"Loaded {len(campaigns)} active campaigns, {len(all_campaigns)} total campaigns")

# ============================================================================
# 2. Extract Region-Specific CTI Scores
# ============================================================================
print("\nExtracting CTI scores by region...")

# Parse target_regions (PostgreSQL array string format: {estonia,latvia,lithuania})
def parse_pg_array(s):
    if pd.isna(s):
        return []
    return s.strip('{}').split(',')

all_campaigns['regions'] = all_campaigns['target_regions'].apply(parse_pg_array)

# Explode regions so each campaign-region pair is a row
campaign_regions = all_campaigns.explode('regions')
campaign_regions = campaign_regions[campaign_regions['regions'] != '']

print(f"Total campaign-region pairs: {len(campaign_regions)}")
print(f"Regions: {campaign_regions['regions'].unique()}")

# TODO: Group by region and compute CTI distribution
# For now, use confidence as proxy for CTI score
region_stats = campaign_regions.groupby('regions')['confidence'].describe()
print("\nConfidence (proxy CTI) distribution by region:")
print(region_stats)

# ============================================================================
# 3. Compute Region-Specific Optimal Thresholds
# ============================================================================
print("\nComputing optimal thresholds per region...")

# TODO: Need ground truth labels (is_hostile, manual_review) to compute ROC
# Placeholder logic:
for region in campaign_regions['regions'].unique():
    region_data = campaign_regions[campaign_regions['regions'] == region]
    
    # TODO: If ground truth exists, compute ROC and find optimal threshold
    # Example:
    # fpr, tpr, thresholds = roc_curve(region_data['is_hostile'], region_data['confidence'])
    # optimal_idx = np.argmax(tpr - fpr)
    # optimal_threshold = thresholds[optimal_idx]
    
    print(f"\nRegion: {region}")
    print(f"  Sample size: {len(region_data)}")
    print(f"  Mean confidence: {region_data['confidence'].mean():.3f}")
    print(f"  Std confidence: {region_data['confidence'].std():.3f}")
    
# ============================================================================
# 4. Visualize Region Distributions
# ============================================================================
print("\nGenerating visualizations...")

plt.figure(figsize=(12, 6))
sns.boxplot(data=campaign_regions, x='regions', y='confidence')
plt.title('CTI Confidence Distribution by Region')
plt.xlabel('Region')
plt.ylabel('Confidence Score')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/10_cti_by_region_boxplot.png", dpi=150)
print(f"Saved: {OUTPUT_DIR}/10_cti_by_region_boxplot.png")

# ============================================================================
# 5. Save Recommended Thresholds
# ============================================================================
# TODO: Once optimal thresholds are computed, save to CSV
# Example structure:
# region,threshold_low,threshold_medium,threshold_high,precision,recall,f1
# estonia,0.65,0.75,0.85,0.82,0.78,0.80

print("\n✅ Analysis complete. Review output/ directory for results.")
print("\n⚠️  TODO:")
print("   - Integrate ground truth labels for ROC analysis")
print("   - Load actual CTI time series (not just campaign confidence)")
print("   - Implement cross-validation for threshold stability")
