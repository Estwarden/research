#!/usr/bin/env python3
"""
23. Sentinel-2 Temporal Change Detection — Luga & Pskov Feb→Mar 2026
======================================================================

Previous findings:
  - satellite-analysis/outputs/04-sentinel2-comparison/: manual Luga comparison
    showed Feb→Mar change dominated by seasonal snowmelt (metal/fuel false pos)
  - NB 20: Seasonal baselines (weekly median + MAD) for deseasonalized z-scores
  - NB 21: IsolationForest baselines per quadrant
  - NB 22: CCDC breakpoints (long-term structural change)
  - FINDINGS.satellite-imagery.md Exp 12: 30d BSI deltas are seasonal artifacts;
    year-over-year same-month comparison is the correct baseline

This notebook AUTOMATES temporal change detection:
  1. For Luga and Pskov, finds the 2 cleanest (<10% cloud) S2 acquisitions
     in Feb 2026 and Mar 2026
  2. Computes per-pixel change magnitude across 6 bands
  3. Computes change in spectral indices (NDVI, BSI, metal_ratio, fuel_ratio)
  4. Generates change heatmaps via EE thumbnail URLs
  5. Classifies changes: seasonal (NDVI from snowmelt), infrastructure (BSI),
     potential_activity (fuel/metal)
  6. Outputs change statistics per quadrant
  7. Uses NB 20 seasonal profiles for deseasonalized z-score comparison

All processing runs server-side in Google Earth Engine. Only zonal statistics
and thumbnail URLs are downloaded.

Requires: earthengine-api, numpy
"""
import csv
import json
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(SCRIPT_DIR, '..', 'data')
SAT_DATA = os.path.join(DATA, 'satellite')
OUTPUT = os.path.join(SCRIPT_DIR, '..', 'output')
METHODOLOGY = os.path.join(SCRIPT_DIR, '..', 'methodology')
os.makedirs(SAT_DATA, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)
os.makedirs(METHODOLOGY, exist_ok=True)

print("=" * 76)
print("23. SENTINEL-2 TEMPORAL CHANGE DETECTION — LUGA & PSKOV Feb→Mar 2026")
print("=" * 76)

# ================================================================
# SITE DEFINITIONS (subset of NB 20 sites)
# ================================================================
SITES = {
    "Luga": {
        "center": [29.846, 58.737],
        "type": "garrison",
        "description": "Luga training ground and garrison",
    },
    "Pskov-76VDV": {
        "center": [28.395, 57.785],
        "type": "airborne",
        "description": "76th Guards Air Assault Division airfield",
    },
}

ROI_RADIUS_M = 1000
SCALE_M = 20          # SWIR native resolution
MAX_CLOUD_PCT = 10    # strict cloud filter for clean pairs
QUADRANT_NAMES = ['NW', 'NE', 'SW', 'SE']

# Time windows for image selection
FEB_START = "2026-02-01"
FEB_END = "2026-02-28"
MAR_START = "2026-03-01"
MAR_END = "2026-03-25"  # current date

# Bands for raw change magnitude
RAW_BANDS = ['B2', 'B3', 'B4', 'B8', 'B11', 'B12']
BAND_LABELS = {
    'B2': 'Blue', 'B3': 'Green', 'B4': 'Red',
    'B8': 'NIR', 'B11': 'SWIR1', 'B12': 'SWIR2',
}

# Spectral indices for change analysis
INDEX_NAMES = ['ndvi', 'bsi', 'ndbi', 'fuel_ratio', 'metal_ratio']


# ================================================================
# HELPER FUNCTIONS
# ================================================================

def make_roi(center, radius_m=ROI_RADIUS_M):
    """Create a square ROI around center [lon, lat]."""
    return ee.Geometry.Point(center).buffer(radius_m).bounds()


def make_quadrant_fc(lon, lat, radius_m=ROI_RADIUS_M):
    """FeatureCollection of 4 labeled quadrant rectangles."""
    lat_d = radius_m / 111000
    lon_d = radius_m / (111000 * math.cos(math.radians(lat)))
    return ee.FeatureCollection([
        ee.Feature(ee.Geometry.Rectangle(
            [lon - lon_d, lat, lon, lat + lat_d]), {'quadrant': 'NW'}),
        ee.Feature(ee.Geometry.Rectangle(
            [lon, lat, lon + lon_d, lat + lat_d]), {'quadrant': 'NE'}),
        ee.Feature(ee.Geometry.Rectangle(
            [lon - lon_d, lat - lat_d, lon, lat]), {'quadrant': 'SW'}),
        ee.Feature(ee.Geometry.Rectangle(
            [lon, lat - lat_d, lon + lon_d, lat]), {'quadrant': 'SE'}),
    ])


def mask_clouds_scl(image):
    """Mask non-clear pixels using Scene Classification Layer.
    Keep: 4=vegetation, 5=bare, 6=water, 7=low-prob-cloud, 11=snow.
    Mask: 1=sat, 2=dark, 3=shadow, 8=med-cloud, 9=high-cloud, 10=cirrus.
    """
    scl = image.select('SCL')
    clear = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7)).Or(scl.eq(11))
    return image.updateMask(clear)


def add_spectral_indices(image):
    """Add spectral indices as bands (server-side). Matches NB 20 formulas."""
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('ndvi')

    # BSI = ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
    bsi_num = image.select('B11').add(image.select('B4')).subtract(
        image.select('B8').add(image.select('B2')))
    bsi_den = image.select('B11').add(image.select('B4')).add(
        image.select('B8')).add(image.select('B2'))
    bsi = bsi_num.divide(bsi_den).rename('bsi')

    ndbi = image.normalizedDifference(['B11', 'B8']).rename('ndbi')

    # Fuel proxy: SWIR2 / (NIR + 100)
    fuel = (image.select('B12').toFloat()
            .divide(image.select('B8').toFloat().add(100))
            .rename('fuel_ratio'))

    # Metal proxy: NIR / (Red + 100)
    metal = (image.select('B8').toFloat()
             .divide(image.select('B4').toFloat().add(100))
             .rename('metal_ratio'))

    return image.addBands([ndvi, bsi, ndbi, fuel, metal])


