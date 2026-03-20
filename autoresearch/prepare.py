#!/usr/bin/env python3
"""Prepare historical data for CTI backtesting. DO NOT MODIFY."""

import json
import os
import urllib.request

API = "https://estwarden.eu"
DATA_FILE = "history.json"


def fetch_history(days=90):
    """Fetch threat history from public API."""
    url = f"{API}/api/history?days={days}"
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read())
    if isinstance(data, dict):
        data = data.get("history", [])
    return data


def load_or_fetch(days=90):
    """Load cached data or fetch fresh."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            data = json.load(f)
        if len(data) >= days * 0.8:  # at least 80% coverage
            return data

    data = fetch_history(days)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Fetched {len(data)} days of history")
    return data


def evaluate(predictions, actuals):
    """Evaluate prediction accuracy. Returns dict of metrics."""
    if not predictions or not actuals or len(predictions) != len(actuals):
        return {"prediction_accuracy": 0, "stability": 0, "lead_time": 0, "eval_score": 0}

    # Prediction accuracy: how often predicted level matches actual
    correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
    accuracy = correct / len(predictions)

    # Stability: inverse of daily score changes (lower volatility = better)
    if len(predictions) > 1:
        changes = [abs(predictions[i] - predictions[i-1])
                   for i in range(1, len(predictions))
                   if isinstance(predictions[i], (int, float))]
        stability = 1.0 / (1.0 + (sum(changes) / max(len(changes), 1)))
    else:
        stability = 1.0

    # Lead time: how many transitions were predicted 1 day early
    lead_hits = 0
    transitions = 0
    for i in range(1, len(actuals)):
        if actuals[i] != actuals[i-1]:
            transitions += 1
            if i > 0 and predictions[i-1] == actuals[i]:
                lead_hits += 1
    lead_time = lead_hits / max(transitions, 1)

    # Composite score (weighted)
    eval_score = accuracy * 0.5 + stability * 0.3 + lead_time * 0.2

    return {
        "prediction_accuracy": round(accuracy, 4),
        "stability": round(stability, 4),
        "lead_time": round(lead_time, 4),
        "eval_score": round(eval_score, 4),
    }


if __name__ == "__main__":
    data = load_or_fetch(90)
    print(f"Data: {len(data)} days")
    print(f"Date range: {data[0]['date']} → {data[-1]['date']}")
    scores = [d.get("score", 0) for d in data]
    print(f"Score range: {min(scores):.1f} — {max(scores):.1f}")
    print(f"Mean: {sum(scores)/len(scores):.1f}")
