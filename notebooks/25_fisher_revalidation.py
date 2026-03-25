#!/usr/bin/env python3
"""
25. Fisher Pre-Screen Revalidation on Expanded Dataset
=======================================================

Context:
  - Experiment 25 (FINDINGS.campaign-detection.md): Fisher discriminant
    (state_ratio + fimi_score) achieves F1=0.92 at N=13 (6 hostile, 7 clean)
  - Experiment 23: power analysis needs N=14 minimum (we had 13)
  - R-012 (nb24): Hawkes branching ratio (BR) distinguishes state vs clean
    clusters (p=0.04, d=0.25)
  - Production DB now has 30 framing analyses (6 hostile, 24 clean)

This notebook:
  1. Loads ALL 30 framing analyses from fresh export
  2. Computes per-cluster features: state_ratio, fimi_score, signal_count
  3. Fits Hawkes per cluster for branching ratio (BR)
  4. Recomputes Fisher discriminant with expanded dataset
  5. Runs full LOO cross-validation
  6. Computes confidence intervals on F1 using bootstrap (1000 resamples)
  7. Tests: does adding Hawkes BR improve the discriminant?
  8. Power analysis for p<0.01 significance

Uses: standard library + numpy + scipy.optimize
"""

import csv
import math
import os
import re
from collections import defaultdict
from datetime import datetime

import numpy as np
from scipy.optimize import minimize

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# ================================================================
# CATEGORY MAPPING (same as nb24)
# ================================================================
STATE_CATS = {'russian_state', 'ru_state', 'pro_kremlin'}
PROXY_CATS = {'ru_proxy', 'russian_language_ee'}
TRUSTED_CATS = {'estonian_media', 'baltic_media', 'government',
                'counter_disinfo', 't1', 't2', 'polish_media',
                'finnish_media', 'lithuanian_media', 'latvian_media',
                'trusted'}
TELEGRAM_CATS = {'telegram', 'social_media', 'defense_osint'}

# FIMI technique keywords (from Experiment 20)
FIMI_HEDGING = [
    'allegedly', 'as claimed', 'якобы', 'так называемый', 'утверждается',
    'как утверждается', 'so-called', 'claimed', 'purported', 'supposed',
    'as asserted', 'what they call',
]
FIMI_OMISSION = [
    'omission', 'omits', 'omitted', 'systematically excludes', 'fails to mention',
    'without mentioning', 'conspicuously absent', 'no mention of',
    'does not acknowledge', 'ignores', 'deliberately excludes',
]
FIMI_AMPLIFICATION = [
    'amplif', 'coordinated', 'synchronized', 'echo', 'multi-outlet',
    'multiple outlets', 'across outlets', 'state media push',
    'campaign', 'manufactured', 'orchestrated',
]
FIMI_FABRICATION = [
    'fabricat', 'invented', 'false claim', 'false quote', 'misattribut',
    'quote that', 'non-existent', 'made up', 'manufactured quote',
]


def is_state_category(cat):
    """Check if category is Russian state media."""
    return cat.strip().lower() in STATE_CATS


def parse_timestamp(s):
    """Parse timestamp to hours since epoch (for Hawkes fitting)."""
    if not s or len(s) < 16:
        return None
    try:
        s = s.strip()
        if '+' in s[10:]:
            s = s.split('+')[0].strip()
        if '.' in s:
            s = s.split('.')[0]
        dt = datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
        epoch = datetime(2026, 1, 1)
        return (dt - epoch).total_seconds() / 3600.0
    except (ValueError, TypeError):
        return None


# ================================================================
# HAWKES PROCESS (from nb24)
# ================================================================

def hawkes_loglik(params, times, T):
    """Negative log-likelihood for univariate Hawkes process."""
    log_mu, log_alpha, log_beta = params
    mu = np.exp(log_mu)
    alpha = np.exp(log_alpha)
    beta = np.exp(log_beta)

    n = len(times)
    if n < 2:
        return 1e10

    A = np.zeros(n)
    for i in range(1, n):
        dt = times[i] - times[i - 1]
        A[i] = np.exp(-beta * dt) * (1.0 + A[i - 1])

    intensities = mu + alpha * A
    intensities = np.maximum(intensities, 1e-20)
    log_intensities = np.log(intensities)

    integral = mu * T
    if beta > 0:
        integral += (alpha / beta) * np.sum(1.0 - np.exp(-beta * (T - times)))

    return -np.sum(log_intensities) + integral


def fit_hawkes(times, max_retries=3):
    """Fit Hawkes process via MLE. Returns dict with μ, α, β, branching_ratio."""
    if len(times) < 3:
        return None

    times = np.sort(np.array(times, dtype=float))
    T = times[-1] - times[0]
    if T <= 0:
        return None

    times = times - times[0]
    T = times[-1] + 0.01
    n = len(times)
    base_rate = n / T

    best_result = None
    best_nll = np.inf

    for trial in range(max_retries):
        rng = np.random.RandomState(42 + trial)
        mu_init = base_rate * 0.5 * (0.5 + rng.random())
        alpha_init = 0.3 * (0.5 + rng.random())
        beta_init = 2.0 * (0.5 + rng.random())
        x0 = [np.log(mu_init), np.log(alpha_init), np.log(beta_init)]

        try:
            res = minimize(
                hawkes_loglik, x0, args=(times, T),
                method='L-BFGS-B',
                bounds=[(-10, 5), (-10, 5), (-5, 8)],
                options={'maxiter': 500, 'ftol': 1e-10}
            )
            if res.success and res.fun < best_nll:
                best_nll = res.fun
                best_result = res
        except (RuntimeWarning, FloatingPointError, OverflowError):
            continue

    if best_result is None:
        return None

    mu = np.exp(best_result.x[0])
    alpha = np.exp(best_result.x[1])
    beta = np.exp(best_result.x[2])

    return {
        'mu': mu, 'alpha': alpha, 'beta': beta,
        'branching_ratio': alpha / beta if beta > 0 else 0,
        'n_events': n, 'T_hours': T,
    }


# ================================================================
# DATA LOADING
# ================================================================

