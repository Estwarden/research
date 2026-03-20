#!/usr/bin/env python3
"""CTI Backtest — Phase 1 optimized, Phase 2 agent-editable."""

import json
import statistics
from prepare import load_or_fetch, evaluate

# ═══════════════════════════════════════════════════
# Optimized by Phase 1 (85K parameter search)
# Phase 2 agent: improve the LOGIC below, not just numbers
# ═══════════════════════════════════════════════════

level_thresholds = {
    "YELLOW": 15.2,
    "ORANGE": 59.7,
    "RED": 92.8,
}

momentum = 0.034
trend_mult = 0.927
window_days = 7

# ═══════════════════════════════════════════════════


def score_to_level(score):
    if score >= level_thresholds["RED"]:
        return "RED"
    elif score >= level_thresholds["ORANGE"]:
        return "ORANGE"
    elif score >= level_thresholds["YELLOW"]:
        return "YELLOW"
    return "GREEN"


def run_backtest():
    history = load_or_fetch()
    if len(history) < window_days + 5:
        print(f"Not enough data ({len(history)} days)")
        return None

    predicted_levels = []
    actual_levels = []
    prev_score = 0

    for i in range(window_days, len(history)):
        day = history[i]
        actual_level = day.get("level", "GREEN")

        window = history[max(0, i - window_days):i]
        window_scores = [d.get("score", 0) for d in window]

        if not window_scores:
            predicted_levels.append("GREEN")
            actual_levels.append(actual_level)
            continue

        mean_score = statistics.mean(window_scores)
        trend = window_scores[-1] - window_scores[0] if len(window_scores) > 1 else 0

        raw_prediction = mean_score + trend * trend_mult
        smoothed = momentum * prev_score + (1 - momentum) * raw_prediction
        prev_score = smoothed

        predicted_level = score_to_level(smoothed)
        predicted_levels.append(predicted_level)
        actual_levels.append(actual_level)

    metrics = evaluate(predicted_levels, actual_levels)

    print(f"Backtest ({len(predicted_levels)} days):")
    print(f"  Accuracy:   {metrics['prediction_accuracy']:.2%}")
    print(f"  Stability:  {metrics['stability']:.4f}")
    print(f"  Lead Time:  {metrics['lead_time']:.2%}")
    print(f"  ─────────────────")
    print(f"  eval_score: {metrics['eval_score']:.4f}")

    return metrics


if __name__ == "__main__":
    run_backtest()
