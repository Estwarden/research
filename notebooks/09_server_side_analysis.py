#!/usr/bin/env python3
"""
Experiments 09-15: Server-Side Analysis & Historical Baselines

Results from Google Earth Engine server-side computation + local ML.

EXP 09: Linear regression NDVI trend (3 years)
EXP 10: Temporal variability (NDVI + BSI stdDev)
EXP 11: Seasonal decomposition (winter vs summer)
EXP 12: Full zonal statistics with 30-day and 1-year deltas
EXP 13: Spectral change magnitude (bitemporal Euclidean distance)
EXP 14: Year-over-year March comparison (2024 vs 2025 vs 2026)
EXP 15: Isolation Forest anomaly detection on multispectral data

All GEE experiments run server-side — only final numbers downloaded.
"""

# Results from server-side experiments (run on 89.167.126.145)

exp09_trend = {
    "Chkalovsk": {"slope_per_yr": 3.279, "r": -0.282, "n_images": 108},
    "Kronstadt":  {"slope_per_yr": -1.367, "r": -0.076, "n_images": 187},
    "Pskov":      {"slope_per_yr": 3.279, "r": -0.067, "n_images": 101},
}

exp10_variability = {
    "Chkalovsk": {"ndvi_std": 0.2556, "bsi_std": 0.1618},
    "Kronstadt":  {"ndvi_std": 0.2004, "bsi_std": 0.1905},
    "Pskov":      {"ndvi_std": 0.2398, "bsi_std": 0.1444},
}

exp11_seasonal = {
    "Chkalovsk": {"summer_ndvi": 0.733, "winter_ndvi": 0.187, "current_ndvi": 0.155, "delta": -0.032},
    "Kronstadt":  {"summer_ndvi": 0.001, "winter_ndvi": 0.000, "current_ndvi": -0.109, "delta": -0.110},
    "Pskov":      {"summer_ndvi": 0.700, "winter_ndvi": 0.167, "current_ndvi": 0.400, "delta": +0.234},
}

exp12_zonal = {
    "Chkalovsk": {"ndvi": 0.286, "ndbi": 0.119, "bsi": 0.150, "fuel_pct": 4.3, "metal_pct": 0.2,
                  "d30_ndvi": +0.229, "d30_ndbi": +0.625, "d30_bsi": +0.341,
                  "d1y_ndvi": -0.008, "d1y_ndbi": -0.016, "d1y_bsi": +0.003},
    "Kronstadt":  {"ndvi": -0.120, "ndbi": -0.524, "bsi": -0.100, "fuel_pct": 2.5, "metal_pct": 1.5,
                   "d30_ndvi": -0.131, "d30_ndbi": +0.239, "d30_bsi": +0.189,
                   "d1y_ndvi": -0.018, "d1y_ndbi": -0.154, "d1y_bsi": -0.033},
    "Pskov":      {"ndvi": 0.425, "ndbi": 0.051, "bsi": 0.104, "fuel_pct": 3.3, "metal_pct": 0.1,
                   "d30_ndvi": +0.281, "d30_ndbi": +0.498, "d30_bsi": +0.312,
                   "d1y_ndvi": +0.233, "d1y_ndbi": +0.035, "d1y_bsi": +0.071},
}

exp13_change_mag = {
    "Chkalovsk": {"median": 4575, "p90": 7135, "p95": 8034, "p99": 9824},
    "Kronstadt":  {"median": 10688, "p90": 13759, "p95": 14142, "p99": 14395},
    "Pskov":      {"median": 4255, "p90": 7840, "p95": 8607, "p99": 10400},
}

exp14_yoy = {
    "Chkalovsk": {2024: {"ndvi": 0.330, "bsi": 0.135}, 2025: {"ndvi": 0.265, "bsi": 0.101}, 2026: {"ndvi": 0.149, "bsi": -0.120}},
    "Pskov": {2024: {"ndvi": 0.330, "bsi": -0.065}, 2026: {"ndvi": 0.401, "bsi": 0.075}},
}

exp15_iforest = {
    "Chkalovsk": {"anomaly_pct": 5.0, "man_made": 22, "bare_impervious": 58, "bright_nir": 29,
                  "hotspot_quadrant": "NW (7.2%)"},
    "Kronstadt":  {"anomaly_pct": 5.0, "man_made": 37, "bare_impervious": 80, "bright_nir": 94,
                   "hotspot_quadrant": "NW (9.7%)"},
    "Pskov":      {"anomaly_pct": 5.0, "man_made": 26, "bare_impervious": 74, "bright_nir": 35,
                   "hotspot_quadrant": "SW (10.0%)"},
}
