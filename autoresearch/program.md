# EstWarden CTI Autoresearch

Automated optimization of the Composite Threat Index for Baltic security monitoring.

## Two phases

### Phase 1: Parameter search (optimize.py)
Brute-force search over thresholds, momentum, trend multiplier, window size.
NumPy vectorized, 100K combinations in seconds. No LLM needed.

Run: `python3 optimize.py`

### Phase 2: Structural improvements (LLM agent)
The LLM agent reads this file, modifies backtest.py, proposes **new features**:
- Source-specific thresholds (not global)
- Time-of-week weighting (weekday vs weekend patterns)
- Exponential decay for older signals
- Conditional logic (if GPS jamming HIGH, weight ADS-B more)
- Cross-source correlation scoring

This is where LLM reasoning helps — hypothesis generation, not number tuning.

Run: `./run.sh` (uses local Ollama or any LLM agent)

## Current best parameters (from Phase 1)

```
YELLOW threshold: 15.2
ORANGE threshold: 59.7
RED threshold:    92.8
Momentum:         0.034
Trend multiplier: 0.927
Window:           7 days

eval_score: 0.8850 (accuracy: 91.7%, stability: 88.9%, lead_time: 80.0%)
```

## Metrics

- **prediction_accuracy** (50% weight): did the predicted level match the actual?
- **stability** (30% weight): fewer false transitions between levels
- **lead_time** (20% weight): predicted tomorrow's level change today

## Constraints for Phase 2

- Only modify `backtest.py` — NOT `prepare.py` or `optimize.py`
- Each experiment must complete in < 5 seconds
- Commit only if eval_score improves ≥ 0.5%
- Log reasoning to experiments.log
