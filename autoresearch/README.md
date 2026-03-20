# CTI Autoresearch

Automated research loop for optimizing the EstWarden Composite Threat Index, inspired by [Karpathy's autoresearch pattern](https://github.com/karpathy/autoresearch).

## How it works

```
program.md (goals + constraints)
     ↓
AI agent reads instructions
     ↓
Modifies backtest.py (weights, thresholds)
     ↓
Runs experiment (backtest against real API data)
     ↓
Measures eval_score (accuracy + stability + lead_time)
     ↓
If improved ≥ 0.5% → commit. Else revert.
     ↓
Loop
```

## Files

| File | Editable? | Purpose |
|------|-----------|---------|
| `program.md` | By humans | Research goals, constraints, what to try |
| `backtest.py` | By agent | Weights, thresholds, scoring logic |
| `prepare.py` | LOCKED | Data fetching + evaluation (ensures honest scoring) |
| `run.sh` | No | Loop orchestrator |

## Run manually

```bash
# 1. Fetch baseline data
python3 prepare.py

# 2. Run backtest with current weights
python3 backtest.py

# 3. Edit weights in backtest.py, re-run, compare scores

# 4. Or run the full loop (plug in your LLM agent)
./run.sh
```

## Run with AI agent

```bash
# Using Claude Code / pi
pi -p "Read autoresearch/program.md. Your job: optimize backtest.py weights 
to maximize eval_score. Run python3 autoresearch/backtest.py after each change. 
Commit improvements. Do 20 iterations."

# Using any MCP-compatible agent
# Point the agent at program.md and let it iterate
```

## What gets optimized

- Source weights (GPS jamming, ADS-B, ACLED, FIRMS, etc.)
- Z-score thresholds for anomaly detection
- Baseline window size (7 vs 14 vs 30 days)
- Scoring formula modifications

All experiments run against real historical data from the public EstWarden API.
