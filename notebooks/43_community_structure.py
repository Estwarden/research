#!/usr/bin/env python3
"""
43. Community Structure Classification
========================================

TIDE-MARK paper (PMC 2026): community structure alone predicts fake vs real
news cascades with AUC 0.83. Fake news has MORE COHESIVE, PERSISTENT
communities (higher modularity, lower conductance).

This notebook extracts structural features from EstWarden event clusters
and tests whether they discriminate hostile from clean framings.

Method:
1. Build propagation graph per cluster (source -> source edges by temporal order)
2. Extract structural features: modularity, conductance, degree distribution,
   density, clustering coefficient
3. Compare hostile vs clean clusters
4. Train logistic regression classifier

Data: cluster_members.csv, output/labeled_clusters.csv (from nb38)
"""
import csv
import os
import math
from collections import defaultdict, Counter
from datetime import datetime

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

# ================================================================
# 1. BUILD PROPAGATION GRAPHS
# ================================================================
print("=" * 72)
print("43. COMMUNITY STRUCTURE CLASSIFICATION")
print("=" * 72)

# Load cluster members with temporal ordering
cluster_signals = defaultdict(list)
with open(f"{DATA}/cluster_members.csv") as f:
    for row in csv.DictReader(f):
        try:
            ts = datetime.fromisoformat(row['published_at'].replace('+00', '+00:00'))
        except (ValueError, KeyError):
            continue
        source = row.get('channel') or row.get('feed_handle') or row.get('source_type', '')
        if not source:
            continue
        cluster_signals[int(row['cluster_id'])].append({
            'ts': ts,
            'source': source,
            'category': row.get('source_category', ''),
            'source_type': row.get('source_type', ''),
        })

# Sort by time within each cluster
for cid in cluster_signals:
    cluster_signals[cid].sort(key=lambda x: x['ts'])

print(f"\nLoaded {len(cluster_signals)} clusters with source attribution")
sizes = [len(v) for v in cluster_signals.values()]
print(f"Cluster sizes: mean={np.mean(sizes):.1f}, median={np.median(sizes):.0f}")

# ================================================================
# 2. EXTRACT STRUCTURAL FEATURES
# ================================================================
print("\n" + "=" * 72)
print("2. STRUCTURAL FEATURE EXTRACTION")
print("=" * 72)

MIN_SIGNALS = 3  # need >= 3 for meaningful structure


def extract_structure(signals):
    """
    Build propagation graph and extract structural features.
    
    Graph: directed, source_i -> source_j if source_j posted after source_i
    on the same topic. Edge weight = 1 / time_delta_hours.
    """
    n = len(signals)
    if n < MIN_SIGNALS:
        return None

    sources = list(set(s['source'] for s in signals))
    n_sources = len(sources)
    if n_sources < 2:
        return None

    source_idx = {s: i for i, s in enumerate(sources)}

    # Build adjacency matrix (directed: earlier -> later)
    adj = np.zeros((n_sources, n_sources))
    for i in range(n):
        for j in range(i + 1, min(i + 5, n)):  # connect to next 4 signals
            src_i = source_idx[signals[i]['source']]
            src_j = source_idx[signals[j]['source']]
            if src_i != src_j:
                dt = (signals[j]['ts'] - signals[i]['ts']).total_seconds() / 3600
                weight = 1.0 / (dt + 0.1)  # inverse time weight
                adj[src_i][src_j] += weight

    # Undirected version for structural metrics
    adj_sym = adj + adj.T

    # --- Density ---
    possible_edges = n_sources * (n_sources - 1)
    actual_edges = np.count_nonzero(adj)
    density = actual_edges / possible_edges if possible_edges > 0 else 0

    # --- Degree distribution ---
    out_degree = np.count_nonzero(adj, axis=1)
    in_degree = np.count_nonzero(adj, axis=0)
    degree = out_degree + in_degree
    degree_cv = np.std(degree) / np.mean(degree) if np.mean(degree) > 0 else 0

    # --- Clustering coefficient (local transitivity) ---
    # For each node: proportion of neighbors that are also connected
    clustering_coeffs = []
    for i in range(n_sources):
        neighbors = set(np.where(adj_sym[i] > 0)[0])
        k = len(neighbors)
        if k < 2:
            clustering_coeffs.append(0)
            continue
        # Count edges between neighbors
        neighbor_edges = 0
        for ni in neighbors:
            for nj in neighbors:
                if ni != nj and adj_sym[ni][nj] > 0:
                    neighbor_edges += 1
        cc = neighbor_edges / (k * (k - 1)) if k > 1 else 0
        clustering_coeffs.append(cc)

    avg_clustering = np.mean(clustering_coeffs)

    # --- Category spread ---
    categories = Counter(s['category'] for s in signals if s['category'])
    n_categories = len(categories)

    # --- Temporal features ---
    span_hours = (signals[-1]['ts'] - signals[0]['ts']).total_seconds() / 3600
    gaps = [(signals[i+1]['ts'] - signals[i]['ts']).total_seconds()
            for i in range(n - 1)]
    gap_cv = np.std(gaps) / np.mean(gaps) if gaps and np.mean(gaps) > 0 else 0

    # --- Source type entropy ---
    type_counts = Counter(s['source_type'] for s in signals)
    total = sum(type_counts.values())
    entropy = -sum((c/total) * math.log2(c/total) for c in type_counts.values() if c > 0)

    return {
        'n_signals': n,
        'n_sources': n_sources,
        'density': round(density, 4),
        'avg_clustering': round(avg_clustering, 4),
        'degree_cv': round(degree_cv, 4),
        'max_out_degree': int(max(out_degree)),
        'n_categories': n_categories,
        'source_type_entropy': round(entropy, 4),
        'span_hours': round(span_hours, 2),
        'gap_cv': round(gap_cv, 4),
    }


