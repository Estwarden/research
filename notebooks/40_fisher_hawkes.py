#!/usr/bin/env python3
"""
40. Fisher + Hawkes Revalidation
==================================

nb25 showed Fisher discriminant F1=0.92 did NOT replicate at N=30 (F1=0.615).
This notebook adds Hawkes branching ratio as a third feature and tests on
the labeled dataset from R-38.

Method:
1. Load labeled dataset (output/labeled_clusters.csv from nb38)
2. Compute Hawkes branching ratio per cluster (from cluster_members.csv)
3. Fit 3-feature Fisher: state_ratio + fimi_proxy + hawkes_BR
4. LOO cross-validation, bootstrap 95% CI
5. Power analysis: how many more hostile samples needed for p<0.01?

Data: output/labeled_clusters.csv, cluster_members.csv, cluster_framings.csv
"""
import csv
import os
import math
from collections import defaultdict
from datetime import datetime

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

# ================================================================
# 1. LOAD LABELED DATASET
# ================================================================
print("=" * 72)
print("40. FISHER + HAWKES REVALIDATION")
print("=" * 72)

labeled = []
with open(f"{OUTPUT}/labeled_clusters.csv") as f:
    for row in csv.DictReader(f):
        labeled.append(row)

hostile = [r for r in labeled if r['label'] == 'hostile']
clean = [r for r in labeled if r['label'] == 'clean']
print(f"\nLabeled dataset: {len(hostile)} hostile, {len(clean)} clean, {len(labeled) - len(hostile) - len(clean)} unlabeled")

if len(hostile) < 3:
    print("\n⚠  Insufficient hostile labels for meaningful analysis.")
    print("   Run nb38 first, then accumulate more hostile framings.")
    print("   Need at minimum 6 hostile clusters (current nb25 baseline).")

# ================================================================
# 2. COMPUTE HAWKES BRANCHING RATIO
# ================================================================
print("\n" + "=" * 72)
print("2. HAWKES BRANCHING RATIO PER CLUSTER")
print("=" * 72)

# Load cluster member timestamps
cluster_times = defaultdict(list)
with open(f"{DATA}/cluster_members.csv") as f:
    for row in csv.DictReader(f):
        try:
            ts = datetime.fromisoformat(row['published_at'].replace('+00', '+00:00'))
            cluster_times[int(row['cluster_id'])].append(ts.timestamp())
        except (ValueError, KeyError):
            continue

for cid in cluster_times:
    cluster_times[cid].sort()


def hawkes_branching_ratio(timestamps, max_iter=100):
    """
    Estimate Hawkes process branching ratio (alpha/beta) via EM algorithm.
    
    Simplified MLE: fit univariate Hawkes with exponential kernel
    N(t) ~ Poisson(mu + alpha * sum(exp(-beta * (t - t_i))))
    
    Branching ratio = alpha/beta. BR > 0.5 indicates strong self-excitation.
    
    Returns BR or None if insufficient data.
    """
    n = len(timestamps)
    if n < 5:
        return None

    # Normalize to relative times (seconds from first event)
    times = np.array(timestamps) - timestamps[0]
    T = times[-1]
    if T <= 0:
        return None

    # Initial estimates
    mu = n / (2 * T)  # background rate
    alpha = 0.5
    beta = 1.0 / (np.median(np.diff(times)) + 1)

    for _ in range(max_iter):
        # E-step: compute triggering probabilities
        # p_ij = alpha * exp(-beta * (t_j - t_i)) / lambda(t_j)
        # Simplified: just estimate aggregate branching ratio

        # Compute intensities
        intensities = np.zeros(n)
        for j in range(n):
            triggered = 0
            for i in range(j):
                dt = times[j] - times[i]
                if dt > 0:
                    triggered += alpha * math.exp(-beta * dt)
            intensities[j] = mu + triggered

        # M-step
        total_triggered = sum(intensities) - n * mu
        if total_triggered <= 0:
            break

        # Update alpha, beta via moment matching
        gaps = np.diff(times)
        if len(gaps) > 0 and np.mean(gaps) > 0:
            beta_new = 1.0 / np.mean(gaps)
            alpha_new = total_triggered / n
            # Damped update
            alpha = 0.5 * alpha + 0.5 * min(alpha_new, 0.99 * beta_new)
            beta = 0.5 * beta + 0.5 * beta_new

    br = alpha / beta if beta > 0 else 0
    return min(br, 2.0)  # cap at 2 for stability


