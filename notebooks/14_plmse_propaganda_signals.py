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
# # 14. PLMSE — Propaganda Signal Detection via Power Law Analysis
#
# **Paper:** "Signals of Propaganda — Detecting and Estimating Political Manipulation
# in Information Cascades" (PLOS ONE, Jan 2025)
#
# **URL:** https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0309688
# **Code:** DOI 10.5281/zenodo.10805274
#
# ## Key Idea
# Political cascades follow different power-law distributions than organic ones.
# Propaganda has higher hashtag/keyword repetition rates. The PLMSE (Power Law MSE)
# metric quantifies the deviation from natural power-law distribution.
#
# **Language-independent. Culture-independent. Pure math.**
#
# ## Application to EstWarden
# We apply PLMSE to our Telegram signal data to detect manipulated information cascades
# without relying on keyword taxonomies or language-specific models.
#
# ## Method
# 1. For each event cluster (narrative), extract word/hashtag frequency distributions
# 2. Fit power-law distribution to the frequency data
# 3. Compute PLMSE: deviation of observed frequencies from fitted power-law line
# 4. Higher PLMSE → more likely propaganda (artificially repeated keywords)

# %% [markdown]
# ## Setup

# %%
import os
import numpy as np
import pandas as pd
from collections import Counter
import re

# Load signals data
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
signals_path = os.path.join(DATA_DIR, 'signals_14d.csv')

if os.path.exists(signals_path):
    df = pd.read_csv(signals_path)
    print(f"Loaded {len(df)} signals")
    print(f"Columns: {list(df.columns)}")
else:
    print(f"Data file not found at {signals_path}")
    print("Run: psql $DATABASE_URL -c \"COPY (SELECT * FROM signals WHERE published_at >= now()-interval '14 days') TO STDOUT CSV HEADER\" > data/signals_14d.csv")

# %% [markdown]
# ## 1. Extract Word Frequencies per Cluster
#
# For each event cluster, we extract word frequencies from signal titles and content.
# This is the input to the PLMSE computation.

