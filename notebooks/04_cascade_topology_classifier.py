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
# # 16. Cascade Topology Classifier — Fake vs Real from Structure Alone
#
# **Paper:** "TIDE-MARK: Tracking Dynamic Communities in Fake News Cascades"
# (PMC, Jan 2026)
#
# **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12876841/
#
# ## Key Finding
# Fake news spreads through MORE COHESIVE, PERSISTENT communities (higher modularity,
# lower conductance). Real news is diffuse and decentralized.
#
# **Structure alone predicts fake vs real with AUC 0.83. No content analysis needed.**
#
# ## Application to EstWarden
# Extract structural features from our event clusters (channel-to-channel forwarding,
# timing patterns, category spread) and classify cascades as organic vs manipulated.
#
# ## Method
# 1. Build propagation graph for each event cluster
# 2. Extract structural features: modularity, conductance, degree distribution
# 3. Train simple classifier (logistic regression) on labeled campaigns
# 4. Apply to new clusters for early warning

# %% [markdown]
# ## Setup

# %%
import os
import numpy as np
import pandas as pd
from collections import defaultdict, Counter

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# %% [markdown]
# ## 1. Build Propagation Graph
#
# From signals in a cluster, construct a directed graph:
# - Nodes = channels/sources
# - Edges = temporal ordering (channel A posts before channel B on same topic)
# - Edge weight = time difference (closer in time = stronger connection)

# %%
def build_propagation_graph(signals_df, channel_col='channel', time_col='published_at'):
    """
    Build a propagation graph from signals in a cluster.
    
    Returns:
        nodes: list of channel names
        edges: list of (source, target, time_diff_hours)
        adjacency: dict of {node: [neighbors]}
    """
    if channel_col not in signals_df.columns:
        # Try metadata extraction
        if 'metadata' in signals_df.columns:
            signals_df = signals_df.copy()
            signals_df[channel_col] = signals_df['metadata'].apply(
                lambda x: x.get('channel', 'unknown') if isinstance(x, dict) else 'unknown'
            )
        else:
            return [], [], {}
    
    sorted_df = signals_df.sort_values(time_col)
    nodes = sorted_df[channel_col].unique().tolist()
    
    edges = []
    adjacency = defaultdict(list)
    
    # Create edges between temporally adjacent signals
    for i in range(len(sorted_df)):
        for j in range(i + 1, min(i + 5, len(sorted_df))):  # Look ahead 5 signals
            src = sorted_df.iloc[i][channel_col]
            tgt = sorted_df.iloc[j][channel_col]
            
            if src == tgt:
                continue
            
            t1 = pd.to_datetime(sorted_df.iloc[i][time_col])
            t2 = pd.to_datetime(sorted_df.iloc[j][time_col])
            diff_hours = (t2 - t1).total_seconds() / 3600
            
            if diff_hours <= 48:  # Within 48 hours
                edges.append((src, tgt, diff_hours))
                adjacency[src].append(tgt)
                adjacency[tgt].append(src)
    
    return nodes, edges, adjacency


# %% [markdown]
# ## 2. Extract Structural Features
#
# From the paper, the key discriminating features are:
# - **Modularity (Q)**: How well the graph partitions into communities
# - **Conductance**: Ratio of external to internal edges in communities
# - **Degree distribution**: Concentration of connections
# - **Temporal ARI**: How persistent communities are over time
#
# We compute simplified versions without requiring full GNN infrastructure.