# Compute BR for labeled clusters
print("\nComputing Hawkes BR for labeled clusters...")
br_values = {}
for row in labeled:
    cid = int(row['cluster_id'])
    if cid in cluster_times:
        br = hawkes_branching_ratio(cluster_times[cid])
        if br is not None:
            br_values[cid] = br

print(f"Computed BR for {len(br_values)} clusters")

hostile_br = [br_values[int(r['cluster_id'])] for r in hostile if int(r['cluster_id']) in br_values]
clean_br = [br_values[int(r['cluster_id'])] for r in clean if int(r['cluster_id']) in br_values]

if hostile_br and clean_br:
    print(f"\nHostile BR: mean={np.mean(hostile_br):.4f}, median={np.median(hostile_br):.4f}, N={len(hostile_br)}")
    print(f"Clean BR:   mean={np.mean(clean_br):.4f}, median={np.median(clean_br):.4f}, N={len(clean_br)}")

    m_h, m_c = np.mean(hostile_br), np.mean(clean_br)
    v_h, v_c = np.var(hostile_br, ddof=1) if len(hostile_br) > 1 else 0, np.var(clean_br, ddof=1) if len(clean_br) > 1 else 0
    se = math.sqrt(v_h/len(hostile_br) + v_c/len(clean_br)) if (v_h/len(hostile_br) + v_c/len(clean_br)) > 0 else 1
    t_stat = (m_h - m_c) / se
    print(f"\n  Welch's t = {t_stat:.4f}")
    print(f"  Direction: hostile BR {'>' if m_h > m_c else '<'} clean BR")
else:
    print("\n  Insufficient BR data for comparison.")

# ================================================================
# 3. THREE-FEATURE FISHER DISCRIMINANT
# ================================================================
print("\n" + "=" * 72)
print("3. FISHER DISCRIMINANT: state_ratio + fimi_proxy + hawkes_BR")
print("=" * 72)

# Build feature matrix for labeled clusters with all three features
X_hostile = []
X_clean = []

for row in labeled:
    cid = int(row['cluster_id'])
    if row['label'] not in ('hostile', 'clean'):
        continue
    if cid not in br_values:
        continue

    state_ratio = float(row['state_ratio'])
    # FIMI proxy: has_state as binary (since we don't have per-cluster FIMI score in the export)
    fimi_proxy = float(row['has_state'])
    br = br_values[cid]

    features = [state_ratio, fimi_proxy, br]
    if row['label'] == 'hostile':
        X_hostile.append(features)
    else:
        X_clean.append(features)

print(f"\nFeature matrix: {len(X_hostile)} hostile, {len(X_clean)} clean (with all 3 features)")

