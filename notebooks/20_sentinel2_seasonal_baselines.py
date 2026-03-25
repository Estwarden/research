#!/usr/bin/env python3
"""
20. Sentinel-2 Seasonal NDVI/BSI Profiles — 3-Year Baselines per Military Site
================================================================================

Previous findings (FINDINGS.satellite-imagery.md):
  - Exp 11: 30-day BSI deltas dominated by seasonal snowmelt (+0.34 Chkalovsk)
  - Exp 12: YoY comparison better but single-year unreliable
  - Exp 14: Need 3+ years of same-month data for meaningful trend
  - Recommendation: Build per-site weekly expected values, z-score against them

This notebook:
  1. Queries Google Earth Engine for Sentinel-2 imagery at 5 key sites (2023–2026)
  2. Extracts per-image zonal median for NDVI, BSI, NDBI, fuel_ratio, metal_ratio
  3. Aggregates to weekly medians in Python
  4. Fits seasonal model: expected(week_of_year) = median across all years
  5. Computes seasonal std (MAD-based robust) per week for z-score denominator
  6. Exports seasonal_profiles.csv (site × week × index × expected × std)
  7. Demonstrates deseasonalized anomaly detection on recent acquisitions

Requires: earthengine-api (pip install earthengine-api), numpy
GEE auth must be configured (ee.Authenticate() or service account).
"""
import csv
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

import numpy as np

try:
    import ee
    ee.Initialize()
    print("✓ Google Earth Engine initialized")
except Exception as e:
    print(f"✗ GEE initialization failed: {e}")
    print("  Run: earthengine authenticate")
    sys.exit(1)

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
SAT_DATA = os.path.join(DATA, 'satellite')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(SAT_DATA, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)

print("=" * 72)
print("20. SENTINEL-2 SEASONAL BASELINES — 3-YEAR PROFILES")
print("=" * 72)

# ================================================================
# SITE DEFINITIONS
# ================================================================
# Publicly known military installations from open-source intelligence.
# Coordinates from OpenStreetMap / Wikimapia / ISW public reports.
# ROI: 2km × 2km box centered on each facility.
SITES = {
    "Pskov-76VDV": {
        "center": [28.395, 57.785],   # lon, lat — 76th VDV airfield
        "type": "airborne",
        "description": "76th Guards Air Assault Division airfield",
    },
    "Cherekha": {
        "center": [28.420, 57.740],   # south of Pskov
        "type": "garrison",
        "description": "Cherekha garrison — motor pool and barracks",
    },
    "Luga": {
        "center": [29.846, 58.737],
        "type": "garrison",
        "description": "Luga training ground and garrison",
    },
    "Chkalovsk": {
        "center": [20.415, 54.775],   # Kaliningrad exclave
        "type": "airbase",
        "description": "Chkalovsk naval aviation airbase",
    },
    "Kronstadt": {
        "center": [29.768, 59.988],
        "type": "naval",
        "description": "Kronstadt naval base — Baltic Fleet",
    },
}

# Analysis parameters
ROI_RADIUS_M = 1000        # 1km radius = 2km × 2km box
DATE_START = "2023-01-01"
DATE_END = "2026-03-25"    # current date
MAX_CLOUD_PCT = 40         # per-scene cloud cover filter (%)
SCALE_M = 20               # 20m for efficiency (SWIR bands are native 20m)
INDICES = ['ndvi', 'bsi', 'ndbi', 'fuel_ratio', 'metal_ratio']


def make_roi(center, radius_m=ROI_RADIUS_M):
    """Create a square ROI around center [lon, lat]."""
    return ee.Geometry.Point(center).buffer(radius_m).bounds()


