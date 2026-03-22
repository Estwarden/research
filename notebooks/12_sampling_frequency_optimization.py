"""
Notebook 12: Sampling Frequency Optimization (Nyquist Analysis)

Research Question:
------------------
Are collectors sampling fast enough for each signal type?
According to Nyquist-Shannon theorem, to avoid aliasing (missing events),
sampling rate must be at least 2× the highest frequency component.

For EstWarden:
  - Fast signals (Twitter/Telegram bursts): high frequency, need high sample rate
  - Slow signals (official press releases): low frequency, can sample less often
  - Trade-off: API costs vs. detection latency

Methodology:
------------
1. Load signals grouped by source_type and feed_handle
2. Compute inter-arrival time distribution for each source
3. Estimate "dominant frequency" (inverse of median inter-arrival time)
4. Calculate Nyquist rate (2× dominant frequency)
5. Compare against current collector intervals
6. Recommend optimal sampling intervals per source type

Expected Output:
----------------
- Table: optimal_sampling_intervals.csv (source_type, median_inter_arrival_sec, nyquist_rate_sec, current_interval_sec, recommendation)
- Plot: inter-arrival time distributions by source type
- Metric: potential cost savings vs. detection latency trade-off
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuration
DATA_DIR = "../data"
OUTPUT_DIR = "../output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# 1. Load Data
# ============================================================================
print("Loading signals data...")

signals = pd.read_csv(f"{DATA_DIR}/signals_50d.csv", parse_dates=["published_at"])
print(f"Loaded {len(signals)} signals")

# Remove rows with missing timestamps
signals = signals.dropna(subset=['published_at'])
print(f"After dropping NaN timestamps: {len(signals)} signals")

# ============================================================================
# 2. Compute Inter-Arrival Times
# ============================================================================
print("\nComputing inter-arrival times by source...")

# Group by source_type (and optionally feed_handle for finer granularity)
signals = signals.sort_values(['source_type', 'published_at'])

def compute_inter_arrival(group):
    """Compute time differences between consecutive signals in a group."""
    group = group.sort_values('published_at')
    group['inter_arrival_sec'] = group['published_at'].diff().dt.total_seconds()
    return group

signals = signals.groupby('source_type', group_keys=False).apply(compute_inter_arrival)

# Remove first signal in each group (no prior signal to diff against)
signals = signals.dropna(subset=['inter_arrival_sec'])

print(f"Computed {len(signals)} inter-arrival intervals")

# ============================================================================
# 3. Compute Dominant Frequency and Nyquist Rate
# ============================================================================
print("\nComputing Nyquist rates by source type...")

nyquist_analysis = signals.groupby('source_type')['inter_arrival_sec'].agg([
    ('count', 'count'),
    ('median_inter_arrival_sec', 'median'),
    ('mean_inter_arrival_sec', 'mean'),
    ('p50', lambda x: x.quantile(0.5)),
    ('p90', lambda x: x.quantile(0.9))
]).reset_index()

# Dominant frequency = 1 / median_inter_arrival_sec (Hz)
nyquist_analysis['dominant_freq_hz'] = 1.0 / nyquist_analysis['median_inter_arrival_sec']

# Nyquist rate = 2 × dominant_freq (minimum sampling rate)
# Expressed as interval: 1 / (2 × freq)
nyquist_analysis['nyquist_interval_sec'] = 1.0 / (2 * nyquist_analysis['dominant_freq_hz'])

# For human-readable recommendations
nyquist_analysis['recommended_interval_min'] = nyquist_analysis['nyquist_interval_sec'] / 60

print("\nNyquist Analysis Results:")
print(nyquist_analysis[['source_type', 'median_inter_arrival_sec', 'nyquist_interval_sec', 'recommended_interval_min']])

# ============================================================================
# 4. Compare Against Current Collector Intervals
# ============================================================================
print("\nComparing against current collector intervals...")

# TODO: Load actual collector config (if available) or hardcode known intervals
# Example current intervals (placeholder):
current_intervals = {
    'rss': 300,           # 5 min
    'gdelt': 3600,        # 1 hour
    'osint_perplexity': 1800,  # 30 min
    # ... add other source_types
}

nyquist_analysis['current_interval_sec'] = nyquist_analysis['source_type'].map(current_intervals)

# Check if current interval meets Nyquist criterion
nyquist_analysis['meets_nyquist'] = nyquist_analysis['current_interval_sec'] <= nyquist_analysis['nyquist_interval_sec']

# Recommendation: if not meeting Nyquist, suggest faster sampling; if over-sampling, suggest slower
def recommend_interval(row):
    if pd.isna(row['current_interval_sec']):
        return f"Sample every {row['recommended_interval_min']:.1f} min (no current config)"
    elif row['current_interval_sec'] > row['nyquist_interval_sec']:
        return f"⚠️  Under-sampling! Increase to every {row['recommended_interval_min']:.1f} min"
    elif row['current_interval_sec'] < (row['nyquist_interval_sec'] / 2):
        return f"✅ Over-sampling (safe but costly). Could reduce to {row['recommended_interval_min']:.1f} min"
    else:
        return "✅ Optimal"

nyquist_analysis['recommendation'] = nyquist_analysis.apply(recommend_interval, axis=1)

print("\nRecommendations:")
print(nyquist_analysis[['source_type', 'current_interval_sec', 'nyquist_interval_sec', 'recommendation']])

# ============================================================================
# 5. Visualize Inter-Arrival Distributions
# ============================================================================
print("\nGenerating visualizations...")

# Plot inter-arrival time distributions (log scale)
top_sources = nyquist_analysis.nlargest(6, 'count')['source_type'].values
plot_data = signals[signals['source_type'].isin(top_sources)]

plt.figure(figsize=(14, 6))
for src in top_sources:
    src_data = plot_data[plot_data['source_type'] == src]['inter_arrival_sec']
    plt.hist(src_data, bins=50, alpha=0.5, label=src, log=True)

plt.xlabel('Inter-Arrival Time (seconds)')
plt.ylabel('Frequency (log scale)')
plt.title('Signal Inter-Arrival Time Distribution by Source Type')
plt.legend()
plt.xscale('log')
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/12_inter_arrival_distributions.png", dpi=150)
print(f"Saved: {OUTPUT_DIR}/12_inter_arrival_distributions.png")

# ============================================================================
# 6. Save Results
# ============================================================================
output_file = f"{OUTPUT_DIR}/optimal_sampling_intervals.csv"
nyquist_analysis.to_csv(output_file, index=False)
print(f"\n✅ Saved: {output_file}")

print("\n⚠️  TODO:")
print("   - Load actual collector config to populate current_interval_sec")
print("   - Add cost model (API calls per month vs. detection latency)")
print("   - Distinguish between burst sources (Telegram) vs. steady sources (RSS)")
print("   - Consider time-of-day patterns (some sources are more active at certain hours)")