def load_framing_analyses():
    """Load all cluster framings with hostile/clean labels."""
    analyses = []
    path = os.path.join(DATA, 'cluster_framings.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            is_hostile = row.get('is_hostile', 'f') == 't'
            analyses.append({
                'framing_id': int(row['framing_id']),
                'cluster_id': row['cluster_id'],
                'is_hostile': is_hostile,
                'confidence': float(row.get('confidence', 0) or 0),
                'operation_name': row.get('operation_name', ''),
                'event_fact': row.get('event_fact', ''),
                'state_framing': row.get('state_framing', ''),
                'framing_delta': row.get('framing_delta', ''),
            })
    return analyses


def load_framing_cluster_signals():
    """Load signals per cluster from fresh export."""
    clusters = defaultdict(list)
    path = os.path.join(DATA, 'framing_cluster_signals.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            cid = row.get('cluster_id', '')
            ts_raw = row.get('published_at', '')
            cat = row.get('source_category', '').strip().lower()
            t = parse_timestamp(ts_raw)
            clusters[cid].append({
                'time': t,
                'source_category': cat,
                'source_type': row.get('source_type', ''),
                'channel': row.get('channel', ''),
                'feed_handle': row.get('feed_handle', ''),
                'title': row.get('title', ''),
            })
    return clusters


def load_cluster_members_for_ids(target_ids):
    """Load cluster members from 90-day export for specific cluster IDs."""
    clusters = defaultdict(list)
    path = os.path.join(DATA, 'cluster_members.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            cid = row.get('cluster_id', '')
            if cid in target_ids:
                t = parse_timestamp(row.get('published_at', ''))
                clusters[cid].append({
                    'time': t,
                    'source_category': row.get('source_category', '').strip().lower(),
                })
    return clusters


# ================================================================
# FEATURE COMPUTATION
# ================================================================

def compute_state_ratio(signals):
    """Compute fraction of signals from Russian state media."""
    n = len(signals)
    if n == 0:
        return 0
    state_n = sum(1 for s in signals if is_state_category(s.get('source_category', '')))
    return state_n / n


def compute_fimi_score(analysis):
    """
    Compute FIMI score from framing_delta text.
    Detects FIMI techniques: hedging, omission, amplification, fabrication.
    Score = count of distinct techniques detected (0-4).
    """
    text = (analysis.get('framing_delta', '') + ' ' +
            analysis.get('state_framing', '')).lower()
    score = 0
    techniques_found = []

    if any(kw in text for kw in FIMI_HEDGING):
        score += 1
        techniques_found.append('hedging')
    if any(kw in text for kw in FIMI_OMISSION):
        score += 1
        techniques_found.append('omission')
    if any(kw in text for kw in FIMI_AMPLIFICATION):
        score += 1
        techniques_found.append('amplification')
    if any(kw in text for kw in FIMI_FABRICATION):
        score += 1
        techniques_found.append('fabrication')

    return score, techniques_found


def compute_temporal_features(signals):
    """Compute temporal burstiness features."""
    times = sorted(s['time'] for s in signals if s.get('time') is not None)
    if len(times) < 2:
        return {'span_h': 0, 'cv': 0, 'burstiness': 0}

    gaps = [times[i + 1] - times[i] for i in range(len(times) - 1)]
    gaps = [g for g in gaps if g > 0]

    if not gaps:
        return {'span_h': times[-1] - times[0], 'cv': 0, 'burstiness': 0}

    mean_gap = np.mean(gaps)
    std_gap = np.std(gaps, ddof=1) if len(gaps) > 1 else 0
    cv = std_gap / mean_gap if mean_gap > 0 else 0
    burstiness = (cv - 1) / (cv + 1) if (cv + 1) != 0 else 0

    return {
        'span_h': times[-1] - times[0],
        'cv': cv,
        'burstiness': burstiness,
    }


# ================================================================
# FISHER LINEAR DISCRIMINANT
# ================================================================

def fisher_discriminant(X, y):
    """
    Compute Fisher Linear Discriminant weights.

    X: (N, p) feature matrix
    y: (N,) binary labels (0/1)

    Returns: weights w such that score = X_std @ w
    """
    # Standardize features
    mu = np.mean(X, axis=0)
    sigma = np.std(X, axis=0, ddof=1)
    sigma[sigma == 0] = 1
    X_std = (X - mu) / sigma

    # Class means in standardized space
    X0 = X_std[y == 0]
    X1 = X_std[y == 1]
    mu0 = np.mean(X0, axis=0)
    mu1 = np.mean(X1, axis=0)

    # Within-class scatter matrix
    S0 = np.cov(X0.T) if len(X0) > 1 else np.zeros((X.shape[1], X.shape[1]))
    S1 = np.cov(X1.T) if len(X1) > 1 else np.zeros((X.shape[1], X.shape[1]))

    # Handle scalar case
    if X.shape[1] == 1:
        S0 = np.array([[np.var(X0, ddof=1)]]) if len(X0) > 1 else np.array([[0.0]])
        S1 = np.array([[np.var(X1, ddof=1)]]) if len(X1) > 1 else np.array([[0.0]])

    n0, n1 = len(X0), len(X1)
    Sw = (n0 - 1) * S0 + (n1 - 1) * S1

    # Add regularization for numerical stability
    Sw += np.eye(X.shape[1]) * 1e-6

    try:
        w = np.linalg.solve(Sw, mu1 - mu0)
    except np.linalg.LinAlgError:
        w = np.linalg.lstsq(Sw, mu1 - mu0, rcond=None)[0]

    return w, mu, sigma


def fisher_score(X, w, mu, sigma):
    """Compute Fisher scores for feature matrix X."""
    sigma_safe = sigma.copy()
    sigma_safe[sigma_safe == 0] = 1
    X_std = (X - mu) / sigma_safe
    return X_std @ w


def optimal_threshold(scores, y):
    """Find threshold maximizing F1 score."""
    thresholds = np.linspace(np.min(scores) - 0.5, np.max(scores) + 0.5, 200)
    best_f1, best_th = 0, 0
    best_metrics = {}

    for th in thresholds:
        pred = (scores >= th).astype(int)
        tp = np.sum((pred == 1) & (y == 1))
        fp = np.sum((pred == 1) & (y == 0))
        fn = np.sum((pred == 0) & (y == 1))
        tn = np.sum((pred == 0) & (y == 0))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        acc = (tp + tn) / len(y)

        if f1 > best_f1:
            best_f1 = f1
            best_th = th
            best_metrics = {'prec': prec, 'rec': rec, 'f1': f1, 'acc': acc,
                            'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn}

    return best_th, best_metrics


# ================================================================
# STATISTICAL TESTS
# ================================================================

def welch_t(x, y):
    """Welch's t-test."""
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return 0, 1.0
    mx, my = np.mean(x), np.mean(y)
    sx, sy = np.std(x, ddof=1), np.std(y, ddof=1)
    se = np.sqrt(sx ** 2 / nx + sy ** 2 / ny)
    if se == 0:
        return 0, 1.0
    t = (mx - my) / se
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    return t, p


def cohens_d(x, y):
    """Cohen's d effect size."""
    pooled = np.sqrt((np.std(x, ddof=1) ** 2 + np.std(y, ddof=1) ** 2) / 2)
    return (np.mean(x) - np.mean(y)) / pooled if pooled > 0 else 0


def point_biserial(x, y_binary):
    """Point-biserial correlation between continuous x and binary y."""
    m1 = np.mean(x[y_binary == 1])
    m0 = np.mean(x[y_binary == 0])
    n1 = np.sum(y_binary == 1)
    n0 = np.sum(y_binary == 0)
    n = len(x)
    sx = np.std(x, ddof=0)
    if sx == 0:
        return 0, 1.0
    r = (m1 - m0) / sx * np.sqrt(n1 * n0 / n ** 2)
    # t-test for significance
    t_stat = r * np.sqrt((n - 2) / (1 - r ** 2)) if abs(r) < 1 else 0
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / math.sqrt(2))))
    return r, p


def bootstrap_f1(scores, y, threshold, n_boot=1000, rng_seed=42):
    """Bootstrap 95% CI on F1 score."""
    rng = np.random.RandomState(rng_seed)
    f1s = []
    n = len(scores)

    for _ in range(n_boot):
        idx = rng.choice(n, size=n, replace=True)
        s_boot = scores[idx]
        y_boot = y[idx]

        pred = (s_boot >= threshold).astype(int)
        tp = np.sum((pred == 1) & (y_boot == 1))
        fp = np.sum((pred == 1) & (y_boot == 0))
        fn = np.sum((pred == 0) & (y_boot == 1))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        f1s.append(f1)

    return np.array(f1s)


def loo_cv(X, y, feature_cols_label=""):
    """
    Leave-one-out cross-validation for Fisher discriminant.
    Returns predictions, probabilities, and metrics.
    """
    n = len(y)
    predictions = np.zeros(n)
    scores_loo = np.zeros(n)

    for i in range(n):
        # Train on all except i
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        X_train, y_train = X[mask], y[mask]
        X_test = X[i:i + 1]

        # Fit Fisher on training set
        w, mu, sigma = fisher_discriminant(X_train, y_train)
        # Score test point
        score_i = fisher_score(X_test, w, mu, sigma)[0]
        scores_loo[i] = score_i

        # Find optimal threshold on training set
        train_scores = fisher_score(X_train, w, mu, sigma)
        th, _ = optimal_threshold(train_scores, y_train)
        predictions[i] = 1 if score_i >= th else 0

    tp = np.sum((predictions == 1) & (y == 1))
    fp = np.sum((predictions == 1) & (y == 0))
    fn = np.sum((predictions == 0) & (y == 1))
    tn = np.sum((predictions == 0) & (y == 0))

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
    acc = (tp + tn) / n

    return {
        'predictions': predictions,
        'scores': scores_loo,
        'prec': prec, 'rec': rec, 'f1': f1, 'acc': acc,
        'tp': int(tp), 'fp': int(fp), 'fn': int(fn), 'tn': int(tn),
    }


def power_analysis_two_group(d, alpha=0.01, power=0.80, ratio=1.0):
    """
    Required sample size per group for two-sample t-test.
    d: Cohen's d effect size
    alpha: significance level
    ratio: n2/n1 ratio
    """
    from scipy.stats import norm
    if d == 0:
        return float('inf')
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    n1 = ((z_alpha + z_beta) ** 2 * (1 + 1 / ratio)) / (d ** 2)
    return math.ceil(n1)


# ================================================================
# MAIN
# ================================================================

def main():
    np.random.seed(42)

    print("=" * 78)
    print("25. FISHER PRE-SCREEN REVALIDATION ON EXPANDED DATASET")
    print("=" * 78)

    # ------------------------------------------------------------------
    # 1. LOAD DATA
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 1: DATA LOADING")
    print("=" * 78)

    analyses = load_framing_analyses()
    cluster_signals = load_framing_cluster_signals()

    hostile = [a for a in analyses if a['is_hostile']]
    clean = [a for a in analyses if not a['is_hostile']]
    print(f"\nFraming analyses loaded: {len(analyses)} total")
    print(f"  Hostile: {len(hostile)}")
    print(f"  Clean:   {len(clean)}")
    print(f"  Class ratio: {len(hostile)}/{len(clean)} = {len(hostile)/len(clean):.2f}")

    # Also load from cluster_members.csv as fallback/cross-check
    target_ids = {a['cluster_id'] for a in analyses}
    cm_clusters = load_cluster_members_for_ids(target_ids)

    # ------------------------------------------------------------------
    # 2. COMPUTE FEATURES
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 2: FEATURE COMPUTATION")
    print("=" * 78)

    features = []
    for a in analyses:
        cid = a['cluster_id']
        sigs = cluster_signals.get(cid, [])

        # Use framing_cluster_signals if available, else cluster_members
        if not sigs:
            sigs = cm_clusters.get(cid, [])

        # State ratio
        sr = compute_state_ratio(sigs)

        # FIMI score from framing text
        fimi, fimi_techniques = compute_fimi_score(a)

        # Temporal features
        temp = compute_temporal_features(sigs)

        # Hawkes branching ratio
        times = [s['time'] for s in sigs if s.get('time') is not None]
        hawkes_result = fit_hawkes(times) if len(times) >= 3 else None
        br = hawkes_result['branching_ratio'] if hawkes_result else 0

        features.append({
            'cluster_id': cid,
            'is_hostile': a['is_hostile'],
            'label': 1 if a['is_hostile'] else 0,
            'state_ratio': sr,
            'fimi_score': fimi,
            'fimi_binary': 1 if fimi > 0 else 0,
            'fimi_techniques': fimi_techniques,
            'signal_count': len(sigs),
            'hawkes_br': br,
            'cv': temp['cv'],
            'burstiness': temp['burstiness'],
            'span_h': temp['span_h'],
            'confidence': a['confidence'],
            'operation_name': a['operation_name'][:50],
        })

    # Feature table
    print(f"\n{'CID':>6s}  {'Label':>6s}  {'SR':>5s}  {'FIMI':>4s}  {'BR':>6s}  "
          f"{'N':>3s}  {'CV':>5s}  {'Name'}")
    print("-" * 90)
    for f in sorted(features, key=lambda x: (-x['label'], -x['state_ratio'])):
        label = "HOST" if f['label'] else "CLEAN"
        name = f['operation_name'] or '—'
        print(f"{f['cluster_id']:>6s}  {label:>6s}  {f['state_ratio']:5.2f}  "
              f"{f['fimi_score']:4d}  {f['hawkes_br']:6.3f}  "
              f"{f['signal_count']:3d}  {f['cv']:5.2f}  {name}")

    # ------------------------------------------------------------------
    # 3. FEATURE IMPORTANCE (Point-biserial correlation)
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 3: FEATURE IMPORTANCE (Point-Biserial Correlation)")
    print("=" * 78)

    y = np.array([f['label'] for f in features])
    feature_names = ['state_ratio', 'fimi_score', 'fimi_binary', 'hawkes_br',
                     'cv', 'burstiness', 'signal_count', 'span_h']

    print(f"\n{'Feature':<20s}  {'r':>8s}  {'p-value':>10s}  {'Hostile μ':>10s}  "
          f"{'Clean μ':>10s}  {'Sig':>5s}")
    print("-" * 78)

    for fname in feature_names:
        x = np.array([f[fname] for f in features])
        r, p = point_biserial(x, y)
        h_mean = np.mean(x[y == 1])
        c_mean = np.mean(x[y == 0])
        sig = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else ''
        print(f"{fname:<20s}  {r:+8.3f}  {p:10.4f}  {h_mean:10.3f}  "
              f"{c_mean:10.3f}  {sig:>5s}")

    # Welch's t-test for key features
    print("\nWelch's t-tests (hostile vs clean):")
    for fname in ['state_ratio', 'fimi_score', 'hawkes_br']:
        h_vals = np.array([f[fname] for f in features if f['label'] == 1])
        c_vals = np.array([f[fname] for f in features if f['label'] == 0])
        t_stat, p_val = welch_t(h_vals, c_vals)
        d = cohens_d(h_vals, c_vals)
        print(f"  {fname:<15s}: t={t_stat:+.3f}, p={p_val:.4f}, d={d:+.3f} "
              f"({'large' if abs(d) > 0.8 else 'medium' if abs(d) > 0.5 else 'small'})")

    # ------------------------------------------------------------------
    # 4. FISHER DISCRIMINANT: ORIGINAL (state_ratio + fimi_score)
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 4: FISHER DISCRIMINANT — ORIGINAL (state_ratio + fimi_score)")
    print("=" * 78)

    X_orig = np.column_stack([
        [f['state_ratio'] for f in features],
        [f['fimi_score'] for f in features],
    ])

    w_orig, mu_orig, sigma_orig = fisher_discriminant(X_orig, y)
    scores_orig = fisher_score(X_orig, w_orig, mu_orig, sigma_orig)
    th_orig, metrics_orig = optimal_threshold(scores_orig, y)

    print(f"\nFisher weights (standardized):")
    print(f"  state_ratio: {w_orig[0]:+.4f}")
    print(f"  fimi_score:  {w_orig[1]:+.4f}")
    print(f"\nOptimal threshold: {th_orig:.4f}")
    print(f"  Precision: {metrics_orig['prec']:.3f}")
    print(f"  Recall:    {metrics_orig['rec']:.3f}")
    print(f"  F1:        {metrics_orig['f1']:.3f}")
    print(f"  Accuracy:  {metrics_orig['acc']:.3f}")
    print(f"  TP={metrics_orig['tp']}, FP={metrics_orig['fp']}, "
          f"FN={metrics_orig['fn']}, TN={metrics_orig['tn']}")

    # Compare with Experiment 25 weights
    print(f"\n  Comparison with Experiment 25 (N=13):")
    print(f"    Exp 25: w = [0.670 (state_ratio), 0.742 (fimi_score)]")
    print(f"    N=30:   w = [{w_orig[0]:.3f} (state_ratio), {w_orig[1]:.3f} (fimi_score)]")

    # LOO cross-validation
    print(f"\n  Leave-One-Out Cross-Validation:")
    loo_orig = loo_cv(X_orig, y, "state_ratio + fimi_score")
    print(f"    LOO Precision: {loo_orig['prec']:.3f}")
    print(f"    LOO Recall:    {loo_orig['rec']:.3f}")
    print(f"    LOO F1:        {loo_orig['f1']:.3f}")
    print(f"    LOO Accuracy:  {loo_orig['acc']:.3f}")
    print(f"    TP={loo_orig['tp']}, FP={loo_orig['fp']}, "
          f"FN={loo_orig['fn']}, TN={loo_orig['tn']}")

    # Misclassified cases
    loo_preds = loo_orig['predictions']
    print(f"\n  Misclassified cases (LOO):")
    for i, f in enumerate(features):
        actual = f['label']
        pred = int(loo_preds[i])
        if actual != pred:
            kind = "FP (clean→hostile)" if pred == 1 else "FN (hostile→clean)"
            name = f['operation_name'] or '—'
            print(f"    {kind}: cluster={f['cluster_id']}, SR={f['state_ratio']:.2f}, "
                  f"FIMI={f['fimi_score']}, BR={f['hawkes_br']:.3f}, {name}")

    # Bootstrap CI
    boot_f1s = bootstrap_f1(scores_orig, y, th_orig, n_boot=1000)
    ci_lo, ci_hi = np.percentile(boot_f1s, [2.5, 97.5])
    print(f"\n  Bootstrap 95% CI on F1 (1000 resamples):")
    print(f"    Point estimate: {metrics_orig['f1']:.3f}")
    print(f"    95% CI: [{ci_lo:.3f}, {ci_hi:.3f}]")
    print(f"    Mean bootstrap F1: {np.mean(boot_f1s):.3f}")
    print(f"    Std:  {np.std(boot_f1s):.3f}")

    # ------------------------------------------------------------------
    # 4b. SENSITIVITY: LLM-ANALYZED ONLY (exclude auto-classified clean)
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 4b: SENSITIVITY — LLM-ANALYZED SAMPLES ONLY")
    print("=" * 78)
    print("\nAuto-classified clean samples have empty framing_delta text,")
    print("so FIMI=0 by construction. This may inflate FIMI's discriminative")
    print("power. Rerun Fisher on only LLM-analyzed samples.\n")

    # Identify LLM-analyzed samples (have framing_delta text)
    llm_mask = []
    for f in features:
        # Find the matching analysis
        a_match = None
        for a in analyses:
            if a['cluster_id'] == f['cluster_id']:
                a_match = a
                break
        has_text = bool(a_match and a_match.get('framing_delta', '').strip()
                        and 'Auto-classified' not in a_match.get('event_fact', ''))
        llm_mask.append(has_text)
        f['llm_analyzed'] = has_text

    n_llm = sum(llm_mask)
    n_auto = len(llm_mask) - n_llm
    print(f"LLM-analyzed: {n_llm}  (hostile: {sum(1 for f,m in zip(features,llm_mask) if m and f['label']==1)}, "
          f"clean: {sum(1 for f,m in zip(features,llm_mask) if m and f['label']==0)})")
    print(f"Auto-clean:   {n_auto}")

    llm_features = [f for f, m in zip(features, llm_mask) if m]
    if len(llm_features) >= 5 and sum(f['label'] for f in llm_features) >= 2:
        y_llm = np.array([f['label'] for f in llm_features])
        X_llm = np.column_stack([
            [f['state_ratio'] for f in llm_features],
            [f['fimi_score'] for f in llm_features],
        ])

        w_llm, mu_llm, sig_llm = fisher_discriminant(X_llm, y_llm)
        scores_llm = fisher_score(X_llm, w_llm, mu_llm, sig_llm)
        th_llm, m_llm = optimal_threshold(scores_llm, y_llm)

        print(f"\nFisher on LLM-analyzed only (N={len(y_llm)}):")
        print(f"  Weights: SR={w_llm[0]:+.4f}, FIMI={w_llm[1]:+.4f}")
        print(f"  Train F1: {m_llm['f1']:.3f}  (prec={m_llm['prec']:.3f}, rec={m_llm['rec']:.3f})")

        loo_llm = loo_cv(X_llm, y_llm, "LLM-only: SR+FIMI")
        print(f"  LOO F1:   {loo_llm['f1']:.3f}  (prec={loo_llm['prec']:.3f}, rec={loo_llm['rec']:.3f})")
        print(f"  LOO TP={loo_llm['tp']}, FP={loo_llm['fp']}, FN={loo_llm['fn']}, TN={loo_llm['tn']}")

        # Feature correlations in LLM-only set
        for fname in ['state_ratio', 'fimi_score']:
            x = np.array([f[fname] for f in llm_features])
            r, p = point_biserial(x, y_llm)
            print(f"  {fname}: r={r:+.3f}, p={p:.4f}")

        # B5 equivalent on LLM-only
        sr_llm = np.array([f['state_ratio'] for f in llm_features])
        fimi_llm = np.array([f['fimi_score'] for f in llm_features])
        b5_llm = ((sr_llm > 0.50) | (fimi_llm > 0)).astype(int)
        b5_tp = np.sum((b5_llm == 1) & (y_llm == 1))
        b5_fp = np.sum((b5_llm == 1) & (y_llm == 0))
        b5_fn = np.sum((b5_llm == 0) & (y_llm == 1))
        b5_pr = b5_tp / (b5_tp + b5_fp) if (b5_tp + b5_fp) > 0 else 0
        b5_rc = b5_tp / (b5_tp + b5_fn) if (b5_tp + b5_fn) > 0 else 0
        b5_f1 = 2 * b5_pr * b5_rc / (b5_pr + b5_rc) if (b5_pr + b5_rc) > 0 else 0
        print(f"\n  B5 (SR>0.5 OR FIMI>0) on LLM-only: F1={b5_f1:.3f} "
              f"(prec={b5_pr:.3f}, rec={b5_rc:.3f})")

        # Show misclassified
        loo_llm_preds = loo_llm['predictions']
        print(f"\n  Misclassified (LOO, LLM-only):")
        for i, f in enumerate(llm_features):
            if f['label'] != int(loo_llm_preds[i]):
                kind = "FP" if int(loo_llm_preds[i]) == 1 else "FN"
                name = f['operation_name'][:40] or '—'
                print(f"    {kind}: cluster={f['cluster_id']}, SR={f['state_ratio']:.2f}, "
                      f"FIMI={f['fimi_score']}, {name}")
    else:
        print("  Insufficient LLM-analyzed samples for sensitivity analysis")

    # ------------------------------------------------------------------
    # 5. FISHER + HAWKES BR
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 5: FISHER DISCRIMINANT + HAWKES BR")
    print("=" * 78)

    X_br = np.column_stack([
        [f['state_ratio'] for f in features],
        [f['fimi_score'] for f in features],
        [f['hawkes_br'] for f in features],
    ])

    w_br, mu_br, sigma_br = fisher_discriminant(X_br, y)
    scores_br = fisher_score(X_br, w_br, mu_br, sigma_br)
    th_br, metrics_br = optimal_threshold(scores_br, y)

    print(f"\nFisher weights (standardized):")
    print(f"  state_ratio: {w_br[0]:+.4f}")
    print(f"  fimi_score:  {w_br[1]:+.4f}")
    print(f"  hawkes_br:   {w_br[2]:+.4f}")
    print(f"\nOptimal threshold: {th_br:.4f}")
    print(f"  Precision: {metrics_br['prec']:.3f}")
    print(f"  Recall:    {metrics_br['rec']:.3f}")
    print(f"  F1:        {metrics_br['f1']:.3f}")
    print(f"  Accuracy:  {metrics_br['acc']:.3f}")

    # LOO
    loo_br = loo_cv(X_br, y, "state_ratio + fimi_score + hawkes_br")
    print(f"\n  LOO Cross-Validation:")
    print(f"    LOO Precision: {loo_br['prec']:.3f}")
    print(f"    LOO Recall:    {loo_br['rec']:.3f}")
    print(f"    LOO F1:        {loo_br['f1']:.3f}")
    print(f"    LOO Accuracy:  {loo_br['acc']:.3f}")

    # Misclassified
    loo_br_preds = loo_br['predictions']
    print(f"\n  Misclassified cases (LOO):")
    for i, f in enumerate(features):
        actual = f['label']
        pred = int(loo_br_preds[i])
        if actual != pred:
            kind = "FP (clean→hostile)" if pred == 1 else "FN (hostile→clean)"
            name = f['operation_name'] or '—'
            print(f"    {kind}: cluster={f['cluster_id']}, SR={f['state_ratio']:.2f}, "
                  f"FIMI={f['fimi_score']}, BR={f['hawkes_br']:.3f}, {name}")

    # Bootstrap CI
    boot_f1s_br = bootstrap_f1(scores_br, y, th_br, n_boot=1000)
    ci_lo_br, ci_hi_br = np.percentile(boot_f1s_br, [2.5, 97.5])
    print(f"\n  Bootstrap 95% CI on F1 (1000 resamples):")
    print(f"    Point estimate: {metrics_br['f1']:.3f}")
    print(f"    95% CI: [{ci_lo_br:.3f}, {ci_hi_br:.3f}]")

    # ------------------------------------------------------------------
    # 6. ALTERNATIVE FEATURE COMBINATIONS
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 6: ALTERNATIVE FEATURE COMBINATIONS")
    print("=" * 78)

    combos = {
        'state_ratio only': [['state_ratio']],
        'fimi_score only': [['fimi_score']],
        'hawkes_br only': [['hawkes_br']],
        'SR + FIMI (original)': [['state_ratio', 'fimi_score']],
        'SR + BR': [['state_ratio', 'hawkes_br']],
        'FIMI + BR': [['fimi_score', 'hawkes_br']],
        'SR + FIMI + BR': [['state_ratio', 'fimi_score', 'hawkes_br']],
        'SR + FIMI + BR + CV': [['state_ratio', 'fimi_score', 'hawkes_br', 'cv']],
    }

    print(f"\n{'Combination':<30s}  {'Train F1':>8s}  {'LOO F1':>7s}  {'LOO Acc':>7s}  "
          f"{'LOO TP':>6s}  {'LOO FP':>6s}  {'LOO FN':>6s}")
    print("-" * 78)

    for name, (cols,) in combos.items():
        X_c = np.column_stack([[f[c] for f in features] for c in cols])
        if X_c.ndim == 1:
            X_c = X_c.reshape(-1, 1)

        w_c, mu_c, sig_c = fisher_discriminant(X_c, y)
        scores_c = fisher_score(X_c, w_c, mu_c, sig_c)
        _, m_c = optimal_threshold(scores_c, y)

        loo_c = loo_cv(X_c, y, name)

        print(f"{name:<30s}  {m_c['f1']:8.3f}  {loo_c['f1']:7.3f}  {loo_c['acc']:7.3f}  "
              f"{loo_c['tp']:6d}  {loo_c['fp']:6d}  {loo_c['fn']:6d}")

    # ------------------------------------------------------------------
    # 7. BASELINE COMPARISONS (from Experiment 24)
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 7: BASELINE COMPARISONS")
    print("=" * 78)

    baselines = {}

    # B1: Random
    rng = np.random.RandomState(42)
    b1_pred = rng.randint(0, 2, size=len(y))
    b1_tp = np.sum((b1_pred == 1) & (y == 1))
    b1_fp = np.sum((b1_pred == 1) & (y == 0))
    b1_fn = np.sum((b1_pred == 0) & (y == 1))
    b1_prec = b1_tp / (b1_tp + b1_fp) if (b1_tp + b1_fp) > 0 else 0
    b1_rec = b1_tp / (b1_tp + b1_fn) if (b1_tp + b1_fn) > 0 else 0
    b1_f1 = 2 * b1_prec * b1_rec / (b1_prec + b1_rec) if (b1_prec + b1_rec) > 0 else 0
    baselines['B1: Random'] = b1_f1

    # B2: Majority (always clean)
    baselines['B2: Majority (clean)'] = 0.0

    # B3: Volume > median
    vols = np.array([f['signal_count'] for f in features])
    b3_pred = (vols > np.median(vols)).astype(int)
    b3_tp = np.sum((b3_pred == 1) & (y == 1))
    b3_fp = np.sum((b3_pred == 1) & (y == 0))
    b3_fn = np.sum((b3_pred == 0) & (y == 1))
    b3_prec = b3_tp / (b3_tp + b3_fp) if (b3_tp + b3_fp) > 0 else 0
    b3_rec = b3_tp / (b3_tp + b3_fn) if (b3_tp + b3_fn) > 0 else 0
    b3_f1 = 2 * b3_prec * b3_rec / (b3_prec + b3_rec) if (b3_prec + b3_rec) > 0 else 0
    baselines['B3: Volume > median'] = b3_f1

    # B4: state_ratio > 0.50
    sr_arr = np.array([f['state_ratio'] for f in features])
    b4_pred = (sr_arr > 0.50).astype(int)
    b4_tp = np.sum((b4_pred == 1) & (y == 1))
    b4_fp = np.sum((b4_pred == 1) & (y == 0))
    b4_fn = np.sum((b4_pred == 0) & (y == 1))
    b4_prec = b4_tp / (b4_tp + b4_fp) if (b4_tp + b4_fp) > 0 else 0
    b4_rec = b4_tp / (b4_tp + b4_fn) if (b4_tp + b4_fn) > 0 else 0
    b4_f1 = 2 * b4_prec * b4_rec / (b4_prec + b4_rec) if (b4_prec + b4_rec) > 0 else 0
    baselines['B4: SR > 0.50'] = b4_f1

    # B5: state_ratio > 0.5 OR fimi > 0
    fimi_arr = np.array([f['fimi_score'] for f in features])
    b5_pred = ((sr_arr > 0.50) | (fimi_arr > 0)).astype(int)
    b5_tp = np.sum((b5_pred == 1) & (y == 1))
    b5_fp = np.sum((b5_pred == 1) & (y == 0))
    b5_fn = np.sum((b5_pred == 0) & (y == 1))
    b5_prec = b5_tp / (b5_tp + b5_fp) if (b5_tp + b5_fp) > 0 else 0
    b5_rec = b5_tp / (b5_tp + b5_fn) if (b5_tp + b5_fn) > 0 else 0
    b5_f1 = 2 * b5_prec * b5_rec / (b5_prec + b5_rec) if (b5_prec + b5_rec) > 0 else 0
    baselines['B5: SR>0.5 OR FIMI>0'] = b5_f1

    print(f"\n{'Baseline':<30s}  {'F1':>6s}")
    print("-" * 40)
    for name, f1 in baselines.items():
        print(f"{name:<30s}  {f1:6.3f}")
    print(f"{'Fisher (SR+FIMI) LOO':<30s}  {loo_orig['f1']:6.3f}")
    print(f"{'Fisher (SR+FIMI+BR) LOO':<30s}  {loo_br['f1']:6.3f}")

    # ------------------------------------------------------------------
    # 8. POWER ANALYSIS
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 8: POWER ANALYSIS")
    print("=" * 78)

    # Effect size for state_ratio
    h_sr = np.array([f['state_ratio'] for f in features if f['label'] == 1])
    c_sr = np.array([f['state_ratio'] for f in features if f['label'] == 0])
    d_sr = cohens_d(h_sr, c_sr)

    # Effect size for fimi_score
    h_fimi = np.array([f['fimi_score'] for f in features if f['label'] == 1])
    c_fimi = np.array([f['fimi_score'] for f in features if f['label'] == 0])
    d_fimi = cohens_d(h_fimi, c_fimi)

    # Effect size for hawkes_br
    h_br = np.array([f['hawkes_br'] for f in features if f['label'] == 1])
    c_br = np.array([f['hawkes_br'] for f in features if f['label'] == 0])
    d_br = cohens_d(h_br, c_br)

    print(f"\nEffect sizes (Cohen's d):")
    print(f"  state_ratio: d = {d_sr:.3f} ({'large' if abs(d_sr) > 0.8 else 'medium' if abs(d_sr) > 0.5 else 'small'})")
    print(f"  fimi_score:  d = {d_fimi:.3f} ({'large' if abs(d_fimi) > 0.8 else 'medium' if abs(d_fimi) > 0.5 else 'small'})")
    print(f"  hawkes_br:   d = {d_br:.3f} ({'large' if abs(d_br) > 0.8 else 'medium' if abs(d_br) > 0.5 else 'small'})")

    print(f"\nCurrent sample: N={len(y)} (n_hostile={sum(y)}, n_clean={sum(1-y)})")
    print(f"  Exp 25 had: N=13 (n_hostile=6, n_clean=7)")
    print(f"  Exp 23 minimum: N=14")
    print(f"  Current N={len(y)} {'≥ minimum' if len(y) >= 14 else '< minimum'}")

    # Required N for p<0.01 significance
    from scipy.stats import norm

    print(f"\nRequired sample sizes for p<0.01, power=0.80:")
    for fname, d_val in [('state_ratio', d_sr), ('fimi_score', d_fimi), ('hawkes_br', d_br)]:
        if abs(d_val) > 0:
            n_needed = power_analysis_two_group(abs(d_val), alpha=0.01, power=0.80,
                                                ratio=len(clean) / len(hostile))
            print(f"  {fname:<15s}: d={d_val:.3f} → need n₁={n_needed} hostile "
                  f"(~n₂={int(n_needed * len(clean)/len(hostile))} clean)")
        else:
            print(f"  {fname:<15s}: d=0 → infinite sample needed")

    # ------------------------------------------------------------------
    # 9. TIERED DETECTION SIMULATION
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 9: TIERED DETECTION ARCHITECTURE")
    print("=" * 78)

    # Use the original Fisher (SR + FIMI) for tiered routing
    # T1: score > high_th → AUTO_HOSTILE
    # T2: low_th < score <= high_th → LLM_NEEDED
    # T3: score <= low_th → AUTO_CLEAN

    # Sweep tier boundaries
    print(f"\n{'T1 (auto-hostile)':>20s}  {'T3 (auto-clean)':>20s}  {'F1':>5s}  {'Acc':>5s}  "
          f"{'LLM%':>5s}  {'T1':>3s}  {'T2':>3s}  {'T3':>3s}")
    print("-" * 78)

    best_tier_f1 = 0
    best_tier_config = None

    for hi in np.linspace(-0.5, 2.0, 20):
        for lo in np.linspace(-2.0, hi - 0.1, 15):
            t1_mask = scores_orig >= hi  # auto hostile
            t3_mask = scores_orig <= lo  # auto clean
            t2_mask = ~t1_mask & ~t3_mask  # LLM needed

            # T1 predictions
            t1_pred = np.ones(np.sum(t1_mask))
            # T3 predictions
            t3_pred = np.zeros(np.sum(t3_mask))
            # T2: use ground truth (LLM is perfect in our simulation)
            t2_pred = y[t2_mask]

            all_pred = np.zeros(len(y))
            all_pred[t1_mask] = 1
            all_pred[t3_mask] = 0
            all_pred[t2_mask] = t2_pred

            tp = np.sum((all_pred == 1) & (y == 1))
            fp = np.sum((all_pred == 1) & (y == 0))
            fn = np.sum((all_pred == 0) & (y == 1))
            tn = np.sum((all_pred == 0) & (y == 0))

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
            acc = (tp + tn) / len(y)
            llm_pct = np.sum(t2_mask) / len(y) * 100

            # Only check configs with F1=1.0 and minimize LLM calls
            if f1 >= 1.0 and (best_tier_config is None or
                              llm_pct < best_tier_config['llm_pct']):
                best_tier_f1 = f1
                best_tier_config = {
                    'hi': hi, 'lo': lo, 'f1': f1, 'acc': acc,
                    'llm_pct': llm_pct,
                    't1': int(np.sum(t1_mask)),
                    't2': int(np.sum(t2_mask)),
                    't3': int(np.sum(t3_mask)),
                    'fp_auto': int(np.sum((all_pred == 1) & (y == 0) & t1_mask)),
                    'fn_auto': int(np.sum((all_pred == 0) & (y == 1) & t3_mask)),
                }

    if best_tier_config:
        c = best_tier_config
        print(f"  Best F1=1.0 config:")
        print(f"    T1 (auto-hostile): score > {c['hi']:.2f}  ({c['t1']} clusters)")
        print(f"    T2 (LLM needed):   {c['lo']:.2f} < score ≤ {c['hi']:.2f}  ({c['t2']} clusters)")
        print(f"    T3 (auto-clean):   score ≤ {c['lo']:.2f}  ({c['t3']} clusters)")
        print(f"    LLM calls: {c['llm_pct']:.0f}% ({c['t2']}/{len(y)})")
        print(f"    Auto-hostile FP: {c['fp_auto']}")
        print(f"    Auto-clean FN:   {c['fn_auto']}")

        # Print per-cluster tier assignment
        print(f"\n  Tier assignments:")
        for i, f in enumerate(features):
            s = scores_orig[i]
            if s > c['hi']:
                tier = "T1 AUTO_HOSTILE"
            elif s <= c['lo']:
                tier = "T3 AUTO_CLEAN"
            else:
                tier = "T2 LLM_NEEDED"
            label = "HOST" if f['label'] else "CLEAN"
            name = f['operation_name'][:40] or '—'
            correct = "✅" if (f['label'] == 1 and 'HOSTILE' in tier) or \
                             (f['label'] == 0 and 'CLEAN' in tier) or \
                             'LLM' in tier else "❌"
            print(f"    {tier:16s}  {label:5s}  score={s:+.3f}  "
                  f"SR={f['state_ratio']:.2f}  FIMI={f['fimi_score']}  {correct}  {name}")
    else:
        # No perfect config found - show best available
        print("  No config achieves F1=1.0. Showing best available:")
        # Find config minimizing errors
        best_config = None
        for hi in np.linspace(-0.5, 2.0, 20):
            for lo in np.linspace(-2.0, hi - 0.1, 15):
                t1_mask = scores_orig >= hi
                t3_mask = scores_orig <= lo
                t2_mask = ~t1_mask & ~t3_mask

                fp_auto = np.sum((y == 0) & t1_mask)
                fn_auto = np.sum((y == 1) & t3_mask)
                errors = fp_auto + fn_auto
                llm_pct = np.sum(t2_mask) / len(y) * 100

                if best_config is None or errors < best_config['errors'] or \
                   (errors == best_config['errors'] and llm_pct < best_config['llm_pct']):
                    best_config = {
                        'hi': hi, 'lo': lo, 'errors': errors,
                        'llm_pct': llm_pct,
                        'fp_auto': int(fp_auto), 'fn_auto': int(fn_auto),
                        't1': int(np.sum(t1_mask)),
                        't2': int(np.sum(t2_mask)),
                        't3': int(np.sum(t3_mask)),
                    }

        if best_config:
            c = best_config
            print(f"    T1 > {c['hi']:.2f}: {c['t1']} clusters, FP={c['fp_auto']}")
            print(f"    T2: {c['t2']} clusters (LLM needed)")
            print(f"    T3 ≤ {c['lo']:.2f}: {c['t3']} clusters, FN={c['fn_auto']}")
            print(f"    LLM calls: {c['llm_pct']:.0f}%, total errors: {c['errors']}")

    # ------------------------------------------------------------------
    # 10. FINDINGS SUMMARY
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("FINDINGS SUMMARY")
    print("=" * 78)

    # Determine verdict
    original_f1 = 0.92  # from Experiment 25
    new_f1_train = metrics_orig['f1']
    new_f1_loo = loo_orig['f1']
    new_f1_loo_br = loo_br['f1']

    replicates = new_f1_loo >= 0.80
    improves = new_f1_loo > original_f1
    br_helps = new_f1_loo_br > new_f1_loo

    print(f"""
1. DATASET EXPANSION
   - Original (Experiment 25): N=13 (6 hostile, 7 clean)
   - Current:                  N={len(y)} ({sum(y)} hostile, {sum(1-y)} clean)
   - Class ratio: {len(hostile)}/{len(clean)} = {len(hostile)/len(clean):.2f} (was 6/7 = 0.86)
   - The 24 clean analyses include Fisher auto-clean classifications
   - Hostile count unchanged (6) — the pipeline hasn't found new hostile framings

2. FISHER DISCRIMINANT REPLICATION
   - Experiment 25 (N=13): F1 = 0.92, weights = [0.670, 0.742]
   - N={len(y)} refit:      F1 = {new_f1_train:.3f} (train), LOO F1 = {new_f1_loo:.3f}
   - New weights: [{w_orig[0]:.3f}, {w_orig[1]:.3f}]
   - Bootstrap 95% CI on F1: [{ci_lo:.3f}, {ci_hi:.3f}]
   - Verdict: {"✅ REPLICATES" if replicates else "❌ DOES NOT REPLICATE"}
     (LOO F1 {">= 0.80 threshold" if replicates else "< 0.80 threshold"})

3. HAWKES BR CONTRIBUTION
   - Fisher + BR LOO F1: {new_f1_loo_br:.3f} (vs {new_f1_loo:.3f} without BR)
   - BR {"improves" if br_helps else "does not improve"} the discriminant
   - Hawkes BR effect size: d = {d_br:.3f} ({'large' if abs(d_br) > 0.8 else 'medium' if abs(d_br) > 0.5 else 'small'})

4. POWER ANALYSIS
   - N={len(y)} {"meets" if len(y) >= 14 else "does not meet"} the N=14 minimum from Experiment 23
   - For p<0.01 significance on state_ratio (d={d_sr:.2f}): need ~{power_analysis_two_group(abs(d_sr), 0.01, 0.80, len(clean)/len(hostile)) if abs(d_sr) > 0 else 'infinite'} hostile samples
   - Current hostile count ({sum(y)}) {"is sufficient" if sum(y) >= power_analysis_two_group(abs(d_sr), 0.01, 0.80, len(clean)/len(hostile)) else "is insufficient"} for p<0.01

5. HONEST ASSESSMENT
   - The N=6 hostile sample is the binding constraint — same 6 as Experiment 25
   - 24 clean samples provide better negative-class estimation
   - But the POSITIVE class hasn't grown, so the Fisher discriminant's
     ability to identify hostile framings is estimated from only 6 examples
   - The high F1 may still be a small-sample artifact — we need more hostile
     framings to reach statistical confidence at p<0.01
   - Class imbalance (6:24 = 1:4) affects the optimal threshold
   - Auto-classified clean samples have FIMI=0 by construction (no framing
     text to analyze), which inflates FIMI's discriminative power on the
     full dataset — the LLM-only sensitivity analysis is more honest
""")

    # Compute actual required hostile samples
    if abs(d_sr) > 0:
        n_hostile_needed_05 = power_analysis_two_group(abs(d_sr), 0.05, 0.80,
                                                       len(clean) / len(hostile))
        n_hostile_needed_01 = power_analysis_two_group(abs(d_sr), 0.01, 0.80,
                                                       len(clean) / len(hostile))
        print(f"6. SAMPLE SIZE REQUIREMENTS")
        print(f"   For α=0.05, power=0.80: need {n_hostile_needed_05} hostile samples "
              f"(have {sum(y)})")
        print(f"   For α=0.01, power=0.80: need {n_hostile_needed_01} hostile samples "
              f"(have {sum(y)})")
        print(f"   Estimated time to {n_hostile_needed_01} hostile: "
              f"~{math.ceil((n_hostile_needed_01 - sum(y)) / (sum(y) / 3))} months "
              f"(at ~{sum(y)/3:.1f} hostile/month rate)")

    print(f"\n{'='*78}")
    print("DONE")
    print(f"{'='*78}")


if __name__ == '__main__':
    main()
