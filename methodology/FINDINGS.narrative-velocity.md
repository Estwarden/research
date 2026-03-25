# FINDINGS: Narrative Velocity Metric — Weaponization Detection

**Date**: 2026-03-25
**Notebook**: `27_narrative_velocity.py`
**Dataset**: 849,914 signals over 90 days (2026-W01 to 2026-W13)
**Text signals analyzed**: 42,712 (excluding AIS/ADS-B/sensors)
**Signals with narrative tags**: 1,835 (4.3%)

## Background

Experiment 29 discovered the **weaponization escalation signature**: state media
gradually takes over coverage of a narrative, with `state_ratio` rising from
0% → 10% → 59% over 3 weeks on `russian_speakers_oppressed`. This is the pattern
where an organic narrative gets co-opted by state media, which adds hostile framing.

This notebook implements and validates the **narrative velocity metric** as a
production-ready alert formula.

## Method

### Narrative Classification
Signals are classified into 8 narrative themes using
keyword matching against title + content (lowercased). Keywords cover both
Russian and English terms.

**Hostile narratives** (expected to trigger alerts):
- `russian_speakers_oppressed` — N1: Russophobia/Persecution claims
- `baltic_failed_states` — N3: Economic failure narrative
- `nato_weakness` — N2: NATO dissolution/weakness
- `separatism_fear` — N5: Narva Republic, separatism
- `western_fatigue` — Western support erosion

**Organic controls** (should NOT trigger):
- `rail_baltica` — Infrastructure news
- `military_exercise` — Routine defense activity
- `airspace_violation` — Isolated security events

### Source Classification
Signals classified as `state` (ru_state, russian_state, pro_kremlin, ru_proxy +
known channels/handles), `trusted` (Baltic/Nordic/independent media), or `other`.

### Velocity Formula

```
state_ratio(week) = state_signals / total_signals  (per narrative, per ISO week)
velocity(week)    = state_ratio(week) - state_ratio(week - 1)

ALERT when:
  velocity > 0.15
  AND state_ratio > 0.30
  AND total_signals >= 3
```

## Results

### Narratives Detected

| Narrative | Signals | Weeks Active | Avg SR | Max SR | Expected |
|-----------|---------|-------------|--------|--------|----------|
| airspace_violation | 372 | 5 | 0.76 | 0.83 | organic |
| baltic_failed_states | 370 | 8 | 0.37 | 0.67 | hostile |
| military_exercise | 38 | 4 | 0.21 | 0.67 | organic |
| nato_weakness | 149 | 8 | 0.40 | 0.67 | hostile |
| rail_baltica | 44 | 4 | 0.00 | 0.00 | organic |
| russian_speakers_oppressed | 366 | 6 | 0.43 | 0.69 | hostile |
| separatism_fear | 456 | 9 | 0.43 | 0.55 | hostile |
| western_fatigue | 151 | 9 | 0.41 | 0.65 | hostile |

### Alerts Triggered

| Narrative | Week | Velocity | State Ratio | Signals | Expected |
|-----------|------|----------|-------------|---------|----------|
| western_fatigue | 2026-W10 | +0.562 | 0.562 | 16 | hostile |
| separatism_fear | 2026-W10 | +0.548 | 0.548 | 42 | hostile |
| baltic_failed_states | 2026-W13 | +0.339 | 0.673 | 55 | hostile |
| western_fatigue | 2026-W13 | +0.314 | 0.652 | 23 | hostile |
| nato_weakness | 2026-W12 | +0.256 | 0.416 | 77 | hostile |
| nato_weakness | 2026-W13 | +0.251 | 0.667 | 24 | hostile |
| russian_speakers_oppressed | 2026-W12 | +0.239 | 0.451 | 195 | hostile |
| russian_speakers_oppressed | 2026-W13 | +0.238 | 0.690 | 58 | hostile |

### Validation Against Labeled Events