def find_cleanest_images(roi, date_start, date_end, n=2):
    """Find the N cleanest S2 images in a date range. Returns ee.ImageCollection."""
    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(roi)
                  .filterDate(date_start, date_end)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD_PCT))
                  .sort('CLOUDY_PIXEL_PERCENTAGE')
                  .limit(n))
    return collection


def get_image_metadata(collection):
    """Fetch date and cloud info for images in a collection."""
    def extract_props(image):
        return ee.Feature(None, {
            'date': image.date().format('YYYY-MM-dd'),
            'cloud_pct': image.get('CLOUDY_PIXEL_PERCENTAGE'),
            'system_id': image.get('system:index'),
        })
    info = collection.map(extract_props).getInfo()
    return [feat['properties'] for feat in info.get('features', [])]


def compute_change_image(before_img, after_img):
    """Compute change bands: delta per raw band and per index, plus magnitude.

    Returns an ee.Image with bands:
      - delta_B2..B12:  after - before (raw reflectance change)
      - delta_ndvi, delta_bsi, delta_ndbi, delta_fuel_ratio, delta_metal_ratio
      - change_magnitude: Euclidean distance across 6 raw bands
      - abs_ndvi_change, abs_bsi_change: absolute value for heatmaps
    """
    # Raw band deltas
    before_bands = before_img.select(RAW_BANDS)
    after_bands = after_img.select(RAW_BANDS)
    delta_raw = after_bands.subtract(before_bands).rename(
        [f'delta_{b}' for b in RAW_BANDS])

    # Change magnitude = sqrt(sum of squared deltas)
    sq_sum = delta_raw.pow(2).reduce(ee.Reducer.sum())
    magnitude = sq_sum.sqrt().rename('change_magnitude')

    # Index deltas
    before_indices = before_img.select(INDEX_NAMES)
    after_indices = after_img.select(INDEX_NAMES)
    delta_idx = after_indices.subtract(before_indices).rename(
        [f'delta_{idx}' for idx in INDEX_NAMES])

    # Absolute values for heatmap visualization
    abs_ndvi = delta_idx.select('delta_ndvi').abs().rename('abs_ndvi_change')
    abs_bsi = delta_idx.select('delta_bsi').abs().rename('abs_bsi_change')
    abs_fuel = delta_idx.select('delta_fuel_ratio').abs().rename('abs_fuel_change')
    abs_metal = delta_idx.select('delta_metal_ratio').abs().rename('abs_metal_change')

    return ee.Image.cat([delta_raw, delta_idx, magnitude,
                         abs_ndvi, abs_bsi, abs_fuel, abs_metal])


def classify_change_pixels(change_img, before_img, after_img):
    """Classify each pixel's change type (server-side).

    Classes:
      0 = no significant change
      1 = seasonal_snowmelt  (NDVI↑ AND/OR BSI↑ during thaw transition)
      2 = seasonal_freeze    (NDVI↓ from vegetation to snow/bare)
      3 = infrastructure     (BSI change not explained by season)
      4 = potential_activity  (fuel or metal ratio change beyond seasonal)

    IMPORTANT: We start from a band of the change image (not ee.Image(0))
    to preserve projection, scale, and mask. A bare ee.Image(0) is a global
    constant with no native resolution, causing reduceRegions to collapse
    the quadrant to ~1 pixel.

    The seasonal detection is deliberately broad. Feb→Mar in NW Russia sees
    the snow→bare→vegetation transition. This creates LARGE BSI changes
    (+0.3 to +0.5) that look like infrastructure but are actually seasonal.
    We classify as seasonal if ANY of these hold:
      - NDVI↑ with low-NDVI before (classic snowmelt)
      - BSI↑ with negative-BSI before (snow→bare transition)
      - NDBI↑ from very negative values (snow absorbs SWIR, bare doesn't)
    Only remaining BSI changes are flagged as infrastructure.
    """
    ndvi_delta = change_img.select('delta_ndvi')
    bsi_delta = change_img.select('delta_bsi')
    ndbi_delta = change_img.select('delta_ndbi')
    fuel_delta = change_img.select('delta_fuel_ratio')
    metal_delta = change_img.select('delta_metal_ratio')
    magnitude = change_img.select('change_magnitude')

    # Thresholds for significant change
    SIG_NDVI = 0.08
    SIG_BSI = 0.05
    SIG_FUEL = 0.02
    SIG_METAL = 0.3
    SIG_MAG = 500  # raw reflectance units

    # ── Seasonal detection (broad) ──
    # Before-state: winter/snow conditions (low NDVI, negative BSI)
    before_winter = before_img.select('ndvi').lt(0.15).And(
        before_img.select('bsi').lt(-0.10))

    # Criterion 1: Classic snowmelt — NDVI increases, was snow/bare before
    melt_ndvi = ndvi_delta.gt(SIG_NDVI).And(
        before_img.select('ndvi').lt(0.15))

    # Criterion 2: Snow→bare transition — BSI jumps positive from negative,
    # with concurrent NDBI increase (snow has very negative NDBI)
    melt_bsi = bsi_delta.gt(SIG_BSI).And(
        before_img.select('bsi').lt(-0.10)).And(
        ndbi_delta.gt(0.3))

    # Criterion 3: SWIR rebound — NDBI increases from deeply negative
    # (snow absorbs SWIR heavily, so NDBI << 0 in winter)
    melt_ndbi = ndbi_delta.gt(0.4).And(
        before_img.select('ndbi').lt(-0.4))

    # Any of the above = seasonal change
    seasonal_melt = melt_ndvi.Or(melt_bsi).Or(melt_ndbi)

    # Seasonal freeze (reverse direction)
    seasonal_freeze = ndvi_delta.lt(-SIG_NDVI).And(
        after_img.select('ndvi').lt(0.12))

    # All seasonal pixels
    seasonal = seasonal_melt.Or(seasonal_freeze)

    # ── Non-seasonal classification ──
    # No significant change
    no_change = magnitude.lt(SIG_MAG).And(ndvi_delta.abs().lt(SIG_NDVI))

    # Infrastructure: BSI change not explained by seasonal transition
    infra_change = bsi_delta.abs().gt(SIG_BSI).And(
        seasonal.Not()).And(no_change.Not())

    # Potential activity: fuel or metal change not captured above
    activity_change = (fuel_delta.abs().gt(SIG_FUEL).Or(
        metal_delta.abs().gt(SIG_METAL))).And(
        seasonal.Not()).And(infra_change.Not()).And(no_change.Not())

    # Start from a real band to preserve projection/mask/scale
    base = magnitude.multiply(0).toInt()

    # Build classification image (priority order — last wins)
    classified = (base
                  .where(activity_change, 4)
                  .where(infra_change, 3)
                  .where(seasonal_freeze, 2)
                  .where(seasonal_melt, 1)
                  .where(no_change, 0)
                  .rename('change_class'))

    return classified


