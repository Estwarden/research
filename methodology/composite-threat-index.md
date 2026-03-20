# Composite Threat Index (CTI)

A 0–100 score fusing multiple OSINT signal sources into a single threat assessment for the Baltic region.

## Formula

```
CTI = Σ (weight_i × normalized_zscore_i) / Σ weight_i
```

Where:
- Each source type has a 7-day rolling baseline (mean, stddev)
- Z-score = (current_24h - mean_7d) / max(stddev_7d, 1)
- Normalized to 0–100 via min(z × 10, 100)

## Source Weights

| Source | Weight | Rationale |
|--------|--------|-----------|
| GPS jamming | 20% | Direct EW indicator, high signal-to-noise |
| ADS-B military flights | 15% | Observable force posture |
| Conflict events (ACLED) | 15% | Ground truth kinetic activity |
| Thermal anomalies (FIRMS) | 15% | Base activity proxy |
| AIS naval vessels | 10% | Maritime posture, shadow fleet |
| Telegram/social signals | 10% | Information operations volume |
| RSS media | 5% | Narrative temperature |
| GDELT military news | 5% | Global attention proxy |
| Internet outages (IODA) | 5% | Infrastructure disruption |

## Threat Levels

| Level | Score | Interpretation |
|-------|-------|----------------|
| 🟢 GREEN | 0–24 | Normal baseline. No elevated indicators. |
| 🟡 YELLOW | 25–49 | Elevated activity in 1-2 domains. Monitoring. |
| 🟠 ORANGE | 50–74 | Significant multi-domain activity. Concern. |
| 🔴 RED | 75–100 | Critical activity across multiple domains. |

## Anomaly Detection

Per-source anomalies use z-score thresholds:
- **z ≥ 2.0**: INFO — notable deviation
- **z ≥ 3.0**: WARNING — significant spike or drop
- **z ≥ 4.0**: ALERT — extreme anomaly

Both positive (spike) and negative (drop/silence) anomalies are tracked. A collector going silent is as concerning as a volume spike.

## Calibration

The weighting was determined by:
1. Historical correlation with known threat periods
2. Signal-to-noise ratio per source
3. Lead time (how early the source signals before events)
4. Resistance to manipulation (harder to fake = higher weight)

Weights should be recalibrated quarterly using backtesting against known events.

## Narrative Classification

Information operations are classified into five Baltic-targeted categories:

| Code | Narrative | Description |
|------|-----------|-------------|
| N1 | Russophobia / Persecution | "Estonia persecutes Russian speakers" |
| N2 | War Escalation Panic | "Baltic politicians dragging civilians into war" |
| N3 | Aid = Theft | "Ukraine support wastes taxpayer money" |
| N4 | Delegitimization | "EU/Estonian leaders corrupt/incompetent" |
| N5 | Isolation / Victimhood | "Nobody listens to the Russian community" |

Classification uses LLM with confidence threshold ≥ 0.70. Geographic scope filter: only signals targeting Estonia, Latvia, Lithuania, or the Baltic region.

## Campaign Detection

Four detection methods:
1. **Single-source blitz** — one actor, many signals in short time
2. **Multi-source coordination** — same narrative across platforms
3. **Narrative spike** — volume anomaly against 30-day baseline (z ≥ 3.0)
4. **Cross-platform amplification** — correlated timing across RSS, Telegram, YouTube

Campaigns get human-readable names, not codes.

## Milbase Fusion

Military base activity level is a weighted average of 6 source types:

| Source | Weight |
|--------|--------|
| Satellite imagery analysis | 30% |
| Perplexity OSINT research | 25% |
| FIRMS thermal anomalies | 15% |
| GDELT military news | 15% |
| ACLED conflict events | 10% |
| Milwatch RSS feeds | 5% |

Result: 0.0–1.0 activity level per monitored site, cached and updated every 4 hours.

## Optimization Results (March 2026)

### Phase 1: Parameter search (85,000 trials)

Optimal parameters on 31 days of production data:

```
YELLOW threshold: 15.2
ORANGE threshold: 59.7
RED threshold:    92.8
Momentum:         0.034 (minimal smoothing)
Trend multiplier: 0.927 (trust the trend)
Window:           7 days

eval_score: 0.8708
  Accuracy:   87.5%
  Stability:  88.9%
  Lead time:  83.3%
```

### Phase 2: Structural improvements (5 iterations, Claude Sonnet)

All structural changes tested and rejected:
- Exponential moving average → worse (0.7167)
- Asymmetric momentum → worse (0.7297)
- Rate-of-change scoring → worse (0.6958)
- Volatility penalty → worse (0.6958)
- Regime detection → worse (0.6958)

**Conclusion:** With 31 days of data and 12 level transitions, the simple linear
model (mean + trend × weight) is near-optimal. Structural improvements require
6+ months of data with diverse threat scenarios. The parameter-optimized model
should be re-evaluated quarterly as more data accumulates.