if len(X_hostile) >= 2 and len(X_clean) >= 2:
    X_h = np.array(X_hostile)
    X_c = np.array(X_clean)

    # Fisher LDA: w = S_w^{-1} (mu_h - mu_c)
    mu_h = np.mean(X_h, axis=0)
    mu_c = np.mean(X_c, axis=0)

    # Within-class scatter
    S_w = np.zeros((3, 3))
    for x in X_h:
        d = (x - mu_h).reshape(-1, 1)
        S_w += d @ d.T
    for x in X_c:
        d = (x - mu_c).reshape(-1, 1)
        S_w += d @ d.T

    # Regularize for numerical stability
    S_w += np.eye(3) * 1e-6

    try:
        w = np.linalg.solve(S_w, mu_h - mu_c)
        w = w / np.linalg.norm(w)  # normalize

        print(f"\nFisher weights: state_ratio={w[0]:.3f}, fimi_proxy={w[1]:.3f}, hawkes_BR={w[2]:.3f}")

        # Project all samples
        scores_h = X_h @ w
        scores_c = X_c @ w

        print(f"\nProjected scores:")
        print(f"  Hostile: mean={np.mean(scores_h):.4f}, std={np.std(scores_h):.4f}")
        print(f"  Clean:   mean={np.mean(scores_c):.4f}, std={np.std(scores_c):.4f}")

        # Find optimal threshold (maximize F1)
        all_scores = np.concatenate([scores_h, scores_c])
        all_labels = np.array([1]*len(scores_h) + [0]*len(scores_c))

        best_f1 = 0
        best_threshold = 0
        for threshold in np.linspace(all_scores.min(), all_scores.max(), 100):
            predicted = (all_scores >= threshold).astype(int)
            tp = np.sum((predicted == 1) & (all_labels == 1))
            fp = np.sum((predicted == 1) & (all_labels == 0))
            fn = np.sum((predicted == 0) & (all_labels == 1))
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold

        print(f"\n  Best threshold: {best_threshold:.4f}")
        print(f"  Best F1: {best_f1:.4f}")

        # LOO cross-validation
        print("\n  Leave-One-Out Cross-Validation:")
        X_all = np.vstack([X_h, X_c])
        y_all = np.array([1]*len(X_h) + [0]*len(X_c))
        n_total = len(X_all)

        loo_correct = 0
        loo_tp = loo_fp = loo_fn = loo_tn = 0
        for i in range(n_total):
            X_train = np.delete(X_all, i, axis=0)
            y_train = np.delete(y_all, i)

            # Refit Fisher on leave-one-out
            h_idx = y_train == 1
            c_idx = y_train == 0
            if h_idx.sum() < 1 or c_idx.sum() < 1:
                continue

            mu_h_loo = np.mean(X_train[h_idx], axis=0)
            mu_c_loo = np.mean(X_train[c_idx], axis=0)
            S_w_loo = np.zeros((3, 3))
            for x in X_train[h_idx]:
                d = (x - mu_h_loo).reshape(-1, 1)
                S_w_loo += d @ d.T
            for x in X_train[c_idx]:
                d = (x - mu_c_loo).reshape(-1, 1)
                S_w_loo += d @ d.T
            S_w_loo += np.eye(3) * 1e-6

            w_loo = np.linalg.solve(S_w_loo, mu_h_loo - mu_c_loo)

            # Predict held-out sample using midpoint threshold
            score_i = X_all[i] @ w_loo
            midpoint = 0.5 * (mu_h_loo @ w_loo + mu_c_loo @ w_loo)
            pred = 1 if score_i >= midpoint else 0
            actual = y_all[i]

            if pred == actual:
                loo_correct += 1
            if pred == 1 and actual == 1:
                loo_tp += 1
            elif pred == 1 and actual == 0:
                loo_fp += 1
            elif pred == 0 and actual == 1:
                loo_fn += 1
            else:
                loo_tn += 1

        loo_acc = loo_correct / n_total * 100
        loo_prec = loo_tp / (loo_tp + loo_fp) if (loo_tp + loo_fp) > 0 else 0
        loo_rec = loo_tp / (loo_tp + loo_fn) if (loo_tp + loo_fn) > 0 else 0
        loo_f1 = 2 * loo_prec * loo_rec / (loo_prec + loo_rec) if (loo_prec + loo_rec) > 0 else 0

        print(f"  LOO Accuracy: {loo_acc:.1f}%")
        print(f"  LOO Precision: {loo_prec:.3f}, Recall: {loo_rec:.3f}, F1: {loo_f1:.3f}")
        print(f"  Confusion: TP={loo_tp}, FP={loo_fp}, FN={loo_fn}, TN={loo_tn}")

        # Bootstrap 95% CI for F1
        print("\n  Bootstrap 95% CI (1000 iterations):")
        rng = np.random.RandomState(42)
        boot_f1s = []
        for _ in range(1000):
            idx = rng.choice(n_total, size=n_total, replace=True)
            X_boot = X_all[idx]
            y_boot = y_all[idx]

            h_idx = y_boot == 1
            c_idx = y_boot == 0
            if h_idx.sum() < 1 or c_idx.sum() < 1:
                continue

            mu_hb = np.mean(X_boot[h_idx], axis=0)
            mu_cb = np.mean(X_boot[c_idx], axis=0)
            S_wb = np.zeros((3, 3))
            for x in X_boot[h_idx]:
                d = (x - mu_hb).reshape(-1, 1)
                S_wb += d @ d.T
            for x in X_boot[c_idx]:
                d = (x - mu_cb).reshape(-1, 1)
                S_wb += d @ d.T
            S_wb += np.eye(3) * 1e-6

            try:
                wb = np.linalg.solve(S_wb, mu_hb - mu_cb)
            except np.linalg.LinAlgError:
                continue

            scores = X_boot @ wb
            midpoint = 0.5 * (mu_hb @ wb + mu_cb @ wb)
            preds = (scores >= midpoint).astype(int)

            tp = np.sum((preds == 1) & (y_boot == 1))
            fp = np.sum((preds == 1) & (y_boot == 0))
            fn = np.sum((preds == 0) & (y_boot == 1))
            p = tp / (tp + fp) if (tp + fp) > 0 else 0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
            boot_f1s.append(f1)

        if boot_f1s:
            ci_lo = np.percentile(boot_f1s, 2.5)
            ci_hi = np.percentile(boot_f1s, 97.5)
            print(f"  F1 95% CI: [{ci_lo:.3f}, {ci_hi:.3f}]")
            print(f"  Mean bootstrap F1: {np.mean(boot_f1s):.3f}")

    except np.linalg.LinAlgError:
        print("\n  Singular matrix -- cannot fit Fisher discriminant.")
        print("  This typically means features are linearly dependent.")