def reduce_quadrant_stats(image, quad_fc, bands):
    """Reduce image bands to per-quadrant statistics in one GEE call."""
    reducer = (ee.Reducer.mean()
               .combine(ee.Reducer.median(), sharedInputs=True)
               .combine(ee.Reducer.stdDev(), sharedInputs=True)
               .combine(ee.Reducer.minMax(), sharedInputs=True)
               .combine(ee.Reducer.percentile([25, 75, 90, 95]),
                        sharedInputs=True))

    results = image.select(bands).reduceRegions(
        collection=quad_fc,
        reducer=reducer,
        scale=SCALE_M,
    ).getInfo()

    parsed = {}
    for feat in results.get('features', []):
        props = feat['properties']
        quad = props.get('quadrant', '?')
        parsed[quad] = props
    return parsed


def reduce_classification_counts(classified_img, quad_fc):
    """Count pixels per class per quadrant using frequencyHistogram.

    Single GEE call: reduceRegions with frequencyHistogram reducer.
    Returns dict: quad → {class_name: count, 'total': total_pixels}
    """
    CLASS_NAMES = {0: 'no_change', 1: 'seasonal_melt', 2: 'seasonal_freeze',
                   3: 'infrastructure', 4: 'potential_activity'}

    red = classified_img.reduceRegions(
        collection=quad_fc,
        reducer=ee.Reducer.frequencyHistogram(),
        scale=SCALE_M,
    ).getInfo()

    results = {}
    for feat in red.get('features', []):
        props = feat['properties']
        quad = props.get('quadrant', '?')
        # reduceRegions puts frequencyHistogram output under 'histogram' key
        # (not the band name, unlike reduceRegion)
        hist = props.get('histogram', props.get('change_class', {}))
        # hist is {str(class_val): count, ...}
        parsed = {}
        total = 0
        for cls_str, cnt in hist.items():
            try:
                cls_val = int(float(cls_str))
            except (ValueError, TypeError):
                continue
            cls_name = CLASS_NAMES.get(cls_val, f'class_{cls_val}')
            parsed[cls_name] = int(cnt)
            total += int(cnt)

        # Fill in missing classes with 0
        for cls_name in CLASS_NAMES.values():
            if cls_name not in parsed:
                parsed[cls_name] = 0
        parsed['total'] = total
        results[quad] = parsed

    return results


def generate_thumbnail_url(image, roi, vis_params, dimensions=512):
    """Generate a thumbnail URL for an EE image."""
    try:
        url = image.getThumbURL({
            'region': roi,
            'dimensions': dimensions,
            **vis_params,
        })
        return url
    except Exception as e:
        return f"ERROR: {e}"


def download_thumbnail(url, path):
    """Download a thumbnail image from EE URL."""
    try:
        import urllib.request
        urllib.request.urlretrieve(url, path)
        return True
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


# ================================================================
# LOAD SEASONAL PROFILES FOR DESEASONALIZED COMPARISON
# ================================================================
print("\n" + "─" * 76)
print("Loading seasonal profiles from NB 20...")
print("─" * 76)

seasonal_lookup = {}
profile_csv = os.path.join(SAT_DATA, 'seasonal_profiles.csv')
if os.path.exists(profile_csv):
    with open(profile_csv) as f:
        for row in csv.DictReader(f):
            site = row['site']
            woy = int(row['week_of_year'])
            seasonal_lookup[(site, woy)] = row
    print(f"  ✓ Loaded {len(seasonal_lookup)} seasonal profiles")
else:
    print("  ⚠ seasonal_profiles.csv not found — skipping deseasonalized analysis")
    print("    Run notebook 20 first to generate seasonal baselines")


# ================================================================
# PHASE 1: Find cleanest image pairs
# ================================================================
print("\n" + "=" * 76)
print("PHASE 1: Finding Cleanest S2 Image Pairs (Feb & Mar 2026)")
print("=" * 76)

image_pairs = {}

