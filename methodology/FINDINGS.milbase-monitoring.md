# Military Base Monitoring — Research Findings

## Current State Audit (2026-03-21)

### Working Data Sources
| Source | Signals (14d) | Sites | Quality |
|--------|-------------|-------|---------|
| FIRMS thermal | 1,005 | 14 | ✅ Good — real hotspots, FRP data |
| Satellite analysis | 367 | 37 | ⚠️ Broken after Mar 14 |
| OSINT milbase | 28 | 5 | ✅ Rich text but schema mismatch |
| ADS-B | 5,092 | — | ❌ Military misclassification |
| AIS naval | 345,857 | — | ⚠️ Not attributed to bases |
| GDELT | 893 | 20+ | ❌ Noise — world news geocoded to bases |
| ACLED | — | — | Not checked |

### Critical Gaps

1. **No fusion engine**: Dempster-Shafer deleted in Dagu migration.
   Each source reports independently. No combined threat picture.

2. **Satellite blind since Mar 14**: Sentinel-2 collector broken.
   7+ days without imagery analysis. Only FIRMS provides continuity.

3. **No baselines**: Cannot detect anomalies without knowing normal activity.

4. **No cross-source correlation**: FIRMS spike + satellite change + OSINT report
   at same site/time = strong signal. Currently uncorrelated.

### FIRMS Anomaly Detection (Experiment 30)

Pskov-76th-VDV (76th Guards Air Assault Division, closest to Estonia):
```
2026-03-07:   1 hotspot
2026-03-10:   4
2026-03-14:   2
2026-03-16:   2
2026-03-17:  22 🔴 (z=2.2, 4.4x above mean)
2026-03-18:   3
2026-03-19:   1
```
March 17 spike: 22 thermal hotspots vs baseline mean=5.0 (std=7.6).
This correlates with reported airborne training exercises.

Rostov-Southern-HQ (Southern Military District):
```
2026-03-10:   1
2026-03-12:  13
2026-03-13:   5
2026-03-14:  30 🔴 (z=1.4, 2.5x above mean)
```

## Research Priorities

### P0: FIRMS-Based Activity Baseline
FIRMS is the ONLY continuously working source. Build per-site baselines:
- 30-day rolling mean + std per site
- Z-score anomaly detection (z > 2 = elevated activity)
- FRP-weighted anomalies (high FRP = engines/explosions, not agriculture)

### P1: Satellite Analysis Recovery
- Debug Sentinel-2 collector (why acquisitions_7d=0 since Mar 14?)
- Consider Planet Labs or Maxar as backup source
- The Gemini-based analysis was producing good results when working

### P2: Fusion Engine Rebuild
Original formula (from deleted task_enrichment.go):
```
Weights: satellite=30%, osint=25%, firms=15%, gdelt=15%, acled=10%, milwatch=5%
```
Need to rebuild as ingest API endpoint. But FIRST fix the input sources.

### P3: ADS-B Military Classification
Current: ICAO hex range matching → Russian civilian airlines tagged military.
Fix: use actual military aircraft database (callsign patterns, aircraft types).
E.g., RFF* = Russian Air Force, RF-* = military registration.

### P4: AIS Geofencing
Attribute naval vessels to base proximity:
- Baltiysk-naval: vessels within 5km
- Kronstadt-naval: vessels within 5km
- Severomorsk-NorthFleet: vessels within 10km
Track: vessel count per base per day, anomaly = more vessels than baseline.

### P5: GDELT Relevance Filtering
Current GDELT tags ANY article to nearby coordinates.
Fix: require article text to MENTION the base/military/Russia.
Simple: `title ILIKE '%military%' OR title ILIKE '%base%' OR title ILIKE '%exercise%'`
