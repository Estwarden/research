#!/usr/bin/env python3
"""Prepare historical data for CTI backtesting. DO NOT MODIFY."""

import json
import os
import urllib.request

API = "https://estwarden.eu"
DATA_FILE = "history.json"
UA = {"User-Agent": "EstWarden-Research/1.0"}


def fetch_history():
    """Fetch threat index history from public API."""
    url = f"{API}/api/threat-index/history"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if isinstance(data, dict):
        data = data.get("history", data.get("data", []))
    return data


def fetch_today():
    """Fetch current threat index with component breakdown."""
    url = f"{API}/api/threat-index"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def load_or_fetch():
    """Load cached data or fetch fresh."""
    if os.path.exists(DATA_FILE):
        age = os.path.getmtime(DATA_FILE)
        import time
        if time.time() - age < 3600:  # cache for 1 hour
            with open(DATA_FILE) as f:
                return json.load(f)

    data = fetch_history()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Fetched {len(data)} days of history")
    return data


def evaluate(predicted_levels, actual_levels, predicted_scores=None):
    """Evaluate prediction quality. Returns metrics dict."""
    n = min(len(predicted_levels), len(actual_levels))
    if n == 0:
        return {"prediction_accuracy": 0, "stability": 0, "lead_time": 0, "eval_score": 0}

    # Accuracy: predicted level matches actual
    correct = sum(1 for i in range(n) if predicted_levels[i] == actual_levels[i])
    accuracy = correct / n

    # Stability: fewer level transitions = more stable
    if n > 1:
        transitions = sum(1 for i in range(1, n) if predicted_levels[i] != predicted_levels[i-1])
        stability = 1.0 / (1.0 + transitions / n)
    else:
        stability = 1.0

    # Lead time: did we predict tomorrow's level change today?
    lead_hits = 0
    actual_transitions = 0
    for i in range(1, n):
        if actual_levels[i] != actual_levels[i-1]:
            actual_transitions += 1
            if predicted_levels[i-1] == actual_levels[i]:
                lead_hits += 1
    lead_time = lead_hits / max(actual_transitions, 1)

    eval_score = accuracy * 0.5 + stability * 0.3 + lead_time * 0.2

    return {
        "prediction_accuracy": round(accuracy, 4),
        "stability": round(stability, 4),
        "lead_time": round(lead_time, 4),
        "eval_score": round(eval_score, 4),
    }


if __name__ == "__main__":
    data = load_or_fetch()
    print(f"Data: {len(data)} days")
    if data:
        print(f"Range: {data[0]['date']} → {data[-1]['date']}")
        scores = [d.get("score", 0) for d in data]
        levels = [d.get("level", "?") for d in data]
        print(f"Scores: {min(scores):.1f} — {max(scores):.1f} (mean {sum(scores)/len(scores):.1f})")
        from collections import Counter
        print(f"Levels: {dict(Counter(levels))}")

    today = fetch_today()
    print(f"\nToday: {today.get('level')} ({today.get('score', 0):.1f}/100)")
    print(f"Components: {json.dumps(today.get('components', {}), indent=2)}")