for site_name, site_info in SITES.items():
    print(f"\n  {site_name} ({site_info['description']})")
    roi = make_roi(site_info['center'])

    # Find Feb and Mar images
    feb_coll = find_cleanest_images(roi, FEB_START, FEB_END, n=2)
    mar_coll = find_cleanest_images(roi, MAR_START, MAR_END, n=2)

    feb_meta = get_image_metadata(feb_coll)
    mar_meta = get_image_metadata(mar_coll)

    print(f"    Feb images ({len(feb_meta)}):")
    for m in feb_meta:
        print(f"      {m['date']}  cloud: {m['cloud_pct']:.1f}%")

    print(f"    Mar images ({len(mar_meta)}):")
    for m in mar_meta:
        print(f"      {m['date']}  cloud: {m['cloud_pct']:.1f}%")

    if not feb_meta or not mar_meta:
        print(f"    ✗ Insufficient images — need at least 1 per month")
        continue

    # Use cleanest Feb as before, cleanest Mar as after
    # Apply cloud mask and compute indices
    before_raw = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(roi)
                  .filterDate(FEB_START, FEB_END)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD_PCT))
                  .sort('CLOUDY_PIXEL_PERCENTAGE')
                  .first())

    after_raw = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                 .filterBounds(roi)
                 .filterDate(MAR_START, MAR_END)
                 .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD_PCT))
                 .sort('CLOUDY_PIXEL_PERCENTAGE')
                 .first())

    before = add_spectral_indices(mask_clouds_scl(before_raw))
    after = add_spectral_indices(mask_clouds_scl(after_raw))

    image_pairs[site_name] = {
        'before': before,
        'after': after,
        'before_raw': before_raw,
        'after_raw': after_raw,
        'before_date': feb_meta[0]['date'],
        'after_date': mar_meta[0]['date'],
        'before_cloud': feb_meta[0]['cloud_pct'],
        'after_cloud': mar_meta[0]['cloud_pct'],
        'roi': roi,
    }

    print(f"    ✓ Pair: {feb_meta[0]['date']} → {mar_meta[0]['date']}")

if not image_pairs:
    print("\n  ✗ No valid image pairs found. Cannot proceed.")
    sys.exit(1)


# ================================================================
# PHASE 2: Compute change images
# ================================================================
print("\n" + "=" * 76)
print("PHASE 2: Computing Per-Pixel Change (Server-Side)")
print("=" * 76)

change_images = {}

for site_name, pair in image_pairs.items():
    print(f"\n  {site_name}: {pair['before_date']} → {pair['after_date']}")
    t0 = time.time()

    change = compute_change_image(pair['before'], pair['after'])
    classified = classify_change_pixels(change, pair['before'], pair['after'])

    change_images[site_name] = {
        'change': change,
        'classified': classified,
    }
    print(f"    ✓ Change image computed ({time.time()-t0:.1f}s)")


# ================================================================
# PHASE 3: Per-quadrant change statistics
# ================================================================
print("\n" + "=" * 76)
print("PHASE 3: Per-Quadrant Change Statistics")
print("=" * 76)

all_quad_stats = {}

for site_name, pair in image_pairs.items():
    print(f"\n{'─' * 70}")
    print(f"{site_name}: {pair['before_date']} → {pair['after_date']}")
    print(f"{'─' * 70}")

    lon, lat = SITES[site_name]['center']
    quad_fc = make_quadrant_fc(lon, lat)
    change = change_images[site_name]['change']

    # Reduce change bands to quadrant stats
    delta_bands = [f'delta_{idx}' for idx in INDEX_NAMES]
    stats_bands = delta_bands + ['change_magnitude']

    t0 = time.time()
    quad_stats = reduce_quadrant_stats(change, quad_fc, stats_bands)
    elapsed = time.time() - t0
    print(f"  Reduced in {elapsed:.0f}s")

    all_quad_stats[site_name] = quad_stats

    # Print spectral index changes per quadrant
    print(f"\n  {'Quad':>4}  {'ΔNDVI':>8}  {'ΔBSI':>8}  {'ΔNDBI':>8}  "
          f"{'ΔFuel':>8}  {'ΔMetal':>8}  {'ChgMag':>8}")
    print(f"  {'─'*4}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}")

    for quad in QUADRANT_NAMES:
        qs = quad_stats.get(quad, {})
        vals = []
        for idx in INDEX_NAMES:
            key = f'delta_{idx}_median'
            v = qs.get(key)
            vals.append(f"{v:+8.4f}" if v is not None else f"{'—':>8}")
        mag = qs.get('change_magnitude_median')
        mag_s = f"{mag:8.0f}" if mag is not None else f"{'—':>8}"
        print(f"  {quad:>4}  {'  '.join(vals)}  {mag_s}")


# ================================================================
# PHASE 4: Before/After absolute values per quadrant
# ================================================================
print("\n" + "=" * 76)
print("PHASE 4: Before/After Absolute Index Values per Quadrant")
print("=" * 76)

before_after_stats = {}

for site_name, pair in image_pairs.items():
    print(f"\n{'─' * 70}")
    print(f"{site_name}")
    print(f"{'─' * 70}")

    lon, lat = SITES[site_name]['center']
    quad_fc = make_quadrant_fc(lon, lat)

    # Reduce before image
    t0 = time.time()
    before_qs = reduce_quadrant_stats(pair['before'], quad_fc, INDEX_NAMES)
    after_qs = reduce_quadrant_stats(pair['after'], quad_fc, INDEX_NAMES)
    print(f"  Reduced in {time.time()-t0:.0f}s")

    before_after_stats[site_name] = {'before': before_qs, 'after': after_qs}

    for idx in INDEX_NAMES:
        print(f"\n  {idx.upper()}")
        print(f"  {'Quad':>4}  {'Before':>10}  {'After':>10}  {'Delta':>10}  {'Interp'}")
        print(f"  {'─'*4}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*30}")
        for quad in QUADRANT_NAMES:
            b = before_qs.get(quad, {}).get(f'{idx}_median')
            a = after_qs.get(quad, {}).get(f'{idx}_median')
            if b is not None and a is not None:
                d = a - b
                # Interpret change
                if idx == 'ndvi' and d > 0.08:
                    interp = "← snowmelt/vegetation onset"
                elif idx == 'ndvi' and d < -0.08:
                    interp = "← vegetation loss"
                elif idx == 'bsi' and abs(d) > 0.05:
                    interp = "← ground/infrastructure change"
                elif idx == 'fuel_ratio' and abs(d) > 0.02:
                    interp = "← fuel signature change"
                elif idx == 'metal_ratio' and abs(d) > 0.3:
                    interp = "← metal signature change"
                else:
                    interp = "stable"
                print(f"  {quad:>4}  {b:>10.4f}  {a:>10.4f}  {d:>+10.4f}  {interp}")
            else:
                print(f"  {quad:>4}  {'—':>10}  {'—':>10}  {'—':>10}")