| Metric | Value |
|--------|-------|
| True Positives | 5 |
| False Positives | 0 |
| False Negatives | 0 |
| True Negatives | 3 |
| **Precision** | **1.00** |
| **Recall** | **1.00** |
| **F1** | **1.00** |
| **Accuracy** | **1.00** |

### Optimal Thresholds

Best F1 = 1.00 achieved across a wide stable range:
- velocity_threshold: 0.10 — 0.20 (all give F1=1.00 when state_ratio ≥ 0.25)
- state_ratio_threshold: 0.25 — 0.50 (all give F1=1.00 when velocity ≥ 0.10)

> **⚠️ Statistical caveat:** F1=1.00 on N=8 (5 hostile, 3 organic) is **statistically
> meaningless**. ANY 2-parameter model with reasonable parameters achieves F1≥0.83 on
> this dataset. The wide stable range is expected with 8 data points, not evidence
> against overfitting. Need 30+ labeled narratives before setting production thresholds.
> See [VALIDITY.md](VALIDITY.md).

**Do NOT deploy these thresholds.** The weaponization PATTERN (0%→10%→59%) is
real and documented. The specific numbers (0.15, 0.30) are not validated.

## Production Alert Formula

```go
// Narrative Velocity Alert
// Run weekly per narrative tag
func CheckNarrativeVelocity(narrative string, currentWeek, prevWeek WeekStats) Alert {
    if currentWeek.TotalSignals < 3 {
        return nil  // insufficient data
    }
    
    currentSR := float64(currentWeek.StateSignals) / float64(currentWeek.TotalSignals)
    prevSR := float64(prevWeek.StateSignals) / float64(prevWeek.TotalSignals)
    velocity := currentSR - prevSR
    
    if velocity > 0.15 && currentSR > 0.30 {
        return Alert{
            Type:       "NARRATIVE_WEAPONIZATION",
            Narrative:  narrative,
            Velocity:   velocity,
            StateRatio: currentSR,
            Severity:   classifySeverity(velocity, currentSR),
        }
    }
    return nil
}

// Severity classification
func classifySeverity(velocity, stateRatio float64) string {
    if velocity > 0.30 && stateRatio > 0.50 {
        return "HIGH"   // rapid takeover
    }
    if velocity > 0.20 && stateRatio > 0.40 {
        return "MEDIUM" // escalating
    }
    return "LOW"        // initial signal
}
```

## Relationship to Existing Detection

The narrative velocity metric operates at a DIFFERENT level than existing detectors:

| Detector | Level | Timescale | What it catches |
|----------|-------|-----------|-----------------|
| Outrage chain | Single event | 8-24h | Manufactured reaction cascade |
| Framing analysis | Single event | 6-48h | Hostile vs truthful coverage |
| Injection cascade | Single event | 3-13 days | Organic→amplified propagation |
| **Narrative velocity** | **Strategic theme** | **Weeks** | **State media takeover of topic** |

The velocity metric is COMPLEMENTARY — it catches the slow, strategic weaponization
that event-level detectors miss because no single event triggers an alert.

## Limitations

1. **Keyword-based classification**: Narrative tagging via keywords may miss
   signals using novel framing or metaphorical language. Embedding-based
   narrative clustering (future work) would be more robust.

2. **Small validation set**: Only 8 labeled
   narratives (5 hostile + 3 organic). Need more labeled examples for
   statistical significance.

3. **Lag**: Weekly aggregation means the earliest possible alert is 1 week
   after weaponization begins. For faster detection, could use rolling
   3-day windows instead of ISO weeks.

4. **Threshold sensitivity**: The optimal thresholds depend on the narrative
   keyword quality and source classification accuracy. Production deployment
   should include a monitoring dashboard for threshold tuning.

## References

- Experiment 27: Narrative persistence over 3 weeks (FINDINGS.md)
- Experiment 29: Escalation signature 0%→10%→59% (FINDINGS.md)
- Experiment 8: Injection cascade scoring, 7 labeled events (FINDINGS.campaign-detection.md)
- Experiment 18: state_ratio as key predictor, r=+0.604, p=0.029 (FINDINGS.campaign-detection.md)