def add_spectral_indices(image):
    """Compute spectral indices server-side on an S2 SR image.

    Sentinel-2 SR bands (Surface Reflectance, ×10000 scale):
      B2=Blue, B3=Green, B4=Red, B8=NIR, B11=SWIR1(1610nm), B12=SWIR2(2190nm)
    """
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('ndvi')

    # BSI = ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
    bsi_num = image.select('B11').add(image.select('B4')).subtract(
        image.select('B8').add(image.select('B2')))
    bsi_den = image.select('B11').add(image.select('B4')).add(
        image.select('B8')).add(image.select('B2'))
    bsi = bsi_num.divide(bsi_den).rename('bsi')

    ndbi = image.normalizedDifference(['B11', 'B8']).rename('ndbi')

    # Fuel proxy: SWIR2 relative to NIR (high SWIR2 + low vegetation)
    fuel = image.select('B12').toFloat().divide(
        image.select('B8').toFloat().add(100)).rename('fuel_ratio')

    # Metal proxy: high NIR relative to Red (bright reflective surfaces)
    metal = image.select('B8').toFloat().divide(
        image.select('B4').toFloat().add(100)).rename('metal_ratio')

    return image.addBands([ndvi, bsi, ndbi, fuel, metal])


def extract_site_timeseries(site_name, site_info):
    """Extract per-image zonal medians for a site via a single GEE call.

    Uses ee.ImageCollection.map() + ee.FeatureCollection export to get
    all per-image stats in one server roundtrip.
    """
    roi = make_roi(site_info['center'])

    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(roi)
                  .filterDate(DATE_START, DATE_END)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD_PCT))
                  .map(add_spectral_indices)
                  .select(INDICES))

    def reduce_image(image):
        """Reduce one image to zonal median stats over the ROI."""
        stats = image.reduceRegion(
            reducer=ee.Reducer.median(),
            geometry=roi,
            scale=SCALE_M,
            maxPixels=1e6,
            bestEffort=True,
        )
        # ee.Dictionary.set() takes (key, value) — chain for multiple
        props = stats.combine(ee.Dictionary({
            'date': image.date().format('YYYY-MM-dd'),
            'cloud_pct': image.get('CLOUDY_PIXEL_PERCENTAGE'),
        }))
        return ee.Feature(None, props)

    features = collection.map(reduce_image)

    # Fetch the entire timeseries in one call
    result = features.getInfo()
    records = []
    for feat in result.get('features', []):
        props = feat.get('properties', {})
        date_str = props.get('date', '')
        if not date_str:
            continue
        # Check that at least NDVI is not None
        if props.get('ndvi') is None:
            continue

        dt = datetime.strptime(date_str, "%Y-%m-%d")
        iso_year, iso_week, _ = dt.isocalendar()

        records.append({
            'site': site_name,
            'date': date_str,
            'year': iso_year,
            'week': iso_week,
            'cloud_pct': props.get('cloud_pct'),
            'ndvi': props.get('ndvi'),
            'bsi': props.get('bsi'),
            'ndbi': props.get('ndbi'),
            'fuel_ratio': props.get('fuel_ratio'),
            'metal_ratio': props.get('metal_ratio'),
        })

    return records


# ================================================================
# PHASE 1: Collect per-image spectral data for all sites
# ================================================================
print("\n" + "=" * 72)
print("PHASE 1: Extracting per-image spectral indices from GEE")
print("=" * 72)

all_records = []
for site_name, site_info in SITES.items():
    print(f"\n  {site_name} ({site_info['description']})... ", end="", flush=True)
    t0 = time.time()
    try:
        records = extract_site_timeseries(site_name, site_info)
        elapsed = time.time() - t0
        print(f"{len(records)} images in {elapsed:.0f}s")
        all_records.extend(records)
    except Exception as e:
        print(f"FAILED: {e}")

print(f"\n  Total: {len(all_records)} per-image observations across {len(SITES)} sites")

# Save raw per-image data
raw_csv = os.path.join(SAT_DATA, 'per_image_spectral.csv')
if all_records:
    fields = ['site', 'date', 'year', 'week', 'cloud_pct'] + INDICES
    with open(raw_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_records)
    print(f"  ✓ Per-image data saved: {raw_csv}")


# ================================================================
# PHASE 2: Aggregate to weekly medians
# ================================================================
print("\n" + "=" * 72)
print("PHASE 2: Aggregating to weekly medians")
print("=" * 72)

# Group by (site, year, week)
weekly_groups = defaultdict(list)
for rec in all_records:
    key = (rec['site'], rec['year'], rec['week'])
    weekly_groups[key].append(rec)

weekly_data = []
for (site, year, week), recs in sorted(weekly_groups.items()):
    row = {
        'site': site,
        'year': year,
        'week': week,
        'n_images': len(recs),
        'date_start': min(r['date'] for r in recs),
    }
    for idx in INDICES:
        vals = [r[idx] for r in recs if r[idx] is not None]
        row[idx] = float(np.median(vals)) if vals else None
    weekly_data.append(row)

