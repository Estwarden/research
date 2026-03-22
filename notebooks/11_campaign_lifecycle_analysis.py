"""
Notebook 11: Campaign Lifecycle Analysis

Research Question:
------------------
How long do disinformation campaigns last? What are the decay curves?
Understanding campaign lifecycle helps:
  - Set appropriate detection windows
  - Predict when follow-up monitoring is no longer needed
  - Identify "slow burn" vs. "burst" campaign patterns

Methodology:
------------
1. Load all campaigns with detection timestamps
2. For each campaign, compute:
   - Duration (first signal → last signal)
   - Peak activity timestamp
   - Decay rate (exponential fit to signal volume over time)
   - Half-life (time for signal volume to drop by 50%)
3. Cluster campaigns by lifecycle pattern (short burst, sustained, recurring)
4. Correlate lifecycle with campaign severity and detection method

Expected Output:
----------------
- Table: campaign_lifecycle_stats.csv (campaign_id, duration_hours, half_life_hours, pattern_cluster)
- Plot: decay curves overlaid by severity level
- Metric: median campaign duration by detection method
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.optimize import curve_fit
from sklearn.cluster import KMeans

# Configuration
DATA_DIR = "../data"
OUTPUT_DIR = "../output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# 1. Load Data
# ============================================================================
print("Loading campaigns and cluster members (signals)...")

campaigns = pd.read_csv(f"{DATA_DIR}/campaigns.csv", parse_dates=["detected_at"])
all_campaigns = pd.read_csv(f"{DATA_DIR}/all_campaigns.csv", parse_dates=["detected_at"])
cluster_members = pd.read_csv(f"{DATA_DIR}/cluster_members.csv", parse_dates=["signal_time", "first_seen", "last_seen"])

print(f"Loaded {len(all_campaigns)} campaigns, {len(cluster_members)} cluster member signals")

# ============================================================================
# 2. Compute Campaign Duration
# ============================================================================
print("\nComputing campaign duration from cluster timestamps...")

# Group signals by cluster_id and compute time span
lifecycle = cluster_members.groupby('cluster_id').agg(
    first_signal=('signal_time', 'min'),
    last_signal=('signal_time', 'max'),
    signal_count=('signal_id', 'count')
).reset_index()

lifecycle['duration_hours'] = (lifecycle['last_signal'] - lifecycle['first_signal']).dt.total_seconds() / 3600
lifecycle['duration_hours'] = lifecycle['duration_hours'].fillna(0)  # single-signal clusters

print(f"\nLifecycle stats:")
print(lifecycle[['duration_hours', 'signal_count']].describe())

# Merge with campaign metadata
# Note: cluster_id may not directly map to campaign.id, need to reconcile via campaign signatures
# For now, assume cluster_id appears in campaign metadata

# TODO: Extract cluster_id from campaign signatures JSON field
# Example: campaigns['cluster_id'] = campaigns['signatures'].apply(lambda x: extract_cluster_id(x))

# ============================================================================
# 3. Model Decay Curves
# ============================================================================
print("\nModeling signal decay for long-running campaigns...")

# Exponential decay model: N(t) = N0 * exp(-λ * t)
def exponential_decay(t, N0, decay_rate):
    return N0 * np.exp(-decay_rate * t)

# Select campaigns with duration > 12 hours for modeling
long_campaigns = lifecycle[lifecycle['duration_hours'] > 12]['cluster_id']

decay_params = []
for cluster_id in long_campaigns[:10]:  # Sample first 10 for speed
    cluster_signals = cluster_members[cluster_members['cluster_id'] == cluster_id].copy()
    cluster_signals['hour'] = (cluster_signals['signal_time'] - cluster_signals['signal_time'].min()).dt.total_seconds() / 3600
    
    # Bin signals into hourly buckets
    hourly_counts = cluster_signals.groupby(cluster_signals['hour'].astype(int)).size()
    
    if len(hourly_counts) < 3:
        continue  # Not enough data points
    
    try:
        t = hourly_counts.index.values
        N = hourly_counts.values
        
        # Fit exponential decay
        params, _ = curve_fit(exponential_decay, t, N, p0=[N.max(), 0.1], maxfev=1000)
        N0, decay_rate = params
        half_life = np.log(2) / decay_rate if decay_rate > 0 else np.inf
        
        decay_params.append({
            'cluster_id': cluster_id,
            'N0': N0,
            'decay_rate': decay_rate,
            'half_life_hours': half_life
        })
        
    except Exception as e:
        print(f"⚠️  Failed to fit cluster {cluster_id}: {e}")

decay_df = pd.DataFrame(decay_params)
print(f"\nFitted {len(decay_df)} decay curves")
if len(decay_df) > 0:
    print(decay_df[['cluster_id', 'decay_rate', 'half_life_hours']].head(10))

# ============================================================================
# 4. Cluster Lifecycle Patterns
# ============================================================================
print("\nClustering campaigns by lifecycle pattern...")

# Feature engineering: duration, signal_count, peak_hour
# TODO: Compute peak_hour (hour with most signals)

# For now, cluster on duration and signal_count
X = lifecycle[['duration_hours', 'signal_count']].fillna(0).values

if len(X) > 10:
    kmeans = KMeans(n_clusters=3, random_state=42)
    lifecycle['pattern_cluster'] = kmeans.fit_predict(X)
    
    print("\nLifecycle pattern clusters:")
    print(lifecycle.groupby('pattern_cluster')[['duration_hours', 'signal_count']].mean())

# ============================================================================
# 5. Visualize Lifecycle Distribution
# ============================================================================
print("\nGenerating visualizations...")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Duration histogram
axes[0].hist(lifecycle['duration_hours'], bins=50, edgecolor='black')
axes[0].set_xlabel('Campaign Duration (hours)')
axes[0].set_ylabel('Frequency')
axes[0].set_title('Campaign Duration Distribution')
axes[0].axvline(lifecycle['duration_hours'].median(), color='red', linestyle='--', label=f'Median: {lifecycle["duration_hours"].median():.1f}h')
axes[0].legend()

# Signal count vs duration scatter
axes[1].scatter(lifecycle['duration_hours'], lifecycle['signal_count'], alpha=0.5)
axes[1].set_xlabel('Duration (hours)')
axes[1].set_ylabel('Signal Count')
axes[1].set_title('Signal Count vs. Campaign Duration')
axes[1].set_xscale('log')
axes[1].set_yscale('log')

plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/11_campaign_lifecycle.png", dpi=150)
print(f"Saved: {OUTPUT_DIR}/11_campaign_lifecycle.png")

# ============================================================================
# 6. Save Results
# ============================================================================
output_file = f"{OUTPUT_DIR}/campaign_lifecycle_stats.csv"
lifecycle.to_csv(output_file, index=False)
print(f"\n✅ Saved: {output_file}")

print("\n⚠️  TODO:")
print("   - Map cluster_id to campaign.id via signatures field")
print("   - Compute peak_hour for each campaign")
print("   - Correlate lifecycle with severity and detection_method")
print("   - Add confidence intervals to decay rate estimates")
