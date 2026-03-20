#!/usr/bin/env python3
"""Phase 1: Brute-force CTI parameter optimization using NumPy vectorized ops."""

import json
import numpy as np
from prepare import load_or_fetch

def run():
    history = load_or_fetch()
    if len(history) < 10:
        print("Not enough data"); return

    # Extract arrays
    scores = np.array([d.get("score", 0.0) for d in history], dtype=np.float64)
    levels = np.array([{"GREEN":0,"YELLOW":1,"ORANGE":2,"RED":3}.get(d.get("level","GREEN"),0) for d in history])
    N = len(scores)

    # Parameter grid
    rng = np.random.default_rng(42)
    TRIALS = 100_000

    yellows = rng.uniform(3, 30, TRIALS)
    oranges = rng.uniform(20, 65, TRIALS)
    reds = rng.uniform(50, 95, TRIALS)
    # Ensure yellow < orange < red
    mask = (yellows < oranges - 3) & (oranges < reds - 3)
    yellows, oranges, reds = yellows[mask], oranges[mask], reds[mask]
    T = len(yellows)

    momentums = rng.uniform(0, 0.8, T)
    trend_mults = rng.uniform(0, 1.5, T)
    windows = rng.choice([3, 5, 7, 10, 14], T)

    print(f"Testing {T:,} valid parameter combos against {N} days...")

    best_score = 0
    best_params = {}

    for t in range(T):
        w = int(windows[t])
        mom = momentums[t]
        tm = trend_mults[t]
        y, o, r = yellows[t], oranges[t], reds[t]

        # Vectorized backtest
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

        # Accuracy
        accuracy = (preds == actuals).sum() / n

        # Stability
        transitions = (preds[1:] != preds[:-1]).sum()
        stability = 1.0 / (1.0 + transitions / n)

        # Lead time
        actual_changes = np.where(actuals[1:] != actuals[:-1])[0]
        lead_hits = sum(1 for c in actual_changes if c > 0 and preds[c-1] == actuals[c])
        lead_time = lead_hits / max(len(actual_changes), 1)

        eval_score = accuracy * 0.5 + stability * 0.3 + lead_time * 0.2

        if eval_score > best_score:
            best_score = eval_score
            best_params = {
                "yellow": round(float(y), 1), "orange": round(float(o), 1),
                "red": round(float(r), 1), "momentum": round(float(mom), 3),
                "trend_mult": round(float(tm), 3), "window": int(w),
                "accuracy": round(float(accuracy), 4),
                "stability": round(float(stability), 4),
                "lead_time": round(float(lead_time), 4),
                "eval_score": round(float(eval_score), 4),
            }

        if t % 20000 == 0 and t > 0:
            print(f"  {t:,}/{T:,} — best so far: {best_score:.4f}")

    print(f"\n{'='*50}")
    print(f"Best eval_score: {best_score:.4f}")
    print(f"{'='*50}")
    for k, v in best_params.items():
        print(f"  {k:15s}: {v}")

    with open("optimization_results.json", "w") as f:
        json.dump({"best": best_params, "trials": T, "data_days": N}, f, indent=2)
    print(f"\nSaved to optimization_results.json")

if __name__ == "__main__":
    run()
