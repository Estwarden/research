# Research Findings: CCDC Time Series Segmentation for Military Sites

**Experiment 22** | 2026-03-25 | 3 sites × CCDC analysis
**Dataset**: Sentinel-2 SR Harmonized via Google Earth Engine, 2023-01-01 to 2026-03-25
**Sites**: Pskov-76VDV (airborne), Luga (garrison), Kronstadt (naval)

---

## Method

CCDC (Continuous Change Detection and Classification; Zhu & Woodcock 2014) fits a harmonic
regression model to each pixel's spectral time series and detects breakpoints when observations
deviate beyond a chi-squared threshold. Runs server-side in GEE.

### Parameters

| Parameter | Value |
|-----------|-------|
| Bands | B4, B8, B11, B12 (Red, NIR, SWIR1, SWIR2) |
| chiSquareProbability | 0.95 |
| minObservations | 6 |
| lambda | 20.0 |
| scale | 20m |
| cloud filter | SCL + <30% |

### Breakpoint Classification

```
vegetation_loss:  NIR↓ + SWIR1↑    → clearing, construction
vegetation_gain:  NIR↑ + SWIR1↓    → regrowth, abandonment
BSI_increase:     (SWIR1+Red)↑-NIR↑ → earthwork, bare soil
metal_increase:   NIR↑ + SWIR1↑    → metallic equipment/structures
snow_transition:  large SWIR Δ     → seasonal snow change
```

---

## Results

### Summary

| Metric | Value |
|--------|-------|
| Sites processed | 3 |
| Pskov-76VDV images | 101 |
| Luga images | 177 |
| Kronstadt images | 187 |
| Total breakpoints | 6 |
| Zonal (quadrant-level) | 4 |
| Point (pixel-level) | 2 |
| ISW event matches (±90d) | 1 |

### Pskov-76VDV (76th Guards Air Assault Division airfield)

| Date | Location | Class | Confidence | Explanation |
|------|----------|-------|:----------:|-------------|
| 2025-12-21 | SW | negligible_change | 0.10 | All magnitudes < 200 |
| 2025-12-26 | NW | vegetation_loss | 0.60 | NIR down(-302) = vegetation removal |
| 2025-12-29 | SE | vegetation_loss | 0.60 | NIR down(-211) = vegetation removal |

### Luga (Luga training ground and garrison)

| Date | Location | Class | Confidence | Explanation |
|------|----------|-------|:----------:|-------------|
| 2023-05-11 | NE | vegetation_loss | 0.80 | NIR down(-486) + SWIR1 up(323) = clearing |
| 2025-02-26 | SW | negligible_change | 0.10 | All magnitudes < 200 |
| 2025-09-29 | NE | vegetation_loss | 0.60 | NIR down(-379) = vegetation removal |

### Kronstadt (Kronstadt naval base — Baltic Fleet)

No breakpoints detected at this site.

### Breakpoint Density by Quadrant

| Site | Quad | Total Px | Px w/ Break | Density |
|------|------|:--------:|:-----------:|:-------:|
| Pskov-76VDV | NW | 4845 | 1073 | 22.1% |
| Pskov-76VDV | NE | 4845 | 1164 | 24.0% |
| Pskov-76VDV | SW | 4845 | 738 | 15.2% |
| Pskov-76VDV | SE | 4845 | 1000 | 20.6% |
| Luga | NW | 4998 | 1383 | 27.7% |
| Luga | NE | 4947 | 1840 | 37.2% |
| Luga | SW | 4998 | 1791 | 35.8% |
| Luga | SE | 4947 | 1127 | 22.8% |
| Kronstadt | NW | 5151 | 1411 | 27.4% |
| Kronstadt | NE | 5202 | 1360 | 26.1% |
| Kronstadt | SW | 5151 | 1374 | 26.7% |
| Kronstadt | SE | 5202 | 1178 | 22.6% |

### Classification Distribution

| Class | Count | Description |
|-------|:-----:|-------------|
| vegetation_loss | 4 | Clearing, construction, ground disturbance |
| negligible_change | 2 | Below significance threshold |

### Event Cross-Reference

| Event | Date | Nearest Break | Δ Days | Class |
|-------|------|:------------:|:------:|-------|
| 76th VDV deployed to Ukraine (ongoing) | 2022-09-01 | — | — | — |
| 76th VDV heavy losses at Vuhledar | 2023-06-01 | — | — | — |
| 76th VDV redeployed to Zaporizhia/Orikhiv | 2024-06-01 | — | — | — |
| 26th Rocket Bde Iskander to Ukraine | 2025-10-01 | 2025-09-29 | -2 | vegetation_loss |
| 68th MR Div to Kupyansk | 2024-01-01 | — | — | — |
| Baltic Fleet — 11th AC to Ukraine | 2023-01-01 | — | — | — |
| 11th AC 1431st+352nd MRRs at Kupyansk | 2025-03-01 | — | — | — |

---

## Conclusions

### What CCDC Detects at 20m Resolution

1. **Landscape-level infrastructure changes**: Construction, clearing,
   paving — persistent spectral shifts the harmonic model cannot explain.
2. **Seasonal pattern disruption**: If a site's vegetation cycle changes,
   CCDC detects this as a breakpoint.
3. **Multi-band regime changes**: Changes across NIR + SWIR bands are
   more likely real than single-band artifacts.

### What CCDC Cannot Detect

1. **Individual vehicle movements**: Sub-pixel at 20m.
2. **Short exercises (<2 weeks)**: Insufficient observations.
3. **Camouflaged activity**: Surface-only detection.

### Complementarity with NB 20/21

| Approach | NB 20 | NB 21 | NB 22 |
|----------|-------|-------|-------|
| Method | Seasonal z-score | IsolationForest | CCDC harmonic breaks |
| Detects | Deviations from season | Spectral outliers | Regime changes |
| Time scale | Days-weeks | Point-in-time | Months-years |

### Production Recommendation

1. Run CCDC annually on full S2 archive per monitored site.
2. Cross-reference new breakpoints with OSINT/SIGINT.
3. Use density maps to prioritize quadrants for monitoring.
4. Two-level alert: NB 20 for transient, NB 22 for permanent changes.

---

## References

1. Zhu, Z. & Woodcock, C.E. (2014). "Continuous change detection and classification
   of land surface using all available Landsat data." *Remote Sensing of Environment*, 144, 152-171.
2. GEE: `ee.Algorithms.TemporalSegmentation.Ccdc`

*Experiment code: `notebooks/22_ccdc_breakpoints.py`*