# Compute for all clusters with enough signals
features = {}
for cid, signals in cluster_signals.items():
    f = extract_structure(signals)
    if f:
        features[cid] = f

print(f"\nExtracted structural features for {len(features)} clusters (>= {MIN_SIGNALS} signals, >= 2 sources)")

# ================================================================
# 3. LABELED COMPARISON
# ================================================================
print("\n" + "=" * 72)
print("3. HOSTILE vs CLEAN STRUCTURAL COMPARISON")
print("=" * 72)

# Load labels from nb38
labels = {}
if os.path.exists(f"{OUTPUT}/labeled_clusters.csv"):
    with open(f"{OUTPUT}/labeled_clusters.csv") as f:
        for row in csv.DictReader(f):
            if row['label'] in ('hostile', 'clean'):
                labels[int(row['cluster_id'])] = row['label'] == 'hostile'

# Fallback to framing labels
with open(f"{DATA}/cluster_framings.csv") as f:
    for row in csv.DictReader(f):
        cid = int(row['cluster_id'])
        if cid not in labels:
            labels[cid] = row['is_hostile'] == 't'

hostile_feats = {cid: f for cid, f in features.items() if labels.get(cid) is True}
clean_feats = {cid: f for cid, f in features.items() if labels.get(cid) is False}

print(f"\nLabeled clusters with structural features:")
print(f"  Hostile: {len(hostile_feats)}")
print(f"  Clean:   {len(clean_feats)}")

if hostile_feats and clean_feats:
    print(f"\n  {'Feature':>25s} {'Hostile':>10s} {'Clean':>10s} {'Direction':>12s}")
    print("  " + "-" * 60)

    for feat_name in ['density', 'avg_clustering', 'degree_cv', 'n_categories',
                      'source_type_entropy', 'span_hours', 'gap_cv', 'n_sources']:
        h_vals = [f[feat_name] for f in hostile_feats.values()]
        c_vals = [f[feat_name] for f in clean_feats.values()]

        m_h = np.mean(h_vals)
        m_c = np.mean(c_vals)
        direction = "hostile >" if m_h > m_c else "hostile <"

        print(f"  {feat_name:>25s} {m_h:>10.4f} {m_c:>10.4f} {direction:>12s}")

    # Per TIDE-MARK: fake news should have HIGHER density and clustering
    h_density = [f['density'] for f in hostile_feats.values()]
    c_density = [f['density'] for f in clean_feats.values()]

    if len(h_density) >= 2 and len(c_density) >= 2:
        v_h = np.var(h_density, ddof=1)
        v_c = np.var(c_density, ddof=1)
        se = math.sqrt(v_h/len(h_density) + v_c/len(c_density))
        t = (np.mean(h_density) - np.mean(c_density)) / se if se > 0 else 0
        print(f"\n  Density Welch's t = {t:.4f}")
        if np.mean(h_density) > np.mean(c_density):
            print("  => Hostile clusters are DENSER (consistent with TIDE-MARK)")
        else:
            print("  => Hostile clusters are LESS dense (contradicts TIDE-MARK)")
else:
    print("\n  Insufficient labeled data for comparison.")
    print("  Run nb38 to build labeled dataset, then re-run this notebook.")

# ================================================================
# 4. SIMPLE CLASSIFIER
# ================================================================
print("\n" + "=" * 72)
print("4. LOGISTIC REGRESSION CLASSIFIER")
print("=" * 72)

FEAT_NAMES = ['density', 'avg_clustering', 'degree_cv', 'n_categories',
              'source_type_entropy', 'gap_cv']

