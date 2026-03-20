# EstWarden CTI Autoresearch

You are an automated research agent optimizing the Composite Threat Index (CTI)
for the EstWarden Baltic Security Monitor.

## Goal

Minimize prediction error of the CTI by optimizing source weights and
detection thresholds against historical data from the public API.

## Constraints

- Each experiment: fetch data from `https://estwarden.eu/api/`, run backtest, measure score
- Experiments must complete in under 60 seconds
- Only modify `weights` and `thresholds` in `backtest.py` — do NOT modify `prepare.py` or `evaluate.py`
- Weights must sum to 100, each weight between 0 and 40
- Z-score thresholds must be between 1.5 and 5.0
- Commit improvements only if `eval_score` improves by ≥ 0.5%

## Metrics

Primary: **prediction_accuracy** — how well the CTI score predicted next-day threat level changes
Secondary: **stability** — lower daily volatility is better (fewer false transitions)
Tertiary: **lead_time** — earlier detection of level changes scores higher

## Current Baseline

```
weights = {
    "gpsjam": 20, "adsb": 15, "acled": 15, "firms": 15,
    "ais": 10, "telegram": 10, "rss": 5, "gdelt": 5, "ioda": 5,
}
thresholds = {
    "info": 2.0, "warning": 3.0, "alert": 4.0,
}
baseline_window_days = 7
```

Baseline eval_score: (run prepare.py to compute)

## What to try

- Rebalance weights based on source signal-to-noise ratio
- Test 14-day vs 7-day baseline windows
- Adjust z-score thresholds for different source types
- Add momentum (rate-of-change) as a scoring factor
- Test exponential weighted moving average instead of simple mean
- Source-specific thresholds instead of global ones

## Evaluation

After each change:
1. Run `python3 backtest.py`
2. Compare `eval_score` to previous best
3. If improved ≥ 0.5%, commit with message: `autoresearch: <what changed> (score: X.XX → Y.YY)`
4. If not improved, revert and try something different
5. Log all experiments to `experiments.log`