# %%
def compute_structural_features(nodes, edges, adjacency):
    """
    Compute structural features for a propagation cascade.
    
    Returns dict of features useful for fake/real classification.
    """
    n_nodes = len(nodes)
    n_edges = len(edges)
    
    if n_nodes < 2 or n_edges < 1:
        return None
    
    # Degree distribution
    degrees = {node: len(adjacency.get(node, [])) for node in nodes}
    degree_values = list(degrees.values())
    
    # Degree statistics
    mean_degree = np.mean(degree_values)
    std_degree = np.std(degree_values) if len(degree_values) > 1 else 0
    max_degree = max(degree_values)
    
    # Degree concentration (Gini-like): higher = more concentrated = more hub-like
    sorted_degrees = sorted(degree_values)
    n = len(sorted_degrees)
    if n > 1 and sum(sorted_degrees) > 0:
        gini = sum((2 * i - n + 1) * d for i, d in enumerate(sorted_degrees)) / (n * sum(sorted_degrees))
    else:
        gini = 0
    
    # Density: actual edges / possible edges
    density = 2 * n_edges / (n_nodes * (n_nodes - 1)) if n_nodes > 1 else 0
    
    # Temporal features from edges
    time_diffs = [e[2] for e in edges]
    mean_time_diff = np.mean(time_diffs)
    std_time_diff = np.std(time_diffs) if len(time_diffs) > 1 else 0
    
    # Speed of first hop: how fast did the first amplification happen?
    first_hop_hours = min(time_diffs) if time_diffs else 0
    
    # Category spread (if available): how many different source types?
    # (This would need category data — placeholder)
    
    # Clustering coefficient (simplified: fraction of closed triangles)
    n_triangles = 0
    n_possible_triangles = 0
    for node in nodes:
        neighbors = set(adjacency.get(node, []))
        for n1 in neighbors:
            for n2 in neighbors:
                if n1 < n2:
                    n_possible_triangles += 1
                    if n2 in set(adjacency.get(n1, [])):
                        n_triangles += 1
    
    clustering_coeff = n_triangles / n_possible_triangles if n_possible_triangles > 0 else 0
    
    return {
        'n_nodes': n_nodes,
        'n_edges': n_edges,
        'density': density,
        'mean_degree': mean_degree,
        'std_degree': std_degree,
        'max_degree': max_degree,
        'degree_gini': gini,
        'clustering_coefficient': clustering_coeff,
        'mean_time_diff_hours': mean_time_diff,
        'std_time_diff_hours': std_time_diff,
        'first_hop_hours': first_hop_hours,
    }

# %% [markdown]
# ## 3. Synthetic Test — Bild Map vs Organic
#
# Create synthetic cascades to validate the features.

# %%
# Bild map cascade (coordinated, fast, hub-like)
bild_signals = pd.DataFrame({
    'channel': ['insiderUKR', 'uniannet', 'Tsaplienko', 'smolii_ukraine',
                'TSN_ua', 'channel5UA', 'pravda_gerashchenko',
                'Tsaplienko', 'BerezaJuice', 'smolii_ukraine'],
    'published_at': [
        '2026-03-16 08:57', '2026-03-16 09:20', '2026-03-16 09:36',
        '2026-03-16 09:40', '2026-03-16 16:14', '2026-03-16 20:51',
        '2026-03-17 00:00', '2026-03-21 14:06', '2026-03-21 14:30',
        '2026-03-21 15:18',
    ]
})

# Organic cascade (gradual, dispersed, no hub)
organic_signals = pd.DataFrame({
    'channel': [f'channel_{i}' for i in range(10)],
    'published_at': pd.date_range('2026-03-16', periods=10, freq='12h'),
})

print("=== Bild Map Cascade (manipulated) ===")
nodes, edges, adj = build_propagation_graph(bild_signals)
features = compute_structural_features(nodes, edges, adj)
if features:
    for k, v in features.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

print("\n=== Organic Cascade ===")
nodes, edges, adj = build_propagation_graph(organic_signals)
features = compute_structural_features(nodes, edges, adj)
if features:
    for k, v in features.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

# %% [markdown]
# ## 4. Expected Discriminators (from paper)
#
# | Feature | Fake News | Real News |
# |---------|-----------|-----------|
# | Modularity | Higher (0.60-0.63) | Lower (0.53-0.56) |
# | Conductance | Lower (0.30-0.33) | Higher (0.36-0.39) |
# | Temporal ARI | Higher (0.71) | Lower (0.66) |
# | Density | Higher | Lower |
# | Degree Gini | Higher (hub-like) | Lower (distributed) |
# | Clustering | Higher | Lower |
#
# Paper achieves AUC 0.83 with logistic regression on these features alone.
#
# ## 5. Next Steps
#
# 1. Export real cluster data with channel metadata
# 2. Label known campaigns as fake/real
# 3. Train logistic regression classifier
# 4. Integrate into pipeline: compute features per new cluster, score, alert
# 5. Combine with PLMSE (notebook 14) and claim drift (notebook 15)