# ================================================================
# PHASE 5: Change classification distribution per quadrant
# ================================================================
print("\n" + "=" * 76)
print("PHASE 5: Change Classification per Quadrant")
print("=" * 76)
print("""
  Classes:
    0 = no_change           (magnitude < 500 AND |ΔNDVI| < 0.08)
    1 = seasonal_melt       (NDVI↑ from snow→vegetation)
    2 = seasonal_freeze     (NDVI↓ to <0.12)
    3 = infrastructure      (|ΔBSI| > 0.05, non-seasonal)
    4 = potential_activity   (fuel or metal change, non-seasonal)
""")

all_class_stats = {}

for site_name in image_pairs:
    print(f"\n{'─' * 70}")
    print(f"{site_name}")
    print(f"{'─' * 70}")

    lon, lat = SITES[site_name]['center']
    quad_fc = make_quadrant_fc(lon, lat)
    classified = change_images[site_name]['classified']

    t0 = time.time()
    class_stats = reduce_classification_counts(classified, quad_fc)
    print(f"  Reduced in {time.time()-t0:.0f}s")

    all_class_stats[site_name] = class_stats

    print(f"\n  {'Quad':>4}  {'Total':>8}  {'NoCh':>8}  {'Melt':>8}  "
          f"{'Frz':>8}  {'Infra':>8}  {'Activ':>8}")
    print(f"  {'─'*4}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}")

    for quad in QUADRANT_NAMES:
        cs = class_stats.get(quad, {})
        total = cs.get('total', 1)
        if total == 0:
            total = 1
        nc = cs.get('no_change', 0)
        ml = cs.get('seasonal_melt', 0)
        fr = cs.get('seasonal_freeze', 0)
        inf = cs.get('infrastructure', 0)
        act = cs.get('potential_activity', 0)
        print(f"  {quad:>4}  {total:>8.0f}  "
              f"{nc:>7.0f}  {ml:>7.0f}  {fr:>7.0f}  "
              f"{inf:>7.0f}  {act:>7.0f}")

    # Print percentages
    print(f"\n  {'Quad':>4}  {'NoCh%':>8}  {'Melt%':>8}  {'Frz%':>8}  "
          f"{'Infra%':>8}  {'Activ%':>8}  {'Seasonal%':>10}")
    print(f"  {'─'*4}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*10}")

    for quad in QUADRANT_NAMES:
        cs = class_stats.get(quad, {})
        total = cs.get('total', 1) or 1
        nc = 100 * cs.get('no_change', 0) / total
        ml = 100 * cs.get('seasonal_melt', 0) / total
        fr = 100 * cs.get('seasonal_freeze', 0) / total
        inf = 100 * cs.get('infrastructure', 0) / total
        act = 100 * cs.get('potential_activity', 0) / total
        seasonal = ml + fr
        flag = ""
        if act > 5:
            flag = " ← INVESTIGATE"
        elif inf > 10:
            flag = " ← check"
        print(f"  {quad:>4}  {nc:>7.1f}%  {ml:>7.1f}%  {fr:>7.1f}%  "
              f"{inf:>7.1f}%  {act:>7.1f}%  {seasonal:>9.1f}%{flag}")


# ================================================================
# PHASE 6: Deseasonalized anomaly comparison (using NB 20 profiles)
# ================================================================
print("\n" + "=" * 76)
print("PHASE 6: Deseasonalized Anomaly Comparison (vs Seasonal Profiles)")
print("=" * 76)

if not seasonal_lookup:
    print("  ⚠ Skipped — no seasonal profiles loaded")