else:
    print("\n  Need >= 2 hostile and >= 2 clean clusters with all features.")
    print("  Run nb38 first to build the labeled dataset.")

# ================================================================
# 4. POWER ANALYSIS
# ================================================================
print("\n" + "=" * 72)
print("4. POWER ANALYSIS")
print("=" * 72)

n_hostile = len(X_hostile)
n_clean = len(X_clean)
print(f"\nCurrent: {n_hostile} hostile, {n_clean} clean")

# For Fisher/LDA, rule of thumb: need 10x samples per feature for stability
# With 3 features, need ~30 samples minimum per class
target_per_class = max(33, 10 * 3)
print(f"Target for p<0.01 with 3 features: {target_per_class} per class")
print(f"Gap: {max(0, target_per_class - n_hostile)} more hostile, {max(0, target_per_class - n_clean)} more clean")

if n_hostile > 0:
    hostile_rate_per_week = n_hostile / 7  # rough estimate
    weeks_needed = max(0, (target_per_class - n_hostile) / max(hostile_rate_per_week, 0.1))
    print(f"\nAt current hostile detection rate (~{hostile_rate_per_week:.1f}/week):")
    print(f"  Estimated {weeks_needed:.0f} weeks to reach N={target_per_class}")

# ================================================================
# 5. SAVE RESULTS
# ================================================================
print("\n" + "=" * 72)
print("5. SAVE RESULTS")
print("=" * 72)

with open(f"{OUTPUT}/fisher_hawkes_features.csv", "w") as f:
    f.write("cluster_id,label,state_ratio,fimi_proxy,hawkes_br\n")
    for row in labeled:
        cid = int(row['cluster_id'])
        if row['label'] in ('hostile', 'clean') and cid in br_values:
            f.write(f"{cid},{row['label']},{row['state_ratio']},"
                    f"{row['has_state']},{br_values[cid]:.6f}\n")

print(f"Saved to output/fisher_hawkes_features.csv")

print(f"""
SUMMARY:
  3-feature Fisher discriminant: state_ratio + fimi_proxy + hawkes_BR
  Hostile: {n_hostile}, Clean: {n_clean}
  
  Key question: Does adding Hawkes BR recover the F1=0.92 that failed
  to replicate in nb25 (F1=0.615 at N=30)?

NEXT STEPS:
  1. Accumulate more hostile-labeled clusters (target: {target_per_class})
  2. Add PLMSE (from nb36) as a 4th feature
  3. Test regularized logistic regression as an alternative to Fisher
  4. Deploy as pre-screen once N>={target_per_class} and F1 95% CI lower bound > 0.75
""")