# %%
def tokenize(text):
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove short words."""
    if not isinstance(text, str):
        return []
    words = re.findall(r'\b\w{3,}\b', text.lower())
    # Remove common stopwords (language-independent by keeping only content words)
    stopwords = {'the', 'and', 'for', 'that', 'with', 'this', 'from', 'are', 'was',
                 'has', 'have', 'been', 'will', 'not', 'but', 'can', 'all', 'its',
                 'also', 'than', 'more', 'about', 'into', 'which', 'when', 'what',
                 'there', 'their', 'they', 'would', 'could', 'should', 'being',
                 'had', 'were', 'who', 'how', 'our', 'out', 'just', 'over'}
    return [w for w in words if w not in stopwords]


def get_word_frequencies(texts):
    """Get word frequency distribution from a list of texts."""
    counter = Counter()
    for text in texts:
        counter.update(tokenize(text))
    # Sort by frequency (descending)
    freqs = sorted(counter.values(), reverse=True)
    return np.array(freqs)

# %% [markdown]
# ## 2. PLMSE Computation
#
# The PLMSE metric from the paper:
#
# For a frequency distribution sorted descending, fit a power law on log-log scale,
# then compute the mean squared error weighted by position.
#
# Higher PLMSE = more deviation from natural power law = likely manipulation.

# %%
def compute_plmse(frequencies, min_points=5):
    """
    Compute Power Law MSE (PLMSE) for a frequency distribution.
    
    Based on: "Signals of Propaganda" (PLOS ONE, 2025)
    
    Args:
        frequencies: sorted descending array of word/hashtag frequencies
        min_points: minimum number of data points required
    
    Returns:
        plmse: float score (higher = more likely propaganda)
        alpha: power law exponent
        c: intercept
    """
    if len(frequencies) < min_points:
        return None, None, None
    
    # Log-log transformation
    x = np.log(np.arange(1, len(frequencies) + 1))  # log(rank)
    y = np.log(frequencies.astype(float))
    
    # Remove infinities (zero frequencies)
    mask = np.isfinite(y)
    x, y = x[mask], y[mask]
    
    if len(x) < min_points:
        return None, None, None
    
    # Logarithmic binning (as recommended in the paper)
    n_bins = min(20, len(x) // 2)
    if n_bins < 3:
        return None, None, None
    
    bin_edges = np.linspace(x.min(), x.max(), n_bins + 1)
    x_binned, y_binned = [], []
    for i in range(n_bins):
        mask_bin = (x >= bin_edges[i]) & (x < bin_edges[i + 1])
        if mask_bin.sum() > 0:
            x_binned.append(x[mask_bin].mean())
            y_binned.append(y[mask_bin].mean())
    
    x_binned = np.array(x_binned)
    y_binned = np.array(y_binned)
    
    if len(x_binned) < 3:
        return None, None, None
    
    # Least squares fit: y = -alpha * x + log(c)
    A = np.vstack([x_binned, np.ones(len(x_binned))]).T
    result = np.linalg.lstsq(A, y_binned, rcond=None)
    slope, intercept = result[0]
    alpha = -slope  # Power law exponent (positive)
    c = np.exp(intercept)
    
    # Compute PLMSE: weighted deviation from fitted line
    y_fitted = slope * x_binned + intercept
    residuals = y_binned - y_fitted
    
    # Weight by position (upper-left deviations = propaganda signal)
    # Points that are ABOVE the line (higher frequency than expected) matter more
    weights = np.where(residuals > 0, 2.0, 1.0)  # Double weight for above-line points
    plmse = np.sqrt(np.mean(weights * residuals**2))
    
    return plmse, alpha, c

# %% [markdown]
# ## 3. Apply to Signal Clusters
#
# Group signals by event cluster and compute PLMSE for each.

# %%
def analyze_cluster(cluster_texts, cluster_name="unknown"):
    """Analyze a cluster of signal texts for propaganda signals."""
    freqs = get_word_frequencies(cluster_texts)
    if len(freqs) == 0:
        return None
    
    plmse, alpha, c = compute_plmse(freqs)
    if plmse is None:
        return None
    
    return {
        'cluster': cluster_name,
        'n_signals': len(cluster_texts),
        'n_unique_words': len(freqs),
        'plmse': plmse,
        'alpha': alpha,
        'c': c,
        'top_words': Counter(w for t in cluster_texts for w in tokenize(t)).most_common(10)
    }


# Example: synthetic test
print("=== Synthetic Test ===")

# Organic cascade: natural power-law distribution
organic_texts = [
    f"Report on situation in region {i}" for i in range(50)
] + [f"Update on military movements near border" for _ in range(3)]

# Propaganda cascade: artificially repeated keywords
propaganda_texts = [
    "INVASION IMMINENT attack Estonia 1-2 months FINAL STAGE" for _ in range(30)
] + [f"Estonia under threat invasion preparation {i}" for i in range(20)]

organic_result = analyze_cluster(organic_texts, "organic")
propaganda_result = analyze_cluster(propaganda_texts, "propaganda")

if organic_result:
    print(f"Organic:     PLMSE={organic_result['plmse']:.4f}, alpha={organic_result['alpha']:.2f}")
if propaganda_result:
    print(f"Propaganda:  PLMSE={propaganda_result['plmse']:.4f}, alpha={propaganda_result['alpha']:.2f}")

# %% [markdown]
# ## 4. Apply to Real Data
#
# Load actual signal data and compute PLMSE per cluster.

# %%
if 'df' in dir() and df is not None and len(df) > 0:
    # Group by cluster if available
    cluster_col = None
    for col in ['cluster_id', 'event_cluster_id', 'cluster']:
        if col in df.columns:
            cluster_col = col
            break
    
    text_col = None
    for col in ['title', 'content', 'text']:
        if col in df.columns:
            text_col = col
            break
    
    if cluster_col and text_col:
        results = []
        for cluster_id, group in df.groupby(cluster_col):
            texts = group[text_col].dropna().tolist()
            if len(texts) >= 5:
                result = analyze_cluster(texts, str(cluster_id))
                if result:
                    results.append(result)
        
        if results:
            results_df = pd.DataFrame(results)
            results_df = results_df.sort_values('plmse', ascending=False)
            print(f"\n=== Top 10 Clusters by PLMSE (Propaganda Score) ===")
            print(results_df[['cluster', 'n_signals', 'plmse', 'alpha']].head(10).to_string())
        else:
            print("No clusters with enough signals found")
    elif text_col:
        # No cluster column — analyze all signals as one group
        texts = df[text_col].dropna().tolist()
        result = analyze_cluster(texts, "all_signals")
        if result:
            print(f"\nAll signals: PLMSE={result['plmse']:.4f}, alpha={result['alpha']:.2f}")
            print(f"Top words: {result['top_words']}")
    else:
        print("No suitable text column found in data")
else:
    print("No data loaded — run with signals_14d.csv")

# %% [markdown]
# ## 5. Interpretation
#
# - **PLMSE > 0.5**: Strong propaganda signal — artificial keyword repetition
# - **PLMSE 0.3-0.5**: Moderate signal — possibly sensationalist content
# - **PLMSE < 0.3**: Likely organic — natural discussion
# - **Alpha (exponent)**: Political cascades ~0.97, organic ~1.21 (paper finding)
#   - Lower alpha = flatter distribution = more keywords repeated many times
#
# ## Next Steps
# 1. Validate on labeled campaigns (known fabrications vs accurate reporting)
# 2. Integrate into pipeline: compute PLMSE per event_cluster in real-time
# 3. Alert when PLMSE exceeds threshold
# 4. Compare with cross-lingual claim matching (notebook 15)