else:
    print("""
  Using NB 20 seasonal profiles to determine if Feb→Mar changes
  are within normal seasonal bounds.

  z_feb = (Feb observed - expected(week_feb)) / robust_std(week_feb)
  z_mar = (Mar observed - expected(week_mar)) / robust_std(week_mar)

  If both z < 2.0: change is normal seasonal variation
  If z_mar > 2.0 but z_feb normal: Mar has anomalous value (new activity?)
  If both z > 2.0: site is anomalous in both months (ongoing anomaly)
""")

    for site_name, pair in image_pairs.items():
        print(f"\n{'─' * 70}")
        print(f"{site_name}")
        print(f"{'─' * 70}")

        # Get week-of-year for before and after dates
        before_dt = datetime.strptime(pair['before_date'], "%Y-%m-%d")
        after_dt = datetime.strptime(pair['after_date'], "%Y-%m-%d")
        _, woy_before, _ = before_dt.isocalendar()
        _, woy_after, _ = after_dt.isocalendar()

        before_profile = seasonal_lookup.get((site_name, woy_before))
        after_profile = seasonal_lookup.get((site_name, woy_after))

        if not before_profile or not after_profile:
            print(f"  ⚠ No profile for weeks {woy_before}/{woy_after}")
            continue

        print(f"  Before: {pair['before_date']} (week {woy_before})")
        print(f"  After:  {pair['after_date']} (week {woy_after})")
        print()
        print(f"  {'Index':<13}  {'FebObs':>8}  {'FebExp':>8}  {'z_feb':>7}  "
              f"{'MarObs':>8}  {'MarExp':>8}  {'z_mar':>7}  {'Verdict'}")
        print(f"  {'─'*13}  {'─'*8}  {'─'*8}  {'─'*7}  "
              f"{'─'*8}  {'─'*8}  {'─'*7}  {'─'*20}")

        # Use whole-site median from before/after images
        lon, lat = SITES[site_name]['center']
        roi = pair['roi']

        before_stats = pair['before'].select(INDEX_NAMES).reduceRegion(
            reducer=ee.Reducer.median(), geometry=roi,
            scale=SCALE_M, maxPixels=1e6, bestEffort=True
        ).getInfo()

        after_stats = pair['after'].select(INDEX_NAMES).reduceRegion(
            reducer=ee.Reducer.median(), geometry=roi,
            scale=SCALE_M, maxPixels=1e6, bestEffort=True
        ).getInfo()

        for idx in INDEX_NAMES:
            feb_obs = before_stats.get(idx)
            mar_obs = after_stats.get(idx)
            feb_exp_key = f'{idx}_expected'
            feb_std_key = f'{idx}_robust_std'

            feb_exp = float(before_profile.get(feb_exp_key, 'nan'))
            feb_std = float(before_profile.get(feb_std_key, 'nan'))
            mar_exp = float(after_profile.get(feb_exp_key, 'nan'))
            mar_std = float(after_profile.get(feb_std_key, 'nan'))

            if (feb_obs is None or mar_obs is None
                    or math.isnan(feb_exp) or math.isnan(mar_exp)):
                print(f"  {idx:<13}  {'—':>8}  {'—':>8}  {'—':>7}  "
                      f"{'—':>8}  {'—':>8}  {'—':>7}  insufficient data")
                continue

            z_feb = ((feb_obs - feb_exp) / feb_std) if feb_std > 1e-6 else 0.0
            z_mar = ((mar_obs - mar_exp) / mar_std) if mar_std > 1e-6 else 0.0

            if abs(z_feb) < 2.0 and abs(z_mar) < 2.0:
                verdict = "NORMAL seasonal"
            elif abs(z_feb) < 2.0 and abs(z_mar) >= 2.0:
                verdict = "⚠ Mar ANOMALOUS"
            elif abs(z_feb) >= 2.0 and abs(z_mar) < 2.0:
                verdict = "⚠ Feb ANOMALOUS"
            else:
                verdict = "⚠ BOTH anomalous"

            print(f"  {idx:<13}  {feb_obs:>8.4f}  {feb_exp:>8.4f}  {z_feb:>+7.2f}  "
                  f"{mar_obs:>8.4f}  {mar_exp:>8.4f}  {z_mar:>+7.2f}  {verdict}")


# ================================================================
# PHASE 7: Generate change heatmap thumbnails
# ================================================================
print("\n" + "=" * 76)
print("PHASE 7: Change Heatmap Thumbnails")
print("=" * 76)

THUMB_DIR = os.path.join(OUTPUT, 'change_heatmaps')
os.makedirs(THUMB_DIR, exist_ok=True)

HEATMAP_VIS = {
    'change_magnitude': {
        'bands': ['change_magnitude'],
        'min': 0, 'max': 3000,
        'palette': ['000000', '1a1a2e', '16213e', '0f3460', 'e94560',
                     'ff6b6b', 'ffd93d', 'ffffff'],
    },
    'ndvi_change': {
        'bands': ['delta_ndvi'],
        'min': -0.3, 'max': 0.3,
        'palette': ['8b0000', 'ff4500', 'ff8c00', 'ffd700', 'f0f0f0',
                     '90ee90', '32cd32', '006400'],
    },
    'bsi_change': {
        'bands': ['delta_bsi'],
        'min': -0.2, 'max': 0.2,
        'palette': ['0000ff', '4169e1', '87ceeb', 'f0f0f0',
                     'deb887', 'cd853f', '8b4513'],
    },
    'fuel_change': {
        'bands': ['delta_fuel_ratio'],
        'min': -0.1, 'max': 0.1,
        'palette': ['006400', '32cd32', '90ee90', 'f0f0f0',
                     'ffb347', 'ff6600', 'cc0000'],
    },
    'classification': {
        'bands': ['change_class'],
        'min': 0, 'max': 4,
        'palette': ['333333', '00ff00', '00bfff', 'ff8c00', 'ff0000'],
    },
}

# Also generate RGB before/after
RGB_VIS = {
    'bands': ['B4', 'B3', 'B2'],
    'min': 0, 'max': 3000,
}

thumbnail_urls = {}

for site_name, pair in image_pairs.items():
    print(f"\n  {site_name}:")
    roi = pair['roi']
    change = change_images[site_name]['change']
    classified = change_images[site_name]['classified']

    site_urls = {}

    # RGB before/after
    for label, img in [('before_rgb', pair['before_raw']),
                       ('after_rgb', pair['after_raw'])]:
        url = generate_thumbnail_url(img, roi, RGB_VIS, dimensions=512)
        fname = f"{site_name}_{label}.png"
        fpath = os.path.join(THUMB_DIR, fname)
        ok = download_thumbnail(url, fpath)
        if ok:
            print(f"    ✓ {fname}")
        else:
            print(f"    ✗ {fname} — saving URL only")
        site_urls[label] = url

    # Change heatmaps
    for heatmap_name, vis in HEATMAP_VIS.items():
        if heatmap_name == 'classification':
            img = classified
        else:
            img = change

        url = generate_thumbnail_url(img, roi, vis, dimensions=512)
        fname = f"{site_name}_{heatmap_name}.png"
        fpath = os.path.join(THUMB_DIR, fname)
        ok = download_thumbnail(url, fpath)
        if ok:
            print(f"    ✓ {fname}")
        else:
            print(f"    ✗ {fname} — saving URL only")
        site_urls[heatmap_name] = url

    thumbnail_urls[site_name] = site_urls


# ================================================================
# PHASE 8: Export change statistics to CSV
# ================================================================
print("\n" + "=" * 76)
print("PHASE 8: Exporting Change Statistics")
print("=" * 76)

