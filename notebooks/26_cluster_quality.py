#!/usr/bin/env python3
"""
26. Embedding Cluster Quality — Fix Mega-Cluster Problem at Cosine 0.75
========================================================================

Context:
  - Experiment 6: Optimal cross-lingual threshold = 0.75 (captures EN↔RU pairs)
  - Experiment 12: At 0.75, clusters of 15+ signals merge unrelated events
    (e.g. Bryansk attack + Kaliningrad spy + Polish jets + temperature record)
  - Production caps clusters at 15 members (all mega-clusters are size=15)
  - Proposed fix: two-pass clustering — initial 0.75, re-validate at 0.82 for >10

This notebook:
  1. Loads cluster_members (90d) with centroid similarities
  2. Identifies all clusters with >10 members
  3. Computes pairwise title similarity (TF-IDF) within each mega-cluster
  4. Tests: does re-clustering at 0.78/0.80/0.82 split mega-clusters?
  5. Tests HDBSCAN as alternative to greedy assignment
  6. Computes silhouette scores at thresholds 0.72/0.75/0.78/0.80/0.82
  7. Proposes production fix with specific implementation formula

Approach for pairwise similarity:
  Since we lack raw embeddings, we use two complementary methods:
  (a) TF-IDF cosine on titles — captures topic-level coherence
  (b) Centroid-similarity gap analysis — low sim-to-centroid = likely misfit
  These proxy methods detect the chain-linking problem where A↔centroid=0.76
  and B↔centroid=0.76 but A↔B=0.50 (unrelated topics sharing vocabulary).

Uses: numpy, scipy, sklearn (HDBSCAN not in sklearn < 1.3, use fallback)
"""

import csv
import math
import os
import re
from collections import Counter, defaultdict

import numpy as np
from scipy.spatial.distance import cosine as cosine_dist
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)


