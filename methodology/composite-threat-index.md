# Composite Threat Index (CTI)

A 0–100 score fusing multiple OSINT signal sources into a single threat assessment for the Baltic region.

## Formula

```
CTI(t) = (1 - α) × raw(t) + α × CTI(t-1)

raw(t) = Σ (wᵢ × zᵢ_norm) / Σ wᵢ  +  β × trend(t)
```

Where:
- `α = 0.034` — momentum (minimal smoothing, react fast)
- `β = 0.927` — trend multiplier (trust the direction)
- `zᵢ = (current_24h - mean_7d) / max(stddev_7d, 1)` — per-source z-score
- `zᵢ_norm = min(z × 10, 100)` — normalized to 0–100
- `trend(t) = score(t) - score(t - window)` — score direction over 7 days

## Source Weights

| Source | Weight | Rationale |
|--------|--------|-----------|
| GPS jamming | 20 | Direct EW indicator, high signal-to-noise |
| ADS-B military flights | 15 | Observable force posture |
| Conflict events (ACLED) | 15 | Ground truth kinetic activity |
| Thermal anomalies (FIRMS) | 15 | Military base activity proxy |
| AIS naval vessels | 10 | Maritime posture, shadow fleet |
| Telegram/social signals | 10 | Information operations volume |
| RSS media | 5 | Narrative temperature |
| GDELT military news | 5 | Global attention proxy |
| Internet outages (IODA) | 5 | Infrastructure disruption |

Total: 100

## Threat Levels (research-calibrated, March 2026)

| Level | Score | Interpretation |
|-------|-------|----------------|
| 🟢 GREEN | 0 – 15.1 | Normal baseline. No elevated indicators. |
| 🟡 YELLOW | 15.2 – 59.6 | Elevated activity in 1+ domains. Active monitoring. |
| 🟠 ORANGE | 59.7 – 92.7 | Significant multi-domain activity. Concern. |
| 🔴 RED | 92.8 – 100 | Critical activity across multiple domains. |

**Why these thresholds:** Production CTI scores range 0–30 in normal conditions.
The lower YELLOW threshold (15.2 vs the naive 25) catches real elevations earlier.
ORANGE and RED are intentionally high — they should fire only during genuine crises.
See [FINDINGS.md](FINDINGS.md) for the optimization methodology.

## Anomaly Detection

Per-source anomalies use z-score thresholds:
- **z ≥ 2.0**: INFO — notable deviation
- **z ≥ 3.0**: WARNING — significant spike or drop
- **z ≥ 4.0**: ALERT — extreme anomaly

Both positive (spike) and negative (silence) anomalies are tracked.
A collector going silent is as concerning as a volume spike.

## Narrative Classification

Information operations are classified into five Baltic-targeted categories:

| Code | Narrative | Description |
|------|-----------|-------------|
| N1 | Russophobia / Persecution | "Estonia persecutes Russian speakers" |
| N2 | War Escalation Panic | "Baltic politicians dragging civilians into war" |
| N3 | Aid = Theft | "Ukraine support wastes taxpayer money" |
| N4 | Delegitimization | "EU/Estonian leaders corrupt/incompetent" |
| N5 | Isolation / Victimhood | "Nobody listens to the Russian community" |

Classification uses LLM with confidence threshold ≥ 0.70.
Geographic scope: only signals targeting Estonia, Latvia, Lithuania, or the Baltic region.

## Campaign Detection

Four detection methods:
1. **Single-source blitz** — one actor, many signals in short time
2. **Multi-source coordination** — same narrative across platforms within 48h
3. **Narrative spike** — volume anomaly against 30-day baseline (z ≥ 3.0)
4. **Cross-platform amplification** — correlated timing across RSS, Telegram, YouTube

## Milbase Fusion

Military base activity level (0.0–1.0) per monitored site:

| Source | Weight |
|--------|--------|
| Satellite imagery (Sentinel-2 + Gemini) | 30 |
| Perplexity OSINT research | 25 |
| FIRMS thermal anomalies | 15 |
| GDELT military news | 15 |
| ACLED conflict events | 10 |
| Milwatch RSS feeds | 5 |

Updated every 4 hours.

## Validation

The CTI parameters were optimized using brute-force search across 85,000 parameter
combinations, evaluated on 31 days of production data with 12 GREEN↔YELLOW transitions.

3-fold cross-validation (10-day folds) confirms robustness:
- Fold variance < 5% (no single fold dominates the result)
- Parameters stable across folds

See [FINDINGS.md](FINDINGS.md) and [autoresearch/](../autoresearch/) for reproducibility.
