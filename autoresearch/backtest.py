#!/usr/bin/env python3
"""CTI Backtest — the agent modifies this file to optimize weights and thresholds."""

import json
import statistics
from prepare import load_or_fetch, evaluate

# ═══════════════════════════════════════════════════
# AGENT: modify these parameters to optimize the CTI
# ═══════════════════════════════════════════════════

# How much each component contributes to the threat level prediction
component_weights = {
    "security": 40,
    "hybrid": 30,
    "fimi": 20,
    "economic": 10,
}

# Score thresholds for level transitions
level_thresholds = {
    "YELLOW": 10,
    "ORANGE": 40,
    "RED": 70,
}

# Smoothing: how much yesterday's prediction influences today's
momentum = 0.3  # 0 = no smoothing, 1 = fully sticky

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
    """Run leave-one-out backtest: predict each day using the prior window."""
    history = load_or_fetch()
    if len(history) < 5:
        print(f"Not enough data ({len(history)} days)")
        return None

    predicted_levels = []
    actual_levels = []
    predicted_scores = []
    prev_score = 0

    for i in range(1, len(history)):
        day = history[i]
        actual_score = day.get("score", 0)
        actual_level = day.get("level", "GREEN")

        # Use previous days as context
        window = history[max(0, i-7):i]
        window_scores = [d.get("score", 0) for d in window]

        if not window_scores:
            predicted_levels.append("GREEN")
            actual_levels.append(actual_level)
            continue

        # Predict: weighted trend + momentum
        mean_score = statistics.mean(window_scores)
        trend = window_scores[-1] - window_scores[0] if len(window_scores) > 1 else 0

        raw_prediction = mean_score + trend * 0.5
        smoothed = momentum * prev_score + (1 - momentum) * raw_prediction
        prev_score = smoothed

        predicted_level = score_to_level(smoothed)
        predicted_levels.append(predicted_level)
        actual_levels.append(actual_level)
        predicted_scores.append(smoothed)

    metrics = evaluate(predicted_levels, actual_levels, predicted_scores)

    print(f"Backtest ({len(predicted_levels)} days):")
    print(f"  Accuracy:   {metrics['prediction_accuracy']:.2%}")
    print(f"  Stability:  {metrics['stability']:.4f}")
    print(f"  Lead Time:  {metrics['lead_time']:.2%}")
    print(f"  ─────────────────")
    print(f"  eval_score: {metrics['eval_score']:.4f}")
    print()
    print(f"Parameters:")
    print(f"  level_thresholds: {json.dumps(level_thresholds)}")
    print(f"  momentum: {momentum}")

    return metrics


if __name__ == "__main__":
    run_backtest()
