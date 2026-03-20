# Research Findings — March 2026

## Key Results

### 1. Lower YELLOW threshold catches threats earlier
**Old:** GREEN < 25, YELLOW < 50
**New:** GREEN < 15.2, YELLOW < 59.7

The production CTI scores range 0–30 in normal conditions. The old threshold (25) was too high — the system stayed GREEN even when multiple sources showed elevated activity. Lowering to 15.2 detects YELLOW conditions 3.3% more accurately.

### 2. Trust the trend, don't smooth
**Momentum: 0.034** (almost zero — previous day's prediction barely matters)
**Trend weight: 0.927** (if scores are rising, the model follows immediately)

The old system smoothed predictions to avoid oscillation. Research shows this HURTS performance — the system should react immediately to rising threat indicators. False YELLOWs are less costly than missing a real escalation.

### 3. Simple model beats complex ones (with limited data)
Tested 5 structural improvements (EMA, asymmetric momentum, regime detection, rate-of-change, volatility penalty). All performed worse than the simple mean + trend model on 31 days of data.

**Why:** Complex models need diverse training data (6+ months with multiple GREEN↔YELLOW↔ORANGE transitions). With only 12 transitions in 31 days, added complexity overfits.

### 4. The dataset is dominated by routine data
90% of signals are AIS vessel positions (routine maritime traffic). For CTI calibration, the signal VOLUME per source matters more than total count. GPS jamming (20% weight) has the highest signal-to-noise ratio for threat detection.

## Applied Changes

| What | Where | Change |
|------|-------|--------|
| CTI thresholds | Dagu threat-index DAG | GREEN<15.2, YELLOW<59.7, ORANGE<92.8 |
| Methodology page | estwarden.eu/guide/methodology | Updated threshold visualization |
| Source weights | Collectors repo | GPS jamming 20%, ADS-B 15%, ACLED 15% |

## Next Steps (when data accumulates)

- **At 90 days:** Re-run Phase 1 optimizer, validate thresholds still hold
- **At 180 days:** Run Phase 2 structural improvements (EMA, regime detection may help with more transitions)
- **At 365 days:** Publish updated dataset, full backtesting paper

## Reproducibility

```bash
git clone https://github.com/Estwarden/research.git
git clone https://github.com/Estwarden/dataset.git data
cd research/autoresearch
pip install numpy
python3 optimize.py  # reproduces the 0.8708 result
```

## Multi-Region Impact (March 2026)

### Architecture change
CTI is now computed per-region (baltic, finland, poland) with the same formula
but filtering signals by geographic region. Each brand (estwarden, latwarden,
litwarden, finwarden, polwarden, balticwarden) maps to a CTI region.

### Score distributions differ by region

| Region | Avg Score | YELLOW days | Notes |
|--------|-----------|-------------|-------|
| Baltic | 12.7 | 16/45 (36%) | Research-optimized (threshold=15.2 is good) |
| Finland | 16.0 | 20/31 (65%) | Consistently higher — threshold may be too low |
| Poland | 17.0 | 22/31 (71%) | Almost always YELLOW — threshold definitely too low |

### Problem: uniform thresholds don't work across regions

The 15.2 YELLOW threshold was optimized on Baltic data where scores range 4.5–21.5.
Finland (8.7–21.6) and Poland (10.4–22.0) have higher baselines, so they're YELLOW
most of the time. This is a **false positive problem** — the threshold needs
per-region calibration.

### Action items
1. **Re-export dataset WITH region column** — current dataset has no region tags
2. **Run Phase 1 optimizer per-region** — find optimal thresholds for each
3. **Source weights may differ by region** — Finnish media (RSS) may be more/less
   predictive than Estonian media for Finnish threat levels
4. **Add per-region notebooks** — notebook 02 (lead indicators) should run once
   per region to find region-specific predictors
5. **Consider region-specific source weights** — GPS jamming near Kaliningrad
   may be more relevant for Lithuania than Finland

### Interim fix
Until per-region thresholds are researched, the YELLOW threshold for Finland
and Poland should be raised to ~18-20 to avoid permanent YELLOW status.
