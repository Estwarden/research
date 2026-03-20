#!/bin/bash
# run.sh — Autoresearch loop for CTI optimization.
# Spawns an AI agent to iteratively improve backtest.py.
#
# Usage:
#   ./run.sh                     # uses Claude Code (pi)
#   ./run.sh --iterations 20     # limit iterations
#
# The agent reads program.md, modifies backtest.py, runs it, and commits
# improvements. All experiments logged to experiments.log.
set -euo pipefail

cd "$(dirname "$0")"
MAX_ITER="${2:-50}"
LOG="experiments.log"
BEST_SCORE=0

echo "EstWarden CTI Autoresearch"
echo "Max iterations: $MAX_ITER"
echo ""

# Compute baseline
echo "=== Baseline ===" | tee -a "$LOG"
python3 backtest.py 2>&1 | tee -a "$LOG"
BEST_SCORE=$(python3 backtest.py 2>/dev/null | grep "eval_score" | grep -oP '[0-9.]+')
echo "Baseline score: $BEST_SCORE" | tee -a "$LOG"
echo "" >> "$LOG"

for i in $(seq 1 "$MAX_ITER"); do
    echo "=== Iteration $i ===" | tee -a "$LOG"
    
    # Agent proposes a change (this is where you plug in your LLM agent)
    # For manual use: edit backtest.py, then run this script
    # For automated use: pipe program.md + backtest.py to an LLM API
    
    NEW_SCORE=$(python3 backtest.py 2>/dev/null | grep "eval_score" | grep -oP '[0-9.]+' || echo "0")
    
    IMPROVED=$(python3 -c "print('yes' if $NEW_SCORE > $BEST_SCORE * 1.005 else 'no')")
    
    if [ "$IMPROVED" = "yes" ]; then
        echo "  ✓ Improved: $BEST_SCORE → $NEW_SCORE" | tee -a "$LOG"
        BEST_SCORE="$NEW_SCORE"
        git add backtest.py 2>/dev/null
        git commit -m "autoresearch: iteration $i (score: $NEW_SCORE)" 2>/dev/null || true
    else
        echo "  ✗ No improvement ($NEW_SCORE vs $BEST_SCORE)" | tee -a "$LOG"
        git checkout -- backtest.py 2>/dev/null || true
    fi
    
    echo "" >> "$LOG"
done

echo ""
echo "Best score: $BEST_SCORE"
echo "Experiments logged to: $LOG"