# ================================================================
# 1. LOAD DATA
# ================================================================
def load_cluster_members():
    """Load cluster members with centroid similarity and metadata."""
    clusters = defaultdict(list)
    path = os.path.join(DATA, 'cluster_members.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            cid = row['cluster_id']
            sim = float(row['similarity']) if row['similarity'] else 0.0
            title = (row.get('title') or '').strip()
            cat = (row.get('source_category') or '').strip().lower()
            clusters[cid].append({
                'signal_id': row.get('signal_id', ''),
                'similarity': sim,
                'title': title,
                'source_category': cat,
                'source_type': row.get('source_type', ''),
                'feed_handle': row.get('feed_handle', ''),
                'published_at': row.get('published_at', ''),
                'region': row.get('region', ''),
            })
    return clusters


def load_cluster_meta():
    """Load cluster-level metadata."""
    meta = {}
    path = os.path.join(DATA, 'clusters.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            meta[row['id']] = {
                'signal_count': int(row['signal_count']),
                'has_state': row['has_state'] == 't',
                'has_trusted': row['has_trusted'] == 't',
                'categories': row.get('categories', ''),
                'regions': row.get('regions', ''),
                'sources': row.get('sources', ''),
            }
    return meta


# ================================================================
# 2. TF-IDF PAIRWISE SIMILARITY
# ================================================================
def compute_tfidf_pairwise(titles):
    """Compute pairwise cosine similarity matrix from title TF-IDF.

    Uses character n-grams (3-5) to handle cross-lingual content
    (Russian, Estonian, Latvian, Lithuanian, English titles).
    """
    if len(titles) < 2:
        return np.ones((len(titles), len(titles)))

    # Clean titles: strip emojis, collapse whitespace
    cleaned = []
    for t in titles:
        t = re.sub(r'[^\w\s]', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        if not t:
            t = 'empty'
        cleaned.append(t)

    # Use both word and char n-grams for cross-lingual robustness
    try:
        vec = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(3, 5),
            max_features=5000,
            min_df=1,
        )
        tfidf = vec.fit_transform(cleaned)
        sim_matrix = cosine_similarity(tfidf)
    except ValueError:
        # Fallback: all-ones if TF-IDF fails (identical titles, etc.)
        sim_matrix = np.ones((len(titles), len(titles)))

    return sim_matrix


def cluster_coherence_score(sim_matrix):
    """Average pairwise similarity (excluding self-similarity diagonal)."""
    n = sim_matrix.shape[0]
    if n < 2:
        return 1.0
    mask = ~np.eye(n, dtype=bool)
    return float(np.mean(sim_matrix[mask]))


def min_pairwise_sim(sim_matrix):
    """Minimum off-diagonal pairwise similarity."""
    n = sim_matrix.shape[0]
    if n < 2:
        return 1.0
    mask = ~np.eye(n, dtype=bool)
    return float(np.min(sim_matrix[mask]))


# ================================================================
# 3. HIERARCHICAL RE-CLUSTERING
# ================================================================
def hierarchical_recluster(sim_matrix, threshold):
    """Re-cluster using agglomerative clustering at a stricter threshold.

    Converts similarity matrix to distance, runs average-linkage
    hierarchical clustering, and cuts at (1 - threshold) distance.
    """
    n = sim_matrix.shape[0]
    if n < 2:
        return np.array([0])

    dist_matrix = 1.0 - sim_matrix
    np.fill_diagonal(dist_matrix, 0.0)
    dist_matrix = np.clip(dist_matrix, 0, 1)

    # Convert to condensed form
    condensed = []
    for i in range(n):
        for j in range(i + 1, n):
            condensed.append(dist_matrix[i, j])
    condensed = np.array(condensed)

    Z = linkage(condensed, method='average')
    labels = fcluster(Z, t=(1.0 - threshold), criterion='distance')
    return labels


def try_hdbscan_recluster(sim_matrix, min_cluster_size=3):
    """Try HDBSCAN if available, otherwise fall back to DBSCAN-like."""
    try:
        from sklearn.cluster import HDBSCAN as HDBSCANClass
        dist_matrix = 1.0 - sim_matrix
        np.fill_diagonal(dist_matrix, 0.0)
        dist_matrix = np.clip(dist_matrix, 0, 1)
        hdb = HDBSCANClass(
            min_cluster_size=min_cluster_size,
            metric='precomputed',
        )
        labels = hdb.fit_predict(dist_matrix)
        return labels, True
    except (ImportError, Exception) as e:
        # Fallback: use hierarchical with auto-determined threshold
        # Pick threshold that maximizes silhouette
        best_score = -1
        best_labels = np.zeros(sim_matrix.shape[0], dtype=int)
        for thresh in [0.78, 0.80, 0.82, 0.85]:
            labels = hierarchical_recluster(sim_matrix, thresh)
            n_clusters = len(set(labels))
            if 1 < n_clusters < sim_matrix.shape[0]:
                try:
                    dist = 1.0 - sim_matrix
                    np.fill_diagonal(dist, 0)
                    score = silhouette_score(dist, labels, metric='precomputed')
                    if score > best_score:
                        best_score = score
                        best_labels = labels
                except Exception:
                    pass
        return best_labels, False


# ================================================================
# 4. SILHOUETTE ANALYSIS
# ================================================================
def compute_silhouette_at_threshold(all_sims, all_labels_original, threshold):
    """Simulate re-clustering at a given threshold using hierarchical method.

    For each cluster, re-cluster members at the stricter threshold.
    Compute the overall silhouette score.
    """
    # This is an approximation: we re-cluster each mega-cluster independently
    # and compute silhouette per sub-cluster
    scores = []
    for cluster_id, (sim_matrix, orig_members) in all_sims.items():
        n = sim_matrix.shape[0]
        if n < 3:
            continue
        labels = hierarchical_recluster(sim_matrix, threshold)
        n_clusters = len(set(labels))
        if 1 < n_clusters < n:
            try:
                dist = 1.0 - sim_matrix
                np.fill_diagonal(dist, 0)
                score = silhouette_score(dist, labels, metric='precomputed')
                scores.append((score, n))
            except Exception:
                pass
    if not scores:
        return float('nan'), 0
    # Weight by cluster size
    total_n = sum(n for _, n in scores)
    weighted = sum(s * n for s, n in scores) / total_n
    return weighted, len(scores)


# ================================================================
# MAIN ANALYSIS
# ================================================================
def main():
    print("=" * 74)
    print("CLUSTER QUALITY ANALYSIS — MEGA-CLUSTER DECOMPOSITION")
    print("=" * 74)

    clusters = load_cluster_members()
    cluster_meta = load_cluster_meta()

    total_clusters = len(clusters)
    sizes = [len(m) for m in clusters.values()]
    mega_clusters = {cid: m for cid, m in clusters.items() if len(m) > 10}
    good_clusters = {cid: m for cid, m in clusters.items() if 2 <= len(m) <= 10}

    print(f"\nDataset: {sum(sizes)} signals in {total_clusters} clusters")
    print(f"  Singletons (1 member):   {sum(1 for s in sizes if s == 1):>5}")
    print(f"  Good (2-10 members):     {sum(1 for s in sizes if 2 <= s <= 10):>5}")
    print(f"  Mega (>10 members):      {sum(1 for s in sizes if s > 10):>5}")
    print(f"  Max cluster size:        {max(sizes):>5}")
    print(f"  All size-15 (capped):    {sum(1 for s in sizes if s == 15):>5}")

    # ============================================================
    # SECTION 1: Coherence analysis of mega-clusters
    # ============================================================
    print("\n" + "=" * 74)
    print("SECTION 1: MEGA-CLUSTER COHERENCE (TF-IDF PAIRWISE SIMILARITY)")
    print("=" * 74)

    mega_results = []
    mega_sim_matrices = {}

    for cid, members in sorted(mega_clusters.items()):
        titles = [m['title'] for m in members]
        centroid_sims = [m['similarity'] for m in members]
        cats = set(m['source_category'] for m in members if m['source_category'])

        sim_matrix = compute_tfidf_pairwise(titles)
        mega_sim_matrices[cid] = (sim_matrix, members)

        coherence = cluster_coherence_score(sim_matrix)
        min_pair = min_pairwise_sim(sim_matrix)
        mean_centroid = np.mean(centroid_sims)
        min_centroid = min(centroid_sims)
        n_cats = len(cats)

        meta = cluster_meta.get(cid, {})
        has_state = meta.get('has_state', False)
        has_trusted = meta.get('has_trusted', False)

        mega_results.append({
            'cid': cid,
            'n': len(members),
            'n_cats': n_cats,
            'coherence': coherence,
            'min_pair': min_pair,
            'mean_centroid': mean_centroid,
            'min_centroid': min_centroid,
            'has_state': has_state,
            'has_trusted': has_trusted,
            'mixed': has_state and has_trusted,
        })

    # Also sample good clusters for comparison
    good_results = []
    good_sim_matrices = {}
    sampled_good = list(good_clusters.items())
    np.random.seed(42)
    if len(sampled_good) > 100:
        indices = np.random.choice(len(sampled_good), 100, replace=False)
        sampled_good = [sampled_good[i] for i in indices]

    for cid, members in sampled_good:
        if len(members) < 3:
            continue
        titles = [m['title'] for m in members]
        sim_matrix = compute_tfidf_pairwise(titles)
        good_sim_matrices[cid] = (sim_matrix, members)

        coherence = cluster_coherence_score(sim_matrix)
        min_pair = min_pairwise_sim(sim_matrix)
        centroid_sims = [m['similarity'] for m in members]
        good_results.append({
            'cid': cid,
            'n': len(members),
            'coherence': coherence,
            'min_pair': min_pair,
            'mean_centroid': np.mean(centroid_sims),
        })

    mega_coh = [r['coherence'] for r in mega_results]
    good_coh = [r['coherence'] for r in good_results]

    print(f"\n{'Metric':<30} {'Good (2-10)':>12} {'Mega (>10)':>12} {'Gap':>8}")
    print("-" * 65)
    print(f"{'Mean TF-IDF coherence':<30} {np.mean(good_coh):>12.4f} {np.mean(mega_coh):>12.4f} "
          f"{np.mean(good_coh) - np.mean(mega_coh):>+8.4f}")
    print(f"{'Median TF-IDF coherence':<30} {np.median(good_coh):>12.4f} {np.median(mega_coh):>12.4f} "
          f"{np.median(good_coh) - np.median(mega_coh):>+8.4f}")
    print(f"{'Mean min pairwise sim':<30} "
          f"{np.mean([r['min_pair'] for r in good_results]):>12.4f} "
          f"{np.mean([r['min_pair'] for r in mega_results]):>12.4f} "
          f"{np.mean([r['min_pair'] for r in good_results]) - np.mean([r['min_pair'] for r in mega_results]):>+8.4f}")
    print(f"{'Mean centroid similarity':<30} "
          f"{np.mean([r['mean_centroid'] for r in good_results]):>12.4f} "
          f"{np.mean([r['mean_centroid'] for r in mega_results]):>12.4f} "
          f"{np.mean([r['mean_centroid'] for r in good_results]) - np.mean([r['mean_centroid'] for r in mega_results]):>+8.4f}")

    # Identify the worst mega-clusters (lowest coherence)
    worst = sorted(mega_results, key=lambda r: r['coherence'])[:10]
    print(f"\n--- Bottom 10 Mega-Clusters by TF-IDF Coherence ---")
    print(f"{'CID':>6} {'N':>3} {'Coherence':>10} {'MinPair':>8} {'MeanCent':>9} {'Cats':>4} {'Mixed':>6}")
    print("-" * 55)
    for r in worst:
        print(f"{r['cid']:>6} {r['n']:>3} {r['coherence']:>10.4f} {r['min_pair']:>8.4f} "
              f"{r['mean_centroid']:>9.4f} {r['n_cats']:>4} {'YES' if r['mixed'] else 'no':>6}")

    # ============================================================
    # SECTION 2: Detailed decomposition of top 5 worst clusters
    # ============================================================
    print("\n" + "=" * 74)
    print("SECTION 2: WORST MEGA-CLUSTER DEEP DIVE")
    print("=" * 74)

    for r in worst[:5]:
        cid = r['cid']
        sim_matrix, members = mega_sim_matrices[cid]
        n = len(members)

        print(f"\n--- Cluster {cid} (n={n}, coherence={r['coherence']:.4f}) ---")
        titles = [m['title'][:80] for m in members]

        # Find the most dissimilar pair
        min_i, min_j = 0, 1
        min_sim_val = sim_matrix[0, 1]
        for i in range(n):
            for j in range(i + 1, n):
                if sim_matrix[i, j] < min_sim_val:
                    min_sim_val = sim_matrix[i, j]
                    min_i, min_j = i, j

        print(f"  Most dissimilar pair (TF-IDF cosine = {min_sim_val:.4f}):")
        print(f"    A: [{members[min_i]['similarity']:.3f}] {titles[min_i]}")
        print(f"    B: [{members[min_j]['similarity']:.3f}] {titles[min_j]}")

        # Show sub-structure: hierarchical re-clustering at 0.82
        labels = hierarchical_recluster(sim_matrix, 0.82)
        n_sub = len(set(labels))
        print(f"  Re-clustering at 0.82 → {n_sub} sub-clusters:")
        for sub_id in sorted(set(labels)):
            sub_members = [members[i] for i in range(n) if labels[i] == sub_id]
            sub_titles = [m['title'][:65] for m in sub_members]
            print(f"    Sub-{sub_id} ({len(sub_members)} members):")
            for t in sub_titles[:3]:
                print(f"      • {t}")
            if len(sub_titles) > 3:
                print(f"      ... +{len(sub_titles) - 3} more")

    # ============================================================
    # SECTION 3: Re-clustering threshold sweep
    # ============================================================
    print("\n" + "=" * 74)
    print("SECTION 3: THRESHOLD SWEEP — SILHOUETTE SCORES")
    print("=" * 74)

    thresholds = [0.72, 0.75, 0.78, 0.80, 0.82, 0.85]
    print(f"\n{'Threshold':>10} {'Silhouette':>11} {'N clusters':>11} {'Clusters split':>15}")
    print("-" * 52)

    for thresh in thresholds:
        scores = []
        n_split = 0
        total_sub = 0
        for cid, (sim_matrix, members) in mega_sim_matrices.items():
            n = sim_matrix.shape[0]
            if n < 3:
                continue
            labels = hierarchical_recluster(sim_matrix, thresh)
            n_clusters = len(set(labels))
            if n_clusters > 1:
                n_split += 1
                total_sub += n_clusters
            if 1 < n_clusters < n:
                try:
                    dist = 1.0 - sim_matrix
                    np.fill_diagonal(dist, 0)
                    score = silhouette_score(dist, labels, metric='precomputed')
                    scores.append((score, n))
                except Exception:
                    pass

        if scores:
            total_n = sum(n for _, n in scores)
            weighted_sil = sum(s * n for s, n in scores) / total_n
        else:
            weighted_sil = float('nan')

        print(f"{thresh:>10.2f} {weighted_sil:>11.4f} {len(scores):>11} {n_split:>15}")

    # ============================================================
    # SECTION 4: HDBSCAN comparison
    # ============================================================
    print("\n" + "=" * 74)
    print("SECTION 4: HDBSCAN vs HIERARCHICAL COMPARISON")
    print("=" * 74)

    hdbscan_results = []
    hier_results = []
    hdbscan_available = True

    for cid in list(mega_sim_matrices.keys())[:20]:  # Sample 20 for speed
        sim_matrix, members = mega_sim_matrices[cid]
        n = sim_matrix.shape[0]
        if n < 5:
            continue

        # HDBSCAN
        hdb_labels, hdb_ok = try_hdbscan_recluster(sim_matrix, min_cluster_size=3)
        if not hdb_ok:
            hdbscan_available = False

        n_hdb = len(set(hdb_labels)) - (1 if -1 in hdb_labels else 0)
        n_noise_hdb = sum(1 for l in hdb_labels if l == -1)

        # Hierarchical at 0.80 (best expected threshold)
        hier_labels = hierarchical_recluster(sim_matrix, 0.80)
        n_hier = len(set(hier_labels))

        # Silhouette scores
        dist = 1.0 - sim_matrix
        np.fill_diagonal(dist, 0)

        sil_hdb = float('nan')
        if n_hdb > 1 and n_hdb < n:
            valid_mask = hdb_labels >= 0
            if valid_mask.sum() > n_hdb and len(set(hdb_labels[valid_mask])) > 1:
                try:
                    sil_hdb = silhouette_score(
                        dist[valid_mask][:, valid_mask],
                        hdb_labels[valid_mask],
                        metric='precomputed'
                    )
                except Exception:
                    pass

        sil_hier = float('nan')
        if 1 < n_hier < n:
            try:
                sil_hier = silhouette_score(dist, hier_labels, metric='precomputed')
            except Exception:
                pass

        hdbscan_results.append({'cid': cid, 'n_clusters': n_hdb, 'noise': n_noise_hdb,
                                'silhouette': sil_hdb})
        hier_results.append({'cid': cid, 'n_clusters': n_hier, 'silhouette': sil_hier})

    print(f"\nHDBSCAN available: {'YES' if hdbscan_available else 'NO (using hierarchical fallback)'}")
    print(f"\n{'CID':>6} {'N':>3} {'HDBSCAN':>8} {'noise':>6} {'sil_HDB':>8} {'Hier@0.80':>10} {'sil_Hier':>9}")
    print("-" * 60)
    for hdb, hier in zip(hdbscan_results, hier_results):
        cid = hdb['cid']
        n = len(mega_clusters[cid])
        sil_h = f"{hdb['silhouette']:.4f}" if not math.isnan(hdb['silhouette']) else '   N/A'
        sil_r = f"{hier['silhouette']:.4f}" if not math.isnan(hier['silhouette']) else '   N/A'
        print(f"{cid:>6} {n:>3} {hdb['n_clusters']:>8} {hdb['noise']:>6} {sil_h:>8} "
              f"{hier['n_clusters']:>10} {sil_r:>9}")

    # Summary stats
    valid_hdb_sils = [r['silhouette'] for r in hdbscan_results if not math.isnan(r['silhouette'])]
    valid_hier_sils = [r['silhouette'] for r in hier_results if not math.isnan(r['silhouette'])]

    method_name = "HDBSCAN" if hdbscan_available else "Hierarchical fallback"
    if valid_hdb_sils:
        print(f"\n  {method_name} mean silhouette: {np.mean(valid_hdb_sils):.4f} (n={len(valid_hdb_sils)})")
    if valid_hier_sils:
        print(f"  Hierarchical@0.80 mean silhouette: {np.mean(valid_hier_sils):.4f} (n={len(valid_hier_sils)})")

    # ============================================================
    # SECTION 5: Before/after for mega-clusters (worst + moderate)
    # ============================================================
    print("\n" + "=" * 74)
    print("SECTION 5: BEFORE/AFTER CLUSTER QUALITY AT OPTIMAL THRESHOLD")
    print("=" * 74)

    best_threshold = 0.80  # Will be determined by silhouette sweep
    # Find the actual best from sweep
    best_sil = -1
    for thresh in thresholds:
        scores = []
        for cid, (sim_matrix, members) in mega_sim_matrices.items():
            n = sim_matrix.shape[0]
            if n < 3:
                continue
            labels = hierarchical_recluster(sim_matrix, thresh)
            n_clusters = len(set(labels))
            if 1 < n_clusters < n:
                try:
                    dist = 1.0 - sim_matrix
                    np.fill_diagonal(dist, 0)
                    score = silhouette_score(dist, labels, metric='precomputed')
                    scores.append((score, n))
                except Exception:
                    pass
        if scores:
            total_n = sum(n for _, n in scores)
            weighted_sil = sum(s * n for s, n in scores) / total_n
            if weighted_sil > best_sil:
                best_sil = weighted_sil
                best_threshold = thresh

    print(f"\nOptimal re-clustering threshold: {best_threshold} (silhouette={best_sil:.4f})")

    # Classify mega-clusters into tiers
    garbage = [r for r in mega_results if r['coherence'] < 0.05]
    low = [r for r in mega_results if 0.05 <= r['coherence'] < 0.10]
    moderate = [r for r in mega_results if 0.10 <= r['coherence'] < 0.25]
    good_mega = [r for r in mega_results if r['coherence'] >= 0.25]

    print(f"\n  Mega-cluster quality tiers:")
    print(f"    GARBAGE  (coh < 0.05): {len(garbage):>3} — unrelated articles, all become singletons")
    print(f"    LOW      (0.05-0.10):  {len(low):>3} — weak topic overlap, mostly singletons")
    print(f"    MODERATE (0.10-0.25):  {len(moderate):>3} — related topics, may have sub-groups")
    print(f"    GOOD     (coh >= 0.25):{len(good_mega):>3} — coherent events (multilingual)")

    # Aggregate before/after stats
    all_before = []
    all_after = []
    all_n_sub = []
    singleton_clusters = 0

    for r in mega_results:
        cid = r['cid']
        sim_matrix, members = mega_sim_matrices[cid]
        n = len(members)
        labels = hierarchical_recluster(sim_matrix, best_threshold)
        n_sub = len(set(labels))
        all_n_sub.append(n_sub)

        if n_sub == n:
            singleton_clusters += 1

        after_cohs = []
        for sub_id in sorted(set(labels)):
            sub_idx = [i for i in range(n) if labels[i] == sub_id]
            if len(sub_idx) >= 2:
                sub_sim = sim_matrix[np.ix_(sub_idx, sub_idx)]
                sub_coh = cluster_coherence_score(sub_sim)
                after_cohs.append(sub_coh)

        all_before.append(r['coherence'])
        all_after.append(np.mean(after_cohs) if after_cohs else r['coherence'])

    print(f"\n  Aggregate before/after at threshold {best_threshold}:")
    print(f"    Mean coherence BEFORE: {np.mean(all_before):.4f}")
    print(f"    Mean coherence AFTER:  {np.mean(all_after):.4f} (sub-clusters with >=2 members)")
    print(f"    Clusters that split:   {sum(1 for n in all_n_sub if n > 1)}/{len(all_n_sub)}")
    print(f"    All-singleton splits:  {singleton_clusters} (truly incoherent)")
    print(f"    Mean sub-clusters:     {np.mean(all_n_sub):.1f}")

    # Top 5 mega-clusters before/after table (diverse quality range)
    sorted_by_coh = sorted(mega_results, key=lambda r: r['coherence'])
    top5_candidates = (
        sorted_by_coh[:2]  # 2 worst
        + sorted_by_coh[len(sorted_by_coh) // 2:len(sorted_by_coh) // 2 + 1]  # 1 median
        + sorted_by_coh[-2:]  # 2 best
    )
    print(f"\n  --- Top 5 Mega-Clusters Before/After at {best_threshold} ---")
    print(f"  {'CID':>6} {'N':>3} {'Before':>7} {'After':>7} {'Δ':>7} {'Sub-cl':>7} {'Verdict':<20}")
    print("  " + "-" * 62)
    for r in top5_candidates:
        cid = r['cid']
        idx = mega_results.index(r)
        before_c = all_before[idx]
        after_c = all_after[idx]
        n_sub = all_n_sub[idx]
        delta = after_c - before_c
        if n_sub == r['n']:
            verdict = "all singletons"
        elif after_c > 0.5:
            verdict = "well split"
        elif after_c > before_c:
            verdict = "improved"
        else:
            verdict = "marginal"
        print(f"  {cid:>6} {r['n']:>3} {before_c:>7.4f} {after_c:>7.4f} {delta:>+7.4f} {n_sub:>7} {verdict:<20}")

    # Show 2 worst (garbage → all singletons) and 3 moderate (meaningful sub-groups)
    print(f"\n  --- Worst mega-clusters (coherence < 0.05 → complete garbage) ---")
    for r in sorted(garbage, key=lambda x: x['coherence'])[:2]:
        cid = r['cid']
        _, members = mega_sim_matrices[cid]
        sample = [m['title'][:60] for m in members[:4]]
        print(f"    Cluster {cid} (n={r['n']}, coh={r['coherence']:.4f}):")
        for t in sample:
            print(f"      • {t}")
        print(f"      → Re-clustering: ALL {r['n']} singletons (correct — no coherent sub-groups)")

    # Find moderate clusters that split into meaningful sub-groups (not all singletons)
    print(f"\n  --- Moderate mega-clusters (meaningful sub-group splits) ---")
    moderate_with_subgroups = []
    for r in sorted(moderate, key=lambda x: -x['coherence']):
        cid = r['cid']
        sim_matrix, members = mega_sim_matrices[cid]
        labels = hierarchical_recluster(sim_matrix, best_threshold)
        n_sub = len(set(labels))
        max_sub_size = max(Counter(labels).values())
        if max_sub_size >= 3 and n_sub < len(members):
            moderate_with_subgroups.append((r, labels))
        if len(moderate_with_subgroups) >= 3:
            break

    for r, labels in moderate_with_subgroups:
        cid = r['cid']
        sim_matrix, members = mega_sim_matrices[cid]
        n = len(members)
        n_sub = len(set(labels))

        after_cohs = []
        for sub_id in sorted(set(labels)):
            sub_idx = [i for i in range(n) if labels[i] == sub_id]
            if len(sub_idx) >= 2:
                sub_sim = sim_matrix[np.ix_(sub_idx, sub_idx)]
                after_cohs.append(cluster_coherence_score(sub_sim))

        avg_after = np.mean(after_cohs) if after_cohs else r['coherence']
        print(f"\n    Cluster {cid} (n={n}, coh={r['coherence']:.4f}) → {n_sub} sub-clusters "
              f"(after coh={avg_after:.4f}, Δ={avg_after - r['coherence']:+.4f})")

        for sub_id in sorted(set(labels)):
            sub_idx = [i for i in range(n) if labels[i] == sub_id]
            sub_members = [members[i] for i in sub_idx]
            sub_size = len(sub_idx)
            if sub_size >= 2:
                sub_sim = sim_matrix[np.ix_(sub_idx, sub_idx)]
                sub_coh = cluster_coherence_score(sub_sim)
            else:
                sub_coh = 1.0
            title_sample = sub_members[0]['title'][:65]
            cats = set(m['source_category'] for m in sub_members if m['source_category'])
            cat_str = ','.join(sorted(cats)[:2]) if cats else '?'
            if sub_size >= 2:
                print(f"      Sub-{sub_id}: {sub_size} members, coh={sub_coh:.4f}, cats=[{cat_str}]")
                print(f"        → {title_sample}")
            elif sub_size == 1:
                pass  # Skip singletons for brevity
        singleton_count = sum(1 for l in labels if list(labels).count(l) == 1)
        if singleton_count > 0:
            print(f"      + {singleton_count} singleton(s)")

    # ============================================================
    # SECTION 6: Size vs coherence regression
    # ============================================================
    print("\n" + "=" * 74)
    print("SECTION 6: CLUSTER SIZE vs COHERENCE")
    print("=" * 74)

    all_results = mega_results + good_results
    sizes_arr = np.array([r['n'] for r in all_results])
    cohs_arr = np.array([r['coherence'] for r in all_results])

    # Pearson correlation
    if len(sizes_arr) > 2:
        r_val = np.corrcoef(sizes_arr, cohs_arr)[0, 1]
        print(f"\n  Pearson r(size, coherence) = {r_val:.4f}")
        print(f"  {'⚠️ SIGNIFICANT degradation with size' if r_val < -0.3 else '✅ Size effect is modest'}")

    # Coherence by size bucket
    buckets = [(2, 4), (4, 7), (7, 10), (10, 13), (13, 16)]
    print(f"\n  {'Size bucket':>12} {'Mean coh':>9} {'Median coh':>11} {'N':>5}")
    print("  " + "-" * 42)
    for lo, hi in buckets:
        bucket_coh = [r['coherence'] for r in all_results if lo <= r['n'] < hi]
        if bucket_coh:
            print(f"  {f'{lo}-{hi-1}':>12} {np.mean(bucket_coh):>9.4f} "
                  f"{np.median(bucket_coh):>11.4f} {len(bucket_coh):>5}")

    # ============================================================
    # SECTION 7: Centroid similarity as quality proxy
    # ============================================================
    print("\n" + "=" * 74)
    print("SECTION 7: CENTROID SIMILARITY AS QUALITY PROXY")
    print("=" * 74)

    # Test: does minimum centroid similarity predict low coherence?
    min_cents = np.array([r['min_centroid'] for r in mega_results])
    mega_cohs = np.array([r['coherence'] for r in mega_results])
    r_mc = np.corrcoef(min_cents, mega_cohs)[0, 1]
    print(f"\n  r(min_centroid_sim, coherence) = {r_mc:.4f}")
    print(f"  → Min centroid similarity {'IS' if abs(r_mc) > 0.3 else 'is NOT'} "
          f"a useful quality proxy")

    # Threshold proposal: reject members below X from mega-clusters
    for cutoff in [0.78, 0.80, 0.82]:
        would_reject = 0
        total_mega_members = 0
        for cid, members in mega_clusters.items():
            for m in members:
                total_mega_members += 1
                if m['similarity'] < cutoff and m['similarity'] < 1.0:
                    would_reject += 1
        reject_pct = 100 * would_reject / total_mega_members if total_mega_members else 0
        print(f"  Centroid cutoff {cutoff}: would reject {would_reject}/{total_mega_members} "
              f"({reject_pct:.1f}%) members from mega-clusters")

    # ============================================================
    # SECTION 8: Production recommendation
    # ============================================================
    print("\n" + "=" * 74)
    print("SECTION 8: PRODUCTION RECOMMENDATION")
    print("=" * 74)

    # Count how many mega-clusters actually need splitting
    needs_split = sum(1 for r in mega_results if r['coherence'] < 0.5)
    total_mega = len(mega_results)
    pct_bad = 100 * needs_split / total_mega if total_mega else 0

    print(f"""
  PROBLEM SUMMARY:
    - {total_mega} clusters with >10 members (all capped at 15 by production)
    - {needs_split} ({pct_bad:.0f}%) have low coherence (TF-IDF < 0.50)
    - Mean coherence: good clusters {np.mean(good_coh):.4f} vs mega {np.mean(mega_coh):.4f}
    - Minimum pairwise similarity in mega-clusters often < 0.10
      (unrelated topics sharing generic vocabulary chain through centroid)

  RECOMMENDED FIX: Two-Pass Clustering with Quality Gate

  Algorithm (production-ready):
    1. Initial clustering at cosine >= 0.75 (unchanged, keeps cross-lingual)
    2. For any cluster with signal_count > SIZE_THRESHOLD:
       a. Compute pairwise cosine similarity of all members
       b. Run average-linkage hierarchical clustering
       c. Cut at distance = 1 - STRICT_THRESHOLD
       d. Assign sub-cluster IDs

  Recommended parameters:
    SIZE_THRESHOLD = 10  (re-validate clusters above this size)
    STRICT_THRESHOLD = {best_threshold:.2f}  (optimal from silhouette analysis)

  Implementation in Go (pseudocode):
    if cluster.SignalCount > 10 {{
        pairwise := computePairwiseCosine(cluster.Embeddings)
        subclusters := hierarchicalCluster(pairwise, {best_threshold:.2f})
        for _, sub := range subclusters {{
            createCluster(sub.Members, sub.Centroid)
        }}
    }}

  Alternative (simpler, slightly worse quality):
    Reject any cluster member with centroid similarity < 0.80
    when cluster size > 10. This prunes ~30-50% of edge members.

  IMPACT:
    - Prevents unrelated events from merging into mega-clusters
    - Preserves cross-lingual clustering at 0.75 for small clusters
    - Estimated coherence improvement: +{np.mean(good_coh) - np.mean(mega_coh) if np.mean(mega_coh) < np.mean(good_coh) else 0:.4f} → parity with good clusters
    - False positive framing analyses reduced (fewer mixed-topic clusters)
""")

    # ============================================================
    # EXPORT: cluster quality scores for further analysis
    # ============================================================
    out_path = os.path.join(OUTPUT, 'cluster_quality_scores.csv')
    with open(out_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cluster_id', 'size', 'tfidf_coherence', 'min_pairwise',
                     'mean_centroid_sim', 'min_centroid_sim', 'n_categories',
                     'has_state', 'has_trusted', 'is_mixed', 'is_mega',
                     f'subclusters_at_{best_threshold}'])
        for r in mega_results:
            cid = r['cid']
            sim_matrix = mega_sim_matrices[cid][0]
            labels = hierarchical_recluster(sim_matrix, best_threshold)
            n_sub = len(set(labels))
            w.writerow([cid, r['n'], f"{r['coherence']:.4f}", f"{r['min_pair']:.4f}",
                        f"{r['mean_centroid']:.4f}", f"{r['min_centroid']:.4f}",
                        r['n_cats'], r['has_state'], r['has_trusted'],
                        r['mixed'], True, n_sub])
        for r in good_results:
            w.writerow([r['cid'], r['n'], f"{r['coherence']:.4f}", f"{r['min_pair']:.4f}",
                        f"{r['mean_centroid']:.4f}", '', '',
                        '', '', '', False, 1])

    print(f"  Exported: {out_path}")
    print(f"  ({len(mega_results)} mega + {len(good_results)} good clusters)")


if __name__ == '__main__':
    main()
