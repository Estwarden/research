#!/usr/bin/env python3
"""CTI Backtest — the agent modifies this file to optimize weights and thresholds."""

import json
import statistics
from prepare import load_or_fetch, evaluate

# ═══════════════════════════════════════════════════
# AGENT: modify these parameters to optimize the CTI
# ═══════════════════════════════════════════════════

weights = {
    "gpsjam": 20,
    "adsb": 15,
    "acled": 15,
    "firms": 15,
    "ais": 10,
    "telegram": 10,
    "rss": 5,
    "gdelt": 5,
    "ioda": 5,
}

thresholds = {
    "info": 2.0,
    "warning": 3.0,
    "alert": 4.0,
}

baseline_window_days = 7

# ═══════════════════════════════════════════════════


def score_to_level(score):
    if score < 25:
        return "GREEN"
    elif score < 50:
        return "YELLOW"
    elif score < 75:
        return "ORANGE"
    return "RED"


def compute_cti(day_data, baseline_data):
    """Compute CTI score for a single day given baseline statistics."""
    total_weight = sum(weights.values())
    score = 0

    for source, weight in weights.items():
        # Get baseline stats
        baseline_values = [d.get("score", 0) for d in baseline_data]
        if len(baseline_values) < 3:
            continue

        mean = statistics.mean(baseline_values)
        stddev = max(statistics.stdev(baseline_values) if len(baseline_values) > 1 else 1, 1)

        current = day_data.get("score", 0)
        z = max((current - mean) / stddev, 0)
        contrib = min(z * 10, 100) * (weight / total_weight)
        score += contrib

    return min(score, 100)


def run_backtest():
    """Run backtest over historical data."""
    history = load_or_fetch(90)
    if len(history) < baseline_window_days + 10:
        print("Not enough data for backtest")
        return

    predictions = []
    actuals = []

    for i in range(baseline_window_days, len(history)):
        baseline = history[i - baseline_window_days:i]
        day = history[i]

        predicted_score = compute_cti(day, baseline)
        predicted_level = score_to_level(predicted_score)
        actual_level = day.get("level", "GREEN")

        predictions.append(predicted_level)
        actuals.append(actual_level)

    metrics = evaluate(predictions, actuals)

    print(f"Backtest Results ({len(predictions)} days):")
    print(f"  Prediction Accuracy: {metrics['prediction_accuracy']:.2%}")
    print(f"  Stability:           {metrics['stability']:.4f}")
    print(f"  Lead Time:           {metrics['lead_time']:.2%}")
    print(f"  ─────────────────────")
    print(f"  eval_score:          {metrics['eval_score']:.4f}")
    print()
    print(f"Weights: {json.dumps(weights)}")
    print(f"Thresholds: {json.dumps(thresholds)}")
    print(f"Baseline window: {baseline_window_days} days")

    return metrics


if __name__ == "__main__":
    run_backtest()