weekly_csv = os.path.join(SAT_DATA, 'weekly_spectral.csv')
if weekly_data:
    fields = ['site', 'year', 'week', 'n_images', 'date_start'] + INDICES
    with open(weekly_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(weekly_data)
    print(f"  ✓ Weekly data saved: {weekly_csv} ({len(weekly_data)} rows)")


# ================================================================
# PHASE 3: Build seasonal profiles (expected value per week-of-year)
# ================================================================
print("\n" + "=" * 72)
print("PHASE 3: Building seasonal profiles")
print("=" * 72)

# Group by (site, week_of_year) across all years
seasonal_data = defaultdict(lambda: defaultdict(list))
for row in weekly_data:
    site = row['site']
    woy = row['week']  # 1..53
    for idx in INDICES:
        val = row[idx]
        if val is not None:
            seasonal_data[(site, woy)][idx].append(val)

seasonal_profiles = []
for (site, woy), idx_vals in sorted(seasonal_data.items()):
    profile = {'site': site, 'week_of_year': woy}
    for idx in INDICES:
        vals = idx_vals.get(idx, [])
        if len(vals) >= 2:
            arr = np.array(vals)
            profile[f'{idx}_expected'] = float(np.median(arr))
            profile[f'{idx}_std'] = float(np.std(arr, ddof=1))
            mad = float(np.median(np.abs(arr - np.median(arr))))
            profile[f'{idx}_mad'] = mad
            profile[f'{idx}_robust_std'] = mad * 1.4826
            profile[f'{idx}_n_years'] = len(vals)
        elif len(vals) == 1:
            profile[f'{idx}_expected'] = vals[0]
            profile[f'{idx}_std'] = float('nan')
            profile[f'{idx}_mad'] = float('nan')
            profile[f'{idx}_robust_std'] = float('nan')
            profile[f'{idx}_n_years'] = 1
        else:
            profile[f'{idx}_expected'] = float('nan')
            profile[f'{idx}_std'] = float('nan')
            profile[f'{idx}_mad'] = float('nan')
            profile[f'{idx}_robust_std'] = float('nan')
            profile[f'{idx}_n_years'] = 0
    seasonal_profiles.append(profile)

# Export seasonal_profiles.csv
profile_csv = os.path.join(SAT_DATA, 'seasonal_profiles.csv')
if seasonal_profiles:
    fields = ['site', 'week_of_year']
    for idx in INDICES:
        fields.extend([f'{idx}_expected', f'{idx}_std', f'{idx}_mad',
                       f'{idx}_robust_std', f'{idx}_n_years'])
    with open(profile_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(seasonal_profiles)
    print(f"\n  ✓ Seasonal profiles saved: {profile_csv}")
    print(f"    {len(seasonal_profiles)} rows ({len(SITES)} sites × up to 53 weeks)")


# ================================================================
# PHASE 4: Print seasonal profile summaries
# ================================================================
print("\n" + "=" * 72)
print("PHASE 4: Seasonal Profile Summaries")
print("=" * 72)

for site_name in SITES:
    site_profs = [p for p in seasonal_profiles if p['site'] == site_name]
    if not site_profs:
        print(f"\n{site_name}: No data")
        continue

    print(f"\n{'─' * 60}")
    print(f"{site_name} ({SITES[site_name]['type']}) — {SITES[site_name]['description']}")
    print(f"{'─' * 60}")

    for idx in INDICES:
        expected_vals = [p[f'{idx}_expected'] for p in site_profs
                         if not math.isnan(p.get(f'{idx}_expected', float('nan')))]
        if not expected_vals:
            print(f"  {idx.upper()}: no data")
            continue

        arr = np.array(expected_vals)
        n_years_vals = [p[f'{idx}_n_years'] for p in site_profs
                        if p.get(f'{idx}_n_years', 0) >= 1]

        # Find winter minimum and summer maximum weeks
        valid_profs = [(p['week_of_year'], p[f'{idx}_expected']) for p in site_profs
                       if not math.isnan(p.get(f'{idx}_expected', float('nan')))]
        min_woy, min_val = min(valid_profs, key=lambda x: x[1])
        max_woy, max_val = max(valid_profs, key=lambda x: x[1])

        print(f"\n  {idx.upper()}")
        print(f"    Range:     {arr.min():.4f} → {arr.max():.4f} (amplitude: {arr.max()-arr.min():.4f})")
        print(f"    Annual μ:  {arr.mean():.4f} (σ={arr.std():.4f})")
        print(f"    Low  (wk {min_woy:2d}): {min_val:.4f}")
        print(f"    High (wk {max_woy:2d}): {max_val:.4f}")
        print(f"    Coverage:  {len(expected_vals)} weeks, "
              f"avg {np.mean(n_years_vals):.1f} years/week")


# ================================================================
# PHASE 5: Deseasonalized anomaly detection on 2026 data
# ================================================================
print("\n" + "=" * 72)
print("PHASE 5: Deseasonalized Anomaly Detection (2026)")
print("=" * 72)
print("""
Formula:
  z = (observed - expected(week)) / robust_std(week)
  robust_std = 1.4826 × MAD(values for that week across all years)

Interpretation:
  |z| < 1.0 : Normal seasonal variation
  |z| > 2.0 : Anomalous — investigate
  |z| > 3.0 : Highly anomalous — likely real activity change
""")

RECENT_YEAR = 2026

# Build lookup: (site, week_of_year) → profile
profile_lookup = {}
for p in seasonal_profiles:
    profile_lookup[(p['site'], p['week_of_year'])] = p

anomaly_table = []
for row in weekly_data:
    if row['year'] != RECENT_YEAR:
        continue
    site = row['site']
    woy = row['week']
    profile = profile_lookup.get((site, woy))
    if profile is None:
        continue

    for idx in INDICES:
        observed = row.get(idx)
        if observed is None:
            continue
        expected = profile.get(f'{idx}_expected')
        robust_std = profile.get(f'{idx}_robust_std')
        n_years = profile.get(f'{idx}_n_years', 0)

        if (expected is None or robust_std is None
                or math.isnan(expected) or math.isnan(robust_std)
                or n_years < 2):
            continue

        if robust_std < 1e-6:
            z = 0.0
        else:
            z = (observed - expected) / robust_std

        anomaly_table.append({
            'site': site,
            'week': woy,
            'date': row.get('date_start', ''),
            'index': idx,
            'observed': observed,
            'expected': expected,
            'robust_std': robust_std,
            'z_score': z,
            'n_years': n_years,
            'anomalous': abs(z) > 2.0,
        })

# Print anomaly results
if anomaly_table:
    anomalies = [a for a in anomaly_table if a['anomalous']]
    print(f"{'─' * 80}")
    print(f"2026 Anomalies (|z| > 2.0) — top 30 by |z|")
    print(f"{'─' * 80}")
    print(f"{'Site':<16} {'Wk':>3} {'Date':<11} {'Index':<13} "
          f"{'Obs':>8} {'Exp':>8} {'σ':>7} {'z':>7} {'N':>2}")
    print(f"{'─'*16} {'─'*3} {'─'*11} {'─'*13} {'─'*8} {'─'*8} {'─'*7} {'─'*7} {'─'*2}")

    if anomalies:
        for a in sorted(anomalies, key=lambda x: abs(x['z_score']), reverse=True)[:30]:
            flag = "🔴" if abs(a['z_score']) > 3.0 else "🟡"
            print(f"{a['site']:<16} {a['week']:>3} {a['date']:<11} {a['index']:<13} "
                  f"{a['observed']:>8.4f} {a['expected']:>8.4f} "
                  f"{a['robust_std']:>7.4f} {a['z_score']:>+7.2f} {a['n_years']:>2} {flag}")
    else:
        print("  No anomalies detected (|z| > 2.0)")

    # Summary stats
    n_total = len(anomaly_table)
    n_anom = len(anomalies)
    n_severe = sum(1 for a in anomalies if abs(a['z_score']) > 3.0)
    print(f"\n  Total scored observations: {n_total}")
    print(f"  Anomalies (|z|>2):        {n_anom} ({100*n_anom/max(n_total,1):.1f}%)")
    print(f"  Severe    (|z|>3):        {n_severe}")

    # Per-site anomaly rate
    print(f"\n{'─' * 80}")
    print(f"Anomaly Rate by Site × Index (2026)")
    print(f"{'─' * 80}")
    print(f"{'Site':<16}", end="")
    for idx in INDICES:
        print(f" {idx:>12}", end="")
    print()
    for site_name in SITES:
        print(f"{site_name:<16}", end="")
        for idx in INDICES:
            site_idx = [a for a in anomaly_table
                        if a['site'] == site_name and a['index'] == idx]
            site_anom = [a for a in site_idx if a['anomalous']]
            if site_idx:
                rate = 100 * len(site_anom) / len(site_idx)
                print(f" {rate:>10.0f}%  ", end="")
            else:
                print(f" {'—':>12}", end="")
        print()
else:
    print("  No 2026 data available for anomaly detection demo.")


# ================================================================
# PHASE 6: Cross-site seasonal comparison
# ================================================================
print("\n" + "=" * 72)
print("PHASE 6: Cross-Site Seasonal Amplitude Comparison")
print("=" * 72)

print(f"\n{'Site':<16} {'Type':<10}", end="")
for idx in INDICES:
    print(f" {idx+'_amp':>14}", end="")
print()
print(f"{'─'*16} {'─'*10}", end="")
for _ in INDICES:
    print(f" {'─'*14}", end="")
print()

for site_name, site_info in SITES.items():
    print(f"{site_name:<16} {site_info['type']:<10}", end="")
    for idx in INDICES:
        vals = [p[f'{idx}_expected'] for p in seasonal_profiles
                if p['site'] == site_name
                and not math.isnan(p.get(f'{idx}_expected', float('nan')))]
        if vals:
            amp = max(vals) - min(vals)
            print(f" {amp:>14.4f}", end="")
        else:
            print(f" {'—':>14}", end="")
    print()


# ================================================================
# PHASE 7: Model coverage validation
# ================================================================
print("\n" + "=" * 72)
print("PHASE 7: Seasonal Model Coverage Validation")
print("=" * 72)
print("\n  Need ≥3 years for robust_std to be meaningful")
print(f"  Need ≥2 years minimum for any seasonal estimate\n")

for site_name in SITES:
    site_profs = [p for p in seasonal_profiles if p['site'] == site_name]
    n_weeks = len(site_profs)
    n_ge3 = sum(1 for p in site_profs if p.get('ndvi_n_years', 0) >= 3)
    n_ge2 = sum(1 for p in site_profs if p.get('ndvi_n_years', 0) >= 2)
    n_1only = sum(1 for p in site_profs if p.get('ndvi_n_years', 0) == 1)

    print(f"  {site_name:<16}: {n_weeks:>3} weeks | "
          f"≥3yr: {n_ge3:>3} ({100*n_ge3/max(n_weeks,1):.0f}%) | "
          f"≥2yr: {n_ge2:>3} ({100*n_ge2/max(n_weeks,1):.0f}%) | "
          f"1yr: {n_1only:>3}")


# ================================================================
# FINAL SUMMARY
# ================================================================
print("\n" + "=" * 72)
print("SUMMARY")
print("=" * 72)

n_per_site = defaultdict(int)
for r in all_records:
    n_per_site[r['site']] += 1

print(f"\nSites analyzed:       {len(SITES)}")
print(f"Date range:           {DATE_START} to {DATE_END}")
print(f"Total per-image obs:  {len(all_records)}")
print(f"Total weekly obs:     {len(weekly_data)}")
print(f"Seasonal profiles:    {len(seasonal_profiles)} (site × week-of-year)")
for sn in SITES:
    print(f"  {sn:<16}: {n_per_site.get(sn,0):>4} images")

print(f"""
Output files:
  {raw_csv}
  {weekly_csv}
  {profile_csv}

Deseasonalized Anomaly Formula (copy to production Go code):
  expected := seasonalProfile[site][weekOfYear].median
  robustStd := seasonalProfile[site][weekOfYear].mad * 1.4826
  z := (observed - expected) / robustStd
  if math.Abs(z) > 2.0 {{ flagAnomaly(site, index, z) }}

This eliminates seasonal false positives (snowmelt, spring thaw, autumn
senescence) that dominated the raw 30-day delta approach (Exp 11-12).
Year-over-year instability (Exp 14) is smoothed by using 3-year median.
""")
