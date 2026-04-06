---
status: growing
tags: [satellite, geoint, sentinel, milbase, multi-source]
---

# Satellite Monitoring

EstWarden monitors Russian military installations near the Baltic — Pskov (76th Guards Airborne), Luga (training grounds), Kronstadt (Baltic Fleet), and others — using free satellite imagery. The goal: detect significant activity changes before they appear in the news cycle.

In March 2026, this mattered concretely: [NASA FIRMS detected a massive fire](https://www.facebook.com/OnGeoIntelligence/videos/1259426422299178/) at the Zavelichi training ground in Pskov Oblast, 32km from NATO territory. Delfi Estonia published [satellite analysis showing Russian bases near Estonia have been half-emptied](https://ekspress.delfi.ee/artikkel/120333504/satellite-imagery-analysis-what-s-going-on-in-putin-s-military-bases-behind-the-estonian-border-and-how-big-a-threat-they-really-pose-us) over recent years — forces redeployed to Ukraine. Knowing this in near-real-time matters for Baltic defense planning.

## Production: Multi-Source GEOINT (April 2026)

The [latest production pipeline](https://blog.estwarden.eu/investigations/multi-source-geoint/) has moved well beyond what the research notebooks cover. It fuses **7 independent sources** into a single confidence score per site:

**Optical satellite** (Sentinel-2, 13 bands) — now computes 8 spectral indices instead of the original 3:

| Index | What it sees | Why it matters |
|-------|-------------|----------------|
| NDVI | Vegetation health | Baseline — vehicle staging disturbs vegetation |
| **NDRE** | Red-edge reflectance (700-783nm) | **Camouflage detection** — paint can't replicate the cellular reflectance spike of real leaves |
| NDBI | Built-up areas | New construction, hardened shelters |
| BSI | Bare soil | Ground disturbance, earthworks |
| **EVI** | Dense vegetation (NDVI saturates in forests) | Baltic region is heavily forested — EVI works where NDVI can't |
| **NDWI / MNDWI** | Water bodies, flooding | Port activity, dam infrastructure |
| **NBR** | Burn scars | Strike damage, fire events like the Pskov fire |

**SAR radar** (Sentinel-1, dual polarization) — works through clouds and at night. The VH/VV ratio distinguishes metal structures (low ratio) from vegetation (high ratio). In a region that's overcast 60-70% of the year, this is essential.

**Nighttime lights** (VIIRS DNB) — new lights at a base that's usually dark, or a base going dark that's usually lit, are both significant.

**Land cover** (Dynamic World) — 10m classification detects when forest is cleared or structures appear.

**Ship tracking** (AIS within 30km of naval bases) — compares current 48-hour vessel count against 7-day baseline.

**Aircraft tracking** (ADS-B within 50km of airbases) — same comparison.

**Fire hotspots** (FIRMS) — thermal alerts per site.

### EMCON Detection

The most intelligence-relevant innovation. When a base shows satellite activity (new vehicles, ground disturbance) but AIS/ADS-B transponders go silent against their baseline — that's Emissions Control (EMCON). Someone deliberately turned off their tracking. In intelligence, the absence of an expected signal is often more significant than the presence of a new one.

### Camouflage Detection

NDRE exploits physics that camouflage can't defeat. Healthy plant cells produce a reflectance spike between 700-783nm (the "red edge") caused by internal leaf structure. Camouflage paint, no matter how well-matched in visible green, scores near zero in this band. High NDVI + low NDRE = camouflage suspect.

### Alternative Hypotheses

Every observation now gets 2-3 competing explanations ranked by likelihood (exercise / operational deployment / routine maintenance), borrowed from Analysis of Competing Hypotheses methodology. This combats the tendency to see what you expect.

## Research: Notebooks 20-23

The research notebooks established the *foundation* for what production now uses, but are significantly behind the current pipeline:

**nb20 — Seasonal Baselines.** Built 3-year NDVI/BSI weekly profiles per site via Google Earth Engine. Key insight: year-over-year same-month comparison is the correct baseline, not 30-day rolling (which triggers on snowmelt). HIGH confidence — this methodology is the basis of the production deseasonalized z-scores.

**nb22 — CCDC Breakpoints.** Continuous Change Detection found 6 abrupt spectral shifts across monitored sites in 3 years. One matched the ISW timeline: Luga base showed a breakpoint 2 days before ISW reported a deployment. MEDIUM confidence — promising but N=6 with only 1 confirmed match.

**nb21 — Isolation Forest.** Per-site anomaly detection on spectral features. Detected ships at Kronstadt (94% bright NIR) and equipment staging at Pskov. Acts as a proxy — catches surface changes but can't distinguish military from civilian activity.

**nb23 — Temporal Change Maps.** Automated year-over-year heatmaps for Luga and Pskov-76VDV (14 maps in `../output/change_heatmaps/`). Eliminates snowmelt false positives.

### Earlier Work (satellite-analysis/)

Pre-research Jupyter experiments: YOLO vehicle detection on SkySat imagery found zero military vehicles at Russian bases (but successfully detected 10+ aircraft at Tallinn Airport as positive control). Spectral clustering and SAR backscatter analysis produced ambiguous results. All superseded by nb20-23 and now by the production pipeline.

## Gap: Research Needs to Catch Up

The production pipeline has shipped capabilities the research hasn't validated:

| Production feature | Research status | What's needed |
|---|---|---|
| NDRE camouflage detection | Not studied | Validate against known concealment sites |
| EMCON correlation | Not studied | Test against ISW deployment timeline |
| 7-source confidence scoring | Not studied | Measure false positive / negative rates |
| Dual-pol SAR baselines | Not studied | Build VV/VH seasonal profiles (like nb20 did for optical) |
| EVI for dense forest | Not studied | Compare EVI vs NDVI for Baltic forest sites |
| Alternative hypotheses quality | Not studied | Evaluate against analyst assessments |

These should become R-59 through R-64 in [[Research Directions]].

## Sources

- [Seeing What's Hidden — EstWarden blog](https://blog.estwarden.eu/investigations/multi-source-geoint/) (April 2026)
- [Satellite imagery of Pskov fire](https://www.facebook.com/OnGeoIntelligence/videos/1259426422299178/) — OnGeo Intelligence (March 2026)
- [Russian bases near Estonia half-emptied](https://ekspress.delfi.ee/artikkel/120333504/) — Delfi/Ekspress satellite analysis
- Sentinel-2: [ESA Copernicus](https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-2), 13-band optical, 10m, 5-day revisit
- Sentinel-1: [ESA Copernicus](https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-1), C-band SAR, works through clouds
