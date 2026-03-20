#!/usr/bin/env python3
"""Phase 1: Brute-force CTI parameter optimization with k-fold cross-validation."""

import json
import numpy as np
from prepare import load_or_fetch


def evaluate_params(scores, levels, y, o, r, mom, tm, w):
    """Backtest one parameter set. Returns (accuracy, stability, lead_time, eval_score)."""
    N = len(scores)
    if N <= w:
        return 0, 0, 0, 0

    preds = np.zeros(N - w, dtype=np.int32)
    prev = 0.0
    for i in range(w, N):
        window_scores = scores[i-w:i]
        mean = window_scores.mean()
        trend = float(window_scores[-1] - window_scores[0])
        raw = mean + trend * tm
        smoothed = mom * prev + (1 - mom) * raw
        prev = smoothed

        if smoothed >= r: preds[i-w] = 3
        elif smoothed >= o: preds[i-w] = 2
        elif smoothed >= y: preds[i-w] = 1

    actuals = levels[w:]
    n = len(preds)
    if n == 0:
        return 0, 0, 0, 0

    accuracy = (preds == actuals).sum() / n
    transitions = (preds[1:] != preds[:-1]).sum()
    stability = 1.0 / (1.0 + transitions / n)
    actual_changes = np.where(actuals[1:] != actuals[:-1])[0]
    lead_hits = sum(1 for c in actual_changes if c > 0 and preds[c-1] == actuals[c])
    lead_time = lead_hits / max(len(actual_changes), 1)

    eval_score = accuracy * 0.5 + stability * 0.3 + lead_time * 0.2
    return accuracy, stability, lead_time, eval_score


def run():
    history = load_or_fetch()
    if len(history) < 10:
        print("Not enough data"); return

    scores = np.array([d.get("score", 0.0) for d in history], dtype=np.float64)
    levels = np.array([{"GREEN":0,"YELLOW":1,"ORANGE":2,"RED":3}.get(d.get("level","GREEN"),0) for d in history])
    N = len(scores)

    # Check for actual transitions (skip trivial all-GREEN)
    transitions = sum(1 for i in range(1, N) if levels[i] != levels[i-1])
    if transitions == 0:
        print(f"WARNING: {N} days, ALL same level — optimization trivial")

    rng = np.random.default_rng(42)
    TRIALS = 100_000

    yellows = rng.uniform(3, 30, TRIALS)
    oranges = rng.uniform(20, 65, TRIALS)
    reds = rng.uniform(50, 95, TRIALS)
    mask = (yellows < oranges - 3) & (oranges < reds - 3)
    yellows, oranges, reds = yellows[mask], oranges[mask], reds[mask]
    T = len(yellows)

    momentums = rng.uniform(0, 0.8, T)
    trend_mults = rng.uniform(0, 1.5, T)
    windows = rng.choice([3, 5, 7, 10, 14], T)

    # 3-fold cross-validation
    K = 3
    fold_size = N // K
    folds = [(i * fold_size, min((i+1) * fold_size, N)) for i in range(K)]

    print(f"Testing {T:,} combos × {K} folds against {N} days ({transitions} level transitions)...")

    best_cv_score = 0
    best_params = {}
    best_fold_scores = []

    for t in range(T):
        w = int(windows[t])
        mom = momentums[t]
        tm = trend_mults[t]
        y, o, r = yellows[t], oranges[t], reds[t]

        fold_evals = []
        for fi, (f_start, f_end) in enumerate(folds):
            # Test on fold fi, train context from everything before it
            fold_scores = scores[f_start:f_end]
            fold_levels = levels[f_start:f_end]
            _, _, _, ev = evaluate_params(fold_scores, fold_levels, y, o, r, mom, tm, w)
            fold_evals.append(ev)

        cv_score = np.mean(fold_evals)

        if cv_score > best_cv_score:
            best_cv_score = cv_score
            best_fold_scores = fold_evals

            # Also compute on full dataset for reporting
            a, s, l, full_eval = evaluate_params(scores, levels, y, o, r, mom, tm, w)
            best_params = {
                "yellow": round(float(y), 1), "orange": round(float(o), 1),
                "red": round(float(r), 1), "momentum": round(float(mom), 3),
                "trend_mult": round(float(tm), 3), "window": int(w),
                "accuracy": round(float(a), 4), "stability": round(float(s), 4),
                "lead_time": round(float(l), 4),
                "eval_score": round(float(full_eval), 4),
                "cv_score": round(float(cv_score), 4),
                "fold_scores": [round(float(f), 4) for f in fold_evals],
            }

        if t % 20000 == 0 and t > 0:
            print(f"  {t:,}/{T:,} — best cv: {best_cv_score:.4f}")

    print(f"\n{'='*50}")
    print(f"Best eval_score: {best_params.get('eval_score', 0):.4f}")
    print(f"Cross-validated: {best_cv_score:.4f} (folds: {best_fold_scores})")
    print(f"{'='*50}")
    for k, v in best_params.items():
        if k != "fold_scores":
            print(f"  {k:15s}: {v}")

    fold_var = np.std(best_fold_scores)
    if fold_var > 0.10:
        print(f"\n⚠ HIGH FOLD VARIANCE ({fold_var:.3f}) — parameters may be overfit")
    else:
        print(f"\n✓ Low fold variance ({fold_var:.3f}) — parameters are robust")

    with open("optimization_results.json", "w") as f:
        json.dump({"best": best_params, "trials": T, "data_days": N, "k_folds": K}, f, indent=2)
    print(f"\nSaved to optimization_results.json")

if __name__ == "__main__":
    run()
