# EstWarden Research

Mathematical methodology behind the [EstWarden](https://estwarden.eu) Composite Threat Index — how we score, weight, and aggregate open-source intelligence into a single Baltic security threat number.

## Contents

- **[Composite Threat Index](methodology/composite-threat-index.md)** — scoring formula, source weights, threat levels, anomaly detection, calibration
- **[Notebooks](notebooks/)** — Jupyter notebooks for backtesting and model development (coming soon)

## Quick Reference

```
CTI = Σ (weight × normalized_zscore) / total_weight

GREEN  (0-24)   Normal
YELLOW (25-49)  Elevated
ORANGE (50-74)  Significant
RED    (75-100) Critical
```

## Contributing

- Better weighting models with evidence
- Backtesting notebooks against historical events
- New anomaly detection approaches
- Country-specific narrative taxonomy proposals

## License

MIT