if len(hostile_feats) >= 3 and len(clean_feats) >= 3:
    # Build feature matrix
    X_h = np.array([[f[fn] for fn in FEAT_NAMES] for f in hostile_feats.values()])
    X_c = np.array([[f[fn] for fn in FEAT_NAMES] for f in clean_feats.values()])
    X = np.vstack([X_h, X_c])
    y = np.array([1]*len(X_h) + [0]*len(X_c))

    # Standardize
    mu = np.mean(X, axis=0)
    std = np.std(X, axis=0)
    std[std == 0] = 1
    X_std = (X - mu) / std

    # Simple logistic regression via gradient descent
    n_features = X_std.shape[1]
    w = np.zeros(n_features)
    b = 0
    lr = 0.1
    n_iter = 1000

    for _ in range(n_iter):
        z = X_std @ w + b
        z = np.clip(z, -500, 500)  # prevent overflow
        p = 1 / (1 + np.exp(-z))
        grad_w = X_std.T @ (p - y) / len(y)
        grad_b = np.mean(p - y)
        w -= lr * grad_w
        b -= lr * grad_b

    # Predict and evaluate
    z = X_std @ w + b
    p = 1 / (1 + np.exp(-np.clip(z, -500, 500)))
    preds = (p >= 0.5).astype(int)

    tp = np.sum((preds == 1) & (y == 1))
    fp = np.sum((preds == 1) & (y == 0))
    fn = np.sum((preds == 0) & (y == 1))
    tn = np.sum((preds == 0) & (y == 0))
    acc = (tp + tn) / len(y) * 100
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

    print(f"\n  Training set results (N={len(y)}):")
    print(f"  Accuracy: {acc:.1f}%, Precision: {prec:.3f}, Recall: {rec:.3f}, F1: {f1:.3f}")
    print(f"  TP={tp}, FP={fp}, FN={fn}, TN={tn}")

    # Feature importance (logistic regression weights)
    print(f"\n  Feature importance (logistic regression weights):")
    for fn, wi in sorted(zip(FEAT_NAMES, w), key=lambda x: -abs(x[1])):
        direction = "=> hostile" if wi > 0 else "=> clean"
        print(f"    {fn:>25s}: {wi:>8.4f} {direction}")

    # LOO cross-validation
    loo_correct = 0
    for i in range(len(X)):
        X_train = np.delete(X_std, i, axis=0)
        y_train = np.delete(y, i)

        w_loo = np.zeros(n_features)
        b_loo = 0
        for _ in range(500):
            z = X_train @ w_loo + b_loo
            z = np.clip(z, -500, 500)
            p = 1 / (1 + np.exp(-z))
            w_loo -= lr * (X_train.T @ (p - y_train) / len(y_train))
            b_loo -= lr * np.mean(p - y_train)

        pred = 1 if (1 / (1 + math.exp(-np.clip(X_std[i] @ w_loo + b_loo, -500, 500)))) >= 0.5 else 0
        if pred == y[i]:
            loo_correct += 1

    loo_acc = loo_correct / len(X) * 100
    print(f"\n  LOO Accuracy: {loo_acc:.1f}%")
else:
    print("\n  Need >= 3 hostile and >= 3 clean clusters for classifier.")
    print("  Current: hostile={}, clean={}".format(len(hostile_feats), len(clean_feats)))

# ================================================================
# 5. SAVE RESULTS
# ================================================================
print("\n" + "=" * 72)
print("5. SAVE RESULTS")
print("=" * 72)

with open(f"{OUTPUT}/community_structure.csv", "w") as f:
    header = "cluster_id,label," + ",".join(FEAT_NAMES) + ",n_signals,n_sources,span_hours\n"
    f.write(header)
    for cid, feat in sorted(features.items()):
        label = 'hostile' if labels.get(cid) is True else ('clean' if labels.get(cid) is False else 'unlabeled')
        values = [str(feat[fn]) for fn in FEAT_NAMES]
        f.write(f"{cid},{label},{','.join(values)},{feat['n_signals']},{feat['n_sources']},{feat['span_hours']}\n")

print(f"Saved {len(features)} cluster structures to output/community_structure.csv")

print(f"""
SUMMARY:
  Extracted 6 structural features from {len(features)} cluster propagation graphs.
  Labeled: {len(hostile_feats)} hostile, {len(clean_feats)} clean.

  Per TIDE-MARK (PMC 2026), hostile cascades should show:
  - Higher graph density (more inter-source connections)
  - Higher clustering coefficient (more triangles)
  - Lower conductance (more cohesive communities)
  
LIMITATIONS:
  - Small labeled dataset (need 100+ events per class for AUC 0.83)
  - Propagation graph approximated from temporal ordering (no direct
    forwarding/repost data available in current export)
  - graph_cv and clustering computed on small graphs (2-15 nodes)
  - No cross-validation on classifier due to small sample

NEXT STEPS:
  1. Accumulate labeled events (R-38 target: 33+ hostile)
  2. Add PLMSE (nb36) and Hawkes BR (nb40) to feature set
  3. Use proper cross-validation when N >= 50 per class
  4. Test Random Forest and SVM as alternatives to logistic regression
  5. Compare structural features vs content features for AUC
""")
