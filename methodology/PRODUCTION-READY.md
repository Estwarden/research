# Production-Ready Changes from Research

## Validated and ready to implement

### 1. Fisher Pre-Screen (Experiment 25, F1=0.92 → 1.00 with LLM fallback)
```
score = 0.670 × state_ratio_normalized + 0.742 × fimi_score_normalized

if score > 0.5:  auto-flag hostile (skip LLM)
if score < -0.7: auto-skip clean (skip LLM)  
else:            run LLM framing analysis
```
LLM calls reduced 77%. F1 maintained at 1.00.

### 2. Narrative Velocity Alert (Experiment 29)
```
velocity = (state_ratio_this_week - state_ratio_last_week) / max(state_ratio_last_week, 0.05)

if velocity > 1.0 AND state_ratio_this_week > 0.3:
    alert: "narrative being weaponized"
```
Catches the W10→W11→W12 escalation pattern (0%→10%→59%).

### 3. OSINT Early Warning Integration (Experiment 29)
Track osint_perplexity signals mentioning new channels/groups.
If a topic detected by OSINT later appears in mainstream media with rising
state_ratio → confirm as emerging info op.
39-day lead time demonstrated on Narva Republic.

### 4. Baltic Entity Filter Without NATO (Experiment 13, 18)
Remove `nato|нато` from Baltic filter — too broad, causes Russian domestic FPs.
Already applied. Documented for reference.

### 5. Cluster Size Cap at 15 (Experiment 12)
Already applied. Documented for reference.

### 6. Cosine Threshold 0.75 (Experiment 6)
Already applied. Documented for reference.

## Not ready — needs more data

### Self-Tuning Thresholds
Need 50+ labeled outcomes from detection_outcomes table.
Current: 13 framing analyses labeled. Need ~4 months at current rate.

### Propagation Shape Features
Temporal entropy and CV show trends (experiment 19) but p>0.3 at N=13.
Need N=50+ to validate. Supplementary signal, not primary detector.