# 8a. Quadrant change statistics
stats_csv = os.path.join(SAT_DATA, 'temporal_change_stats.csv')
rows = []
for site_name in image_pairs:
    pair = image_pairs[site_name]
    qs = all_quad_stats.get(site_name, {})
    for quad in QUADRANT_NAMES:
        q = qs.get(quad, {})
        row = {
            'site': site_name,
            'quadrant': quad,
            'before_date': pair['before_date'],
            'after_date': pair['after_date'],
        }
        for idx in INDEX_NAMES:
            for stat in ['mean', 'median', 'stdDev']:
                key = f'delta_{idx}_{stat}'
                row[f'{idx}_delta_{stat}'] = q.get(key)
        row['change_magnitude_median'] = q.get('change_magnitude_median')
        row['change_magnitude_mean'] = q.get('change_magnitude_mean')
        row['change_magnitude_p90'] = q.get('change_magnitude_p90')
        rows.append(row)

if rows:
    fields = list(rows[0].keys())
    with open(stats_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓ {stats_csv} ({len(rows)} rows)")

# 8b. Classification counts
class_csv = os.path.join(SAT_DATA, 'temporal_change_classes.csv')
class_rows = []
for site_name in image_pairs:
    pair = image_pairs[site_name]
    cs = all_class_stats.get(site_name, {})
    for quad in QUADRANT_NAMES:
        c = cs.get(quad, {})
        total = c.get('total', 1) or 1
        class_rows.append({
            'site': site_name,
            'quadrant': quad,
            'before_date': pair['before_date'],
            'after_date': pair['after_date'],
            'total_pixels': total,
            'no_change': c.get('no_change', 0),
            'seasonal_melt': c.get('seasonal_melt', 0),
            'seasonal_freeze': c.get('seasonal_freeze', 0),
            'infrastructure': c.get('infrastructure', 0),
            'potential_activity': c.get('potential_activity', 0),
            'seasonal_pct': 100 * (c.get('seasonal_melt', 0)
                                   + c.get('seasonal_freeze', 0)) / total,
            'nonseasonal_pct': 100 * (c.get('infrastructure', 0)
                                      + c.get('potential_activity', 0)) / total,
        })

if class_rows:
    fields = list(class_rows[0].keys())
    with open(class_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(class_rows)
    print(f"  ✓ {class_csv} ({len(class_rows)} rows)")

# 8c. Thumbnail URL index
url_json = os.path.join(OUTPUT, 'change_heatmap_urls.json')
url_data = {}
for site_name, urls in thumbnail_urls.items():
    url_data[site_name] = {
        'before_date': image_pairs[site_name]['before_date'],
        'after_date': image_pairs[site_name]['after_date'],
        'thumbnails': urls,
    }
with open(url_json, 'w') as f:
    json.dump(url_data, f, indent=2)
print(f"  ✓ {url_json}")


# ================================================================
# PHASE 9: Comprehensive comparison table
# ================================================================
print("\n" + "=" * 76)
print("PHASE 9: Comprehensive Change Summary")
print("=" * 76)

for site_name in image_pairs:
    pair = image_pairs[site_name]
    print(f"\n{'━' * 76}")
    print(f"  {site_name} — {pair['before_date']} → {pair['after_date']}")
    print(f"  ({pair['before_cloud']:.1f}% cloud → {pair['after_cloud']:.1f}% cloud)")
    print(f"{'━' * 76}")

    cs = all_class_stats.get(site_name, {})

    # Overall site stats
    total_px = sum(cs.get(q, {}).get('total', 0) for q in QUADRANT_NAMES)
    total_melt = sum(cs.get(q, {}).get('seasonal_melt', 0) for q in QUADRANT_NAMES)
    total_frz = sum(cs.get(q, {}).get('seasonal_freeze', 0) for q in QUADRANT_NAMES)
    total_infra = sum(cs.get(q, {}).get('infrastructure', 0) for q in QUADRANT_NAMES)
    total_act = sum(cs.get(q, {}).get('potential_activity', 0)
                    for q in QUADRANT_NAMES)
    total_nc = sum(cs.get(q, {}).get('no_change', 0) for q in QUADRANT_NAMES)

    total_px = max(total_px, 1)
    seasonal_pct = 100 * (total_melt + total_frz) / total_px
    nonseasonal_pct = 100 * (total_infra + total_act) / total_px

    print(f"\n  Overall pixel classification:")
    print(f"    No change:          {total_nc:>6}  ({100*total_nc/total_px:.1f}%)")
    print(f"    Seasonal melt:      {total_melt:>6}  ({100*total_melt/total_px:.1f}%)")
    print(f"    Seasonal freeze:    {total_frz:>6}  ({100*total_frz/total_px:.1f}%)")
    print(f"    Infrastructure:     {total_infra:>6}  ({100*total_infra/total_px:.1f}%)")
    print(f"    Potential activity:  {total_act:>6}  ({100*total_act/total_px:.1f}%)")
    print(f"    ─────────────────────────────────────")
    print(f"    Seasonal total:     {seasonal_pct:.1f}%")
    print(f"    Non-seasonal total: {nonseasonal_pct:.1f}%")

    # Hotspot identification
    print(f"\n  Hotspot quadrants (non-seasonal change > 5%):")
    hotspots = []
    for quad in QUADRANT_NAMES:
        c = cs.get(quad, {})
        qtotal = c.get('total', 1) or 1
        q_ns = (c.get('infrastructure', 0) + c.get('potential_activity', 0))
        q_ns_pct = 100 * q_ns / qtotal
        if q_ns_pct > 5:
            hotspots.append((quad, q_ns_pct, c.get('infrastructure', 0),
                             c.get('potential_activity', 0)))
    if hotspots:
        for quad, pct, infra, act in sorted(hotspots, key=lambda x: -x[1]):
            print(f"    {quad}: {pct:.1f}% non-seasonal "
                  f"(infra={infra}, activity={act})")
    else:
        print(f"    None — all quadrants below 5% non-seasonal change")


# ================================================================
# PHASE 10: Cross-reference with manual comparison JSON
# ================================================================
print("\n" + "=" * 76)
print("PHASE 10: Cross-Reference with Manual Luga Comparison")
print("=" * 76)

manual_json = os.path.join(SCRIPT_DIR, '..', 'satellite-analysis', 'outputs',
                           '04-sentinel2-comparison', 'luga-temporal-comparison.json')
if os.path.exists(manual_json):
    with open(manual_json) as f:
        manual = json.load(f)

    print(f"\n  Manual comparison: {manual.get('comparison', '?')}")
    print(f"\n  {'Metric':<15} {'Manual Feb':>12} {'Manual Mar':>12} "
          f"{'Auto Feb':>12} {'Auto Mar':>12} {'Match?':>8}")
    print(f"  {'─'*15} {'─'*12} {'─'*12} {'─'*12} {'─'*12} {'─'*8}")

    # Get automated Luga whole-site values
    if 'Luga' in image_pairs:
        luga_pair = image_pairs['Luga']
        auto_before = luga_pair['before'].select(INDEX_NAMES).reduceRegion(
            reducer=ee.Reducer.median(), geometry=luga_pair['roi'],
            scale=SCALE_M, maxPixels=1e6, bestEffort=True
        ).getInfo()
        auto_after = luga_pair['after'].select(INDEX_NAMES).reduceRegion(
            reducer=ee.Reducer.median(), geometry=luga_pair['roi'],
            scale=SCALE_M, maxPixels=1e6, bestEffort=True
        ).getInfo()

        feb_man = manual.get('feb01', {})
        mar_man = manual.get('mar21', {})

        comparisons = [
            ('ndvi_mean', 'ndvi', 'ndvi'),
            ('bsi_mean', 'bsi', 'bsi'),
            ('metal_pct', None, None),   # different metric
            ('fuel_pct', None, None),    # different metric
        ]

        for man_key, auto_key_b, auto_key_a in comparisons:
            mv_b = feb_man.get(man_key)
            mv_a = mar_man.get(man_key)
            if auto_key_b and auto_key_a:
                av_b = auto_before.get(auto_key_b)
                av_a = auto_after.get(auto_key_a)
                if mv_b is not None and av_b is not None:
                    match = "~" if abs(mv_b - av_b) < 0.1 else "✗"
                else:
                    match = "—"
                b_str = f"{av_b:.4f}" if av_b is not None else "—"
                a_str = f"{av_a:.4f}" if av_a is not None else "—"
                print(f"  {man_key:<15} {mv_b:>12} {mv_a:>12} "
                      f"{b_str:>12} {a_str:>12} {match:>8}")
            else:
                print(f"  {man_key:<15} {mv_b:>12} {mv_a:>12} "
                      f"{'(diff unit)':>12} {'(diff unit)':>12} {'—':>8}")

    print(f"\n  Manual assessment: \"{manual.get('assessment', 'N/A')}\"")
else:
    print("  Manual comparison JSON not found — skipping")


# ================================================================
# FINAL SUMMARY
# ================================================================
print("\n" + "=" * 76)
print("FINAL SUMMARY")
print("=" * 76)

print(f"""
Sites analyzed: {len(image_pairs)}
""")

for site_name, pair in image_pairs.items():
    cs = all_class_stats.get(site_name, {})
    total_px = max(sum(cs.get(q, {}).get('total', 0) for q in QUADRANT_NAMES), 1)
    total_melt = sum(cs.get(q, {}).get('seasonal_melt', 0) for q in QUADRANT_NAMES)
    total_frz = sum(cs.get(q, {}).get('seasonal_freeze', 0) for q in QUADRANT_NAMES)
    total_infra = sum(cs.get(q, {}).get('infrastructure', 0) for q in QUADRANT_NAMES)
    total_act = sum(cs.get(q, {}).get('potential_activity', 0)
                    for q in QUADRANT_NAMES)
    seasonal = 100 * (total_melt + total_frz) / total_px
    nonseasonal = 100 * (total_infra + total_act) / total_px

    print(f"  {site_name}:")
    print(f"    Period:       {pair['before_date']} → {pair['after_date']}")
    print(f"    Seasonal:     {seasonal:.1f}%")
    print(f"    Non-seasonal: {nonseasonal:.1f}%")
    print(f"    Assessment:   ", end="")
    if nonseasonal < 2:
        print("STABLE — changes dominated by seasonal snowmelt")
    elif nonseasonal < 10:
        print("MINOR changes — mostly seasonal with some infrastructure/activity")
    else:
        print("SIGNIFICANT non-seasonal changes — requires investigation")

print(f"""
Output files:
  {stats_csv}
  {class_csv}
  {url_json}
  {THUMB_DIR}/

Interpretation:
  Feb→Mar in Northwest Russia is dominated by spring thaw / snowmelt.
  Changes classified as 'seasonal_melt' are EXPECTED and NOT activity.
  Only 'infrastructure' and 'potential_activity' categories represent
  potentially significant changes requiring OSINT cross-reference.

  The deseasonalized z-scores (Phase 6) confirm whether observed values
  fall within historical seasonal bounds from NB 20's 3-year profiles.

Methodology:
  1. Server-side EE: image selection, cloud masking (SCL), spectral
     index computation, change detection, pixel classification
  2. Quadrant-level statistics via reduceRegions (single GEE call)
  3. Classification separates seasonal from non-seasonal via snow
     detection (NDVI<0.12, BSI<-0.15) and threshold-based rules
  4. Deseasonalized comparison uses NB 20 weekly seasonal profiles
     with robust_std (MAD×1.4826) for z-score computation
""")
