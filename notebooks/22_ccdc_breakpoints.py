#!/usr/bin/env python3
"""
22. CCDC Time Series Segmentation — Construction/Destruction Breakpoints
=========================================================================

Previous findings (FINDINGS.satellite-imagery.md):
  - Exp 09-14: Seasonal variation dominates raw spectral metrics
  - Recommendation: Run CCDC on 3-year S2 archive for breakpoint detection

  NB 20: Seasonal baselines (weekly median + MAD) for 5 sites
  NB 21: IsolationForest temporal baselines per quadrant

This notebook:
  1. Runs GEE CCDC on 3 sites (Pskov-76VDV, Luga, Kronstadt), 2023-2026
  2. Extracts breakpoint dates, magnitudes, and pixel density
  3. Classifies breakpoints by spectral signature
  4. Cross-references with ISW deployment dates
  5. Outputs FINDINGS.satellite-ccdc.md

CCDC (Zhu & Woodcock 2014) — harmonic regression per pixel, detects spectral
breaks. GEE runs this server-side. Output is an array image; we use
arrayGet([i]) to extract per-segment values as scalars.

Requires: earthengine-api, numpy
"""
import csv
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta

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
print("22. CCDC BREAKPOINT DETECTION — MILITARY SITE TEMPORAL SEGMENTATION")
print("=" * 76)

# ================================================================
# SITE DEFINITIONS
# ================================================================
SITES = {
    "Pskov-76VDV": {
        "center": [28.395, 57.785],
        "type": "airborne",
        "description": "76th Guards Air Assault Division airfield",
    },
    "Luga": {
        "center": [29.846, 58.737],
        "type": "garrison",
        "description": "Luga training ground and garrison",
    },
    "Kronstadt": {
        "center": [29.768, 59.988],
        "type": "naval",
        "description": "Kronstadt naval base — Baltic Fleet",
    },
}

ROI_RADIUS_M = 1000
DATE_START = "2023-01-01"
DATE_END = "2026-03-25"
MAX_CLOUD_PCT = 30
SCALE_M = 20

CCDC_BANDS = ['B4', 'B8', 'B11', 'B12']
BAND_LABELS = {'B4': 'Red', 'B8': 'NIR', 'B11': 'SWIR1', 'B12': 'SWIR2'}

CCDC_PARAMS = {
    'minObservations': 6,
    'chiSquareProbability': 0.95,
    'minNumOfYearsScaler': 0.5,
    'dateFormat': 1,  # fractional years
    'lambda': 20.0,
    'maxIterations': 25000,
}

QUADRANT_NAMES = ['NW', 'NE', 'SW', 'SE']

# ISW / OSINT known events for cross-referencing
KNOWN_EVENTS = [
    {"date": "2022-09-01", "site": "Pskov-76VDV",
     "event": "76th VDV deployed to Ukraine (ongoing)", "source": "ISW"},
    {"date": "2023-06-01", "site": "Pskov-76VDV",
     "event": "76th VDV heavy losses at Vuhledar", "source": "ISW/Mediazona"},
    {"date": "2024-06-01", "site": "Pskov-76VDV",
     "event": "76th VDV redeployed to Zaporizhia/Orikhiv", "source": "ISW Mar 2026"},
    {"date": "2025-10-01", "site": "Luga",
     "event": "26th Rocket Bde Iskander to Ukraine", "source": "Yle Oct 2025"},
    {"date": "2024-01-01", "site": "Luga",
     "event": "68th MR Div to Kupyansk", "source": "ISW Mar 2026"},
    {"date": "2023-01-01", "site": "Kronstadt",
     "event": "Baltic Fleet — 11th AC to Ukraine", "source": "ISW"},
    {"date": "2025-03-01", "site": "Kronstadt",
     "event": "11th AC 1431st+352nd MRRs at Kupyansk", "source": "ISW Mar 2026"},
]


def fracyear_to_date(fy):
    """Convert fractional year to YYYY-MM-DD."""
    if fy is None or fy == 0 or (isinstance(fy, float) and math.isnan(fy)):
        return None
    year = int(fy)
    frac = fy - year
    try:
        base = datetime(year, 1, 1)
        days = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
        return (base + timedelta(days=frac * days)).strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None


def make_roi(center, radius_m=ROI_RADIUS_M):
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


def mask_clouds_s2(image):
    scl = image.select('SCL')
    ok = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7)).Or(scl.eq(11))
    return image.updateMask(ok)


def build_s2_collection(roi):
    return (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(roi)
            .filterDate(DATE_START, DATE_END)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD_PCT))
            .map(mask_clouds_s2)
            .select(CCDC_BANDS))


def classify_breakpoint(mag_dict):
    """Classify breakpoint by spectral signature. Returns (class, conf, expl)."""
    b4 = mag_dict.get('B4')
    b8 = mag_dict.get('B8')
    b11 = mag_dict.get('B11')
    b12 = mag_dict.get('B12')

    vals = [v for v in [b4, b8, b11, b12] if v is not None]
    if len(vals) < 2:
        return 'insufficient_data', 0.0, 'Too few magnitude values'

    sig = 200
    if not any(abs(v) > sig for v in vals):
        return 'negligible_change', 0.1, f'All magnitudes < {sig}'

    if b8 is not None and b11 is not None:
        if b8 < -sig and b11 > sig:
            return ('vegetation_loss', 0.8,
                    f'NIR down({b8:.0f}) + SWIR1 up({b11:.0f}) = clearing')
        if b8 < -sig:
            return ('vegetation_loss', 0.6,
                    f'NIR down({b8:.0f}) = vegetation removal')
        if b8 > sig and b11 < 0:
            return ('vegetation_gain', 0.7,
                    f'NIR up({b8:.0f}) = regrowth')
        if b8 > 500 and b11 > 300:
            return ('metal_increase', 0.7,
                    f'NIR up({b8:.0f}) + SWIR1 up({b11:.0f}) = metal')

    if b11 is not None and b4 is not None and b8 is not None:
        bsi = (b11 + b4) - b8
        if bsi > sig * 2:
            return ('BSI_increase', 0.7, f'BSI proxy up({bsi:.0f}) = earthwork')

    if b11 is not None and abs(b11) > 1000:
        d = "melt" if b11 > 0 else "accumulation"
        return ('snow_transition', 0.5, f'SWIR1 delta({b11:.0f}) = snow {d}')

    max_mag = max(abs(v) for v in vals)
    if max_mag > 500:
        dom = max([(b, v) for b, v in mag_dict.items() if v is not None],
                  key=lambda x: abs(x[1]))
        return ('significant_change', 0.4,
                f'Dominant: {BAND_LABELS.get(dom[0], dom[0])} ({dom[1]:.0f})')

    return 'unclassified', 0.2, f'Max magnitude: {max_mag:.0f}'


# ================================================================
# PHASE 1: Run CCDC per site
# ================================================================
print("\n" + "=" * 76)
print("PHASE 1: Running CCDC on 3 sites (GEE server-side)")
print("=" * 76)
print(f"""
  chiSquareProbability: {CCDC_PARAMS['chiSquareProbability']}
  bands: {CCDC_BANDS}
  date range: {DATE_START} to {DATE_END}
  scale: {SCALE_M}m
""")

ccdc_results = {}

for site_name, site_info in SITES.items():
    print(f"  {site_name}... ", end="", flush=True)
    t0 = time.time()
    try:
        roi = make_roi(site_info['center'])
        collection = build_s2_collection(roi)
        n_images = collection.size().getInfo()
        print(f"{n_images} images... ", end="", flush=True)

        if n_images < 20:
            print(f"SKIPPED (need >=20)")
            continue

        ccdc = ee.Algorithms.TemporalSegmentation.Ccdc(**{
            'collection': collection,
            'breakpointBands': CCDC_BANDS,
            **CCDC_PARAMS,
        })

        ccdc_results[site_name] = {'ccdc': ccdc, 'roi': roi, 'n_images': n_images}
        print(f"OK ({time.time()-t0:.0f}s)")

    except Exception as e:
        print(f"FAILED: {e}")

if not ccdc_results:
    print("\n  ✗ No sites processed")
    sys.exit(1)


# ================================================================
# PHASE 2: Extract breakpoints — optimized single-call per site
# ================================================================
print("\n" + "=" * 76)
print("PHASE 2: Extracting breakpoints (batched per site)")
print("=" * 76)
print("""
  Strategy: Build a flat multi-band scalar image from CCDC arrays,
  then reduceRegions() across all 4 quadrants in ONE GEE call per site.
  This minimizes roundtrips to the GEE server.
""")

all_breakpoints = []
density_data = []

for site_name, site_data in ccdc_results.items():
    print(f"\n{'─' * 70}")
    print(f"{site_name}")
    print(f"{'─' * 70}")
    t0 = time.time()

    ccdc = site_data['ccdc']
    roi = site_data['roi']
    lon, lat = SITES[site_name]['center']
    quad_fc = make_quadrant_fc(lon, lat)

    try:
        # Check max segments
        max_segs_dict = ccdc.select('tBreak').arrayLength(0).reduceRegion(
            reducer=ee.Reducer.max(),
            geometry=roi, scale=SCALE_M, maxPixels=1e6, bestEffort=True,
        ).getInfo()
        max_segs = int(list(max_segs_dict.values())[0])
        print(f"  Max segments per pixel: {max_segs}")

        # Build a flat scalar image with all break info
        # For break 0: tBreak_0, B4_mag_0, B8_mag_0, B11_mag_0, B12_mag_0, has_break_0
        arr_len = ccdc.select('tBreak').arrayLength(0)

        flat_bands = []
        break_band_names = []
        n_breaks = min(max_segs, 3)

        for bi in range(n_breaks):
            has_idx = arr_len.gt(bi)

            tb = (ccdc.select('tBreak').arrayGet([bi])
                  .updateMask(has_idx).rename(f'tBreak_{bi}'))
            has_brk = tb.gt(0).rename(f'has_break_{bi}')

            flat_bands.extend([tb, has_brk])
            break_band_names.append(f'tBreak_{bi}')

            for band in CCDC_BANDS:
                mag = (ccdc.select(f'{band}_magnitude').arrayGet([bi])
                       .updateMask(has_idx).rename(f'{band}_mag_{bi}'))
                flat_bands.append(mag)

        # Add total pixel count band (always 1 where data exists)
        px_band = arr_len.gt(0).rename('has_data').toInt()
        flat_bands.append(px_band)

        flat_img = ee.Image.cat(flat_bands)

        # Single reduceRegions call — all quadrants at once
        reducer = ee.Reducer.median().combine(
            ee.Reducer.sum(), sharedInputs=True
        ).combine(
            ee.Reducer.count(), sharedInputs=True
        )

        print(f"  Reducing across 4 quadrants... ", end="", flush=True)
        results = flat_img.reduceRegions(
            collection=quad_fc,
            reducer=reducer,
            scale=SCALE_M,
        ).getInfo()
        elapsed = time.time() - t0
        print(f"done ({elapsed:.0f}s)")

        # Parse results per quadrant
        for feat in results.get('features', []):
            props = feat['properties']
            quad = props.get('quadrant', '?')
            total_px = props.get('has_data_count', 1)

            for bi in range(n_breaks):
                # Pixels with this break: sum of has_break_bi
                n_break_px = props.get(f'has_break_{bi}_sum', 0)
                if n_break_px < 1:
                    continue

                tbreak_val = props.get(f'tBreak_{bi}_median')
                if not tbreak_val or tbreak_val <= 0:
                    continue

                break_date = fracyear_to_date(tbreak_val)
                break_pct = 100 * n_break_px / max(total_px, 1)

                mags = {}
                for band in CCDC_BANDS:
                    mags[band] = props.get(f'{band}_mag_{bi}_median')

                cls, conf, expl = classify_breakpoint(mags)

                bp = {
                    'site': site_name, 'quadrant': quad,
                    'break_index': bi, 'break_date': break_date or '?',
                    'break_fracyear': tbreak_val,
                    'break_pixel_pct': break_pct,
                    'n_pixels': n_break_px, 'n_total': total_px,
                    'class': cls, 'confidence': conf, 'explanation': expl,
                }
                bp.update({f'mag_{b}': mags.get(b) for b in CCDC_BANDS})
                all_breakpoints.append(bp)

                print(f"    {quad} break[{bi}]: {break_date} "
                      f"({break_pct:.0f}% px) — {cls}")
                mag_str = ', '.join(
                    f'{BAND_LABELS[b]}={mags[b]:.0f}'
                    for b in CCDC_BANDS if mags.get(b) is not None)
                print(f"      magnitudes: {mag_str}")

            # Density for break 0
            n_b0 = props.get('has_break_0_sum', 0)
            density_data.append({
                'site': site_name, 'quadrant': quad,
                'total_pixels': total_px,
                'pixels_with_break': n_b0,
                'density_pct': 100 * n_b0 / max(total_px, 1),
            })

    except Exception as e:
        print(f"  ERROR: {e}")

print(f"\n  Total zonal breakpoints: {len(all_breakpoints)}")


# ================================================================
# PHASE 3: Point-based sampling (center pixel per site)
# ================================================================
print("\n" + "=" * 76)
print("PHASE 3: Point-based breakpoint sampling")
print("=" * 76)

point_breakpoints = []

for site_name, site_data in ccdc_results.items():
    print(f"\n  {site_name}:")
    ccdc = site_data['ccdc']
    lon, lat = SITES[site_name]['center']

    lat_d = ROI_RADIUS_M / 111000 * 0.5
    lon_d = ROI_RADIUS_M / (111000 * math.cos(math.radians(lat))) * 0.5

    sample_points = {
        'center': [lon, lat],
        'NW': [lon - lon_d, lat + lat_d],
        'NE': [lon + lon_d, lat + lat_d],
        'SW': [lon - lon_d, lat - lat_d],
        'SE': [lon + lon_d, lat - lat_d],
    }

    for pt_name, (px, py) in sample_points.items():
        point = ee.Geometry.Point([px, py])
        try:
            raw = ccdc.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=point, scale=SCALE_M,
            ).getInfo()

            tbreak_arr = raw.get('tBreak', [])
            if not isinstance(tbreak_arr, list):
                tbreak_arr = [tbreak_arr] if tbreak_arr else []

            found = []
            for i, tv in enumerate(tbreak_arr):
                if tv and tv > 0:
                    date_str = fracyear_to_date(tv)
                    if not date_str:
                        continue
                    mags = {}
                    for band in CCDC_BANDS:
                        arr = raw.get(f'{band}_magnitude', [])
                        if isinstance(arr, list) and i < len(arr):
                            mags[band] = arr[i]

                    cls, conf, expl = classify_breakpoint(mags)
                    bp = {
                        'site': site_name, 'point': pt_name,
                        'break_index': i, 'break_date': date_str,
                        'break_fracyear': tv,
                        'class': cls, 'confidence': conf, 'explanation': expl,
                    }
                    bp.update({f'mag_{b}': mags.get(b) for b in CCDC_BANDS})
                    point_breakpoints.append(bp)
                    found.append(f"{date_str} ({cls})")

            if found:
                print(f"    {pt_name}: {'; '.join(found)}")
            else:
                print(f"    {pt_name}: no breaks")

        except Exception as e:
            print(f"    {pt_name}: ERROR — {e}")


# ================================================================
# PHASE 4: Segment timeline at center pixel
# ================================================================
print("\n" + "=" * 76)
print("PHASE 4: Segment Timeline at Center Pixel")
print("=" * 76)

for site_name, site_data in ccdc_results.items():
    ccdc = site_data['ccdc']
    lon, lat = SITES[site_name]['center']
    point = ee.Geometry.Point([lon, lat])

    print(f"\n  {site_name}:")
    try:
        raw = ccdc.reduceRegion(
            reducer=ee.Reducer.first(), geometry=point, scale=SCALE_M,
        ).getInfo()

        tstart = raw.get('tStart', [])
        tend = raw.get('tEnd', [])
        tbreak = raw.get('tBreak', [])
        numobs = raw.get('numObs', [])

        if not isinstance(tstart, list):
            tstart = [tstart]
        if not isinstance(tend, list):
            tend = [tend]
        if not isinstance(tbreak, list):
            tbreak = [tbreak]
        if not isinstance(numobs, list):
            numobs = [numobs]

        print(f"    {'Seg':>5} {'Start':<12} {'End':<12} {'Break':<12} {'Nobs':>6}")
        print(f"    {'─'*5} {'─'*12} {'─'*12} {'─'*12} {'─'*6}")

        for i in range(len(tstart)):
            ts = fracyear_to_date(tstart[i]) if i < len(tstart) and tstart[i] else '—'
            te = fracyear_to_date(tend[i]) if i < len(tend) and tend[i] else '—'
            tb = fracyear_to_date(tbreak[i]) if (i < len(tbreak) and tbreak[i]
                                                 and tbreak[i] > 0) else '—'
            no = numobs[i] if i < len(numobs) else '—'
            print(f"    {i+1:>5} {ts:<12} {te:<12} {tb:<12} {no:>6}")

    except Exception as e:
        print(f"    Error: {e}")


# ================================================================
# PHASE 5: Classification summary
# ================================================================
print("\n" + "=" * 76)
print("PHASE 5: All Breakpoints")
print("=" * 76)

all_bp = all_breakpoints + point_breakpoints

if not all_bp:
    print("\n  No breakpoints detected across any site or method.")
    print("  Possible explanations:")
    print("  1. Sites are genuinely stable (no major construction/destruction)")
    print("  2. Changes are sub-pixel at 20m resolution")
    print("  3. Seasonal harmonics absorb the real changes")
else:
    print(f"\n{'─' * 80}")
    print(f"{'Site':<14} {'Loc':>6} {'Date':<12} {'Class':<20} "
          f"{'Conf':>5} {'Px%':>5}")
    print(f"{'─'*14} {'─'*6} {'─'*12} {'─'*20} {'─'*5} {'─'*5}")

    for bp in sorted(all_bp, key=lambda x: (x['site'], x['break_date'])):
        loc = bp.get('quadrant', bp.get('point', '?'))
        px = bp.get('break_pixel_pct', '')
        px_str = f"{px:.0f}" if isinstance(px, (int, float)) else '—'
        print(f"{bp['site']:<14} {loc:>6} {bp['break_date']:<12} "
              f"{bp['class']:<20} {bp['confidence']:>5.2f} {px_str:>5}")

    class_counts = defaultdict(int)
    for bp in all_bp:
        class_counts[bp['class']] += 1
    print(f"\n  Distribution:")
    for cls, cnt in sorted(class_counts.items(), key=lambda x: -x[1]):
        print(f"    {cls:<25}: {cnt}")


# ================================================================
# PHASE 6: Cross-reference with known events
# ================================================================
print("\n" + "=" * 76)
print("PHASE 6: Cross-Reference with Known Events")
print("=" * 76)

MATCH_WINDOW = 90
matches = []

for event in KNOWN_EVENTS:
    ed = datetime.strptime(event['date'], "%Y-%m-%d")
    site = event['site']
    nearby = []
    for bp in all_bp:
        if bp['site'] != site:
            continue
        try:
            bd = datetime.strptime(bp['break_date'], "%Y-%m-%d")
            delta = (bd - ed).days
            if abs(delta) <= MATCH_WINDOW:
                nearby.append({'bp': bp, 'delta': delta})
        except ValueError:
            continue

    print(f"\n  {event['event']}")
    print(f"    Date: {event['date']} | Site: {site}")

    if nearby:
        for m in sorted(nearby, key=lambda x: abs(x['delta'])):
            bp = m['bp']
            d = "after" if m['delta'] > 0 else "before"
            loc = bp.get('quadrant', bp.get('point', '?'))
            print(f"    → MATCH: {bp['break_date']} ({abs(m['delta'])}d {d})"
                  f" @ {loc} — {bp['class']}")
            matches.append({
                'event': event['event'], 'event_date': event['date'],
                'bp_date': bp['break_date'], 'delta_days': m['delta'],
                'class': bp['class'], 'location': loc, 'site': site,
            })
    else:
        print(f"    → No breakpoints within ±{MATCH_WINDOW}d")

print(f"\n  Total matches: {len(matches)}")
print(f"  Events with match: "
      f"{len(set(m['event'] for m in matches))}/{len(KNOWN_EVENTS)}")


# ================================================================
# PHASE 7: Density summary
# ================================================================
print("\n" + "=" * 76)
print("PHASE 7: Breakpoint Density by Quadrant")
print("=" * 76)

if density_data:
    print(f"\n  {'Site':<14} {'Quad':>4} {'Total':>8} {'Break':>8} {'Density':>8}")
    print(f"  {'─'*14} {'─'*4} {'─'*8} {'─'*8} {'─'*8}")
    for dd in density_data:
        flag = " ← HIGH" if dd['density_pct'] > 30 else ""
        print(f"  {dd['site']:<14} {dd['quadrant']:>4} "
              f"{dd['total_pixels']:>8} {dd['pixels_with_break']:>8.0f} "
              f"{dd['density_pct']:>7.1f}%{flag}")


# ================================================================
# PHASE 8: Export
# ================================================================
print("\n" + "=" * 76)
print("PHASE 8: Data Export")
print("=" * 76)

zonal_csv = os.path.join(SAT_DATA, 'ccdc_breakpoints_zonal.csv')
if all_breakpoints:
    fields = ['site', 'quadrant', 'break_index', 'break_date', 'break_fracyear',
              'break_pixel_pct', 'n_pixels', 'n_total',
              'class', 'confidence', 'explanation']
    fields += [f'mag_{b}' for b in CCDC_BANDS]
    with open(zonal_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(all_breakpoints)
    print(f"  ✓ {zonal_csv} ({len(all_breakpoints)} rows)")

point_csv = os.path.join(SAT_DATA, 'ccdc_breakpoints_points.csv')
if point_breakpoints:
    fields = ['site', 'point', 'break_index', 'break_date', 'break_fracyear',
              'class', 'confidence', 'explanation']
    fields += [f'mag_{b}' for b in CCDC_BANDS]
    with open(point_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(point_breakpoints)
    print(f"  ✓ {point_csv} ({len(point_breakpoints)} rows)")

density_csv = os.path.join(SAT_DATA, 'ccdc_density.csv')
if density_data:
    with open(density_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['site', 'quadrant', 'total_pixels',
                                          'pixels_with_break', 'density_pct'])
        w.writeheader()
        w.writerows(density_data)
    print(f"  ✓ {density_csv} ({len(density_data)} rows)")

matches_csv = os.path.join(SAT_DATA, 'ccdc_event_matches.csv')
if matches:
    with open(matches_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['site', 'event', 'event_date',
                                          'bp_date', 'delta_days', 'class',
                                          'location'])
        w.writeheader()
        w.writerows(matches)
    print(f"  ✓ {matches_csv} ({len(matches)} rows)")


# ================================================================
# PHASE 9: Write FINDINGS
# ================================================================
print("\n" + "=" * 76)
print("PHASE 9: Writing FINDINGS.satellite-ccdc.md")
print("=" * 76)

findings_path = os.path.join(METHODOLOGY, 'FINDINGS.satellite-ccdc.md')
site_bp_counts = defaultdict(int)
for bp in all_bp:
    site_bp_counts[bp['site']] += 1

class_counts = defaultdict(int)
for bp in all_bp:
    class_counts[bp['class']] += 1

L = []  # lines
L.append("# Research Findings: CCDC Time Series Segmentation for Military Sites")
L.append("")
L.append(f"**Experiment 22** | {datetime.now().strftime('%Y-%m-%d')} | "
         f"{len(ccdc_results)} sites × CCDC analysis")
L.append(f"**Dataset**: Sentinel-2 SR Harmonized via Google Earth Engine, "
         f"{DATE_START} to {DATE_END}")
L.append("**Sites**: " + ', '.join(
    f'{s} ({SITES[s]["type"]})' for s in SITES))
L.append("")
L.append("---")
L.append("")

# Method
L.append("## Method")
L.append("")
L.append("CCDC (Continuous Change Detection and Classification; "
         "Zhu & Woodcock 2014) fits a harmonic")
L.append("regression model to each pixel's spectral time series and detects "
         "breakpoints when observations")
L.append("deviate beyond a chi-squared threshold. Runs server-side in GEE.")
L.append("")
L.append("### Parameters")
L.append("")
L.append("| Parameter | Value |")
L.append("|-----------|-------|")
L.append(f"| Bands | {', '.join(CCDC_BANDS)} (Red, NIR, SWIR1, SWIR2) |")
L.append(f"| chiSquareProbability | {CCDC_PARAMS['chiSquareProbability']} |")
L.append(f"| minObservations | {CCDC_PARAMS['minObservations']} |")
L.append(f"| lambda | {CCDC_PARAMS['lambda']} |")
L.append(f"| scale | {SCALE_M}m |")
L.append(f"| cloud filter | SCL + <{MAX_CLOUD_PCT}% |")
L.append("")

# Classification
L.append("### Breakpoint Classification")
L.append("")
L.append("```")
L.append("vegetation_loss:  NIR↓ + SWIR1↑    → clearing, construction")
L.append("vegetation_gain:  NIR↑ + SWIR1↓    → regrowth, abandonment")
L.append("BSI_increase:     (SWIR1+Red)↑-NIR↑ → earthwork, bare soil")
L.append("metal_increase:   NIR↑ + SWIR1↑    → metallic equipment/structures")
L.append("snow_transition:  large SWIR Δ     → seasonal snow change")
L.append("```")
L.append("")
L.append("---")
L.append("")

# Results
L.append("## Results")
L.append("")
L.append("### Summary")
L.append("")
L.append("| Metric | Value |")
L.append("|--------|-------|")
L.append(f"| Sites processed | {len(ccdc_results)} |")
for sn in SITES:
    n_img = ccdc_results.get(sn, {}).get('n_images', 0)
    L.append(f"| {sn} images | {n_img} |")
L.append(f"| Total breakpoints | {len(all_bp)} |")
L.append(f"| Zonal (quadrant-level) | {len(all_breakpoints)} |")
L.append(f"| Point (pixel-level) | {len(point_breakpoints)} |")
L.append(f"| ISW event matches (±{MATCH_WINDOW}d) | {len(matches)} |")
L.append("")

# Per-site breakpoints
for sn in SITES:
    site_bps = sorted([bp for bp in all_bp if bp['site'] == sn],
                      key=lambda x: x['break_date'])
    L.append(f"### {sn} ({SITES[sn]['description']})")
    L.append("")

    if site_bps:
        L.append("| Date | Location | Class | Confidence | Explanation |")
        L.append("|------|----------|-------|:----------:|-------------|")
        seen = set()
        for bp in site_bps:
            loc = bp.get('quadrant', bp.get('point', '?'))
            key = (bp['break_date'], loc)
            if key in seen:
                continue
            seen.add(key)
            L.append(f"| {bp['break_date']} | {loc} | {bp['class']} | "
                     f"{bp['confidence']:.2f} | {bp['explanation'][:60]} |")
    else:
        L.append("No breakpoints detected at this site.")

    L.append("")

# Density
if density_data:
    L.append("### Breakpoint Density by Quadrant")
    L.append("")
    L.append("| Site | Quad | Total Px | Px w/ Break | Density |")
    L.append("|------|------|:--------:|:-----------:|:-------:|")
    for dd in density_data:
        L.append(f"| {dd['site']} | {dd['quadrant']} | "
                 f"{dd['total_pixels']} | {dd['pixels_with_break']:.0f} | "
                 f"{dd['density_pct']:.1f}% |")
    L.append("")

# Classification distribution
if class_counts:
    L.append("### Classification Distribution")
    L.append("")
    L.append("| Class | Count | Description |")
    L.append("|-------|:-----:|-------------|")
    descs = {
        'vegetation_loss': 'Clearing, construction, ground disturbance',
        'vegetation_gain': 'Regrowth, abandonment, revegetation',
        'BSI_increase': 'Earthwork or bare soil exposure',
        'metal_increase': 'Metallic equipment or structure arrival',
        'snow_transition': 'Seasonal snow change',
        'significant_change': 'Large spectral change (type unclear)',
        'negligible_change': 'Below significance threshold',
        'unclassified': 'Does not match patterns',
        'insufficient_data': 'Too few magnitude values',
    }
    for cls, cnt in sorted(class_counts.items(), key=lambda x: -x[1]):
        L.append(f"| {cls} | {cnt} | {descs.get(cls, '')} |")
    L.append("")

# Event cross-reference
L.append("### Event Cross-Reference")
L.append("")
L.append("| Event | Date | Nearest Break | Δ Days | Class |")
L.append("|-------|------|:------------:|:------:|-------|")
for event in KNOWN_EVENTS:
    em = [m for m in matches if m['event'] == event['event']]
    if em:
        best = min(em, key=lambda x: abs(x['delta_days']))
        L.append(f"| {event['event'][:50]} | {event['date']} | "
                 f"{best['bp_date']} | {best['delta_days']:+d} | {best['class']} |")
    else:
        L.append(f"| {event['event'][:50]} | {event['date']} | — | — | — |")
L.append("")
L.append("---")
L.append("")

# Conclusions
L.append("## Conclusions")
L.append("")
L.append("### What CCDC Detects at 20m Resolution")
L.append("")
L.append("1. **Landscape-level infrastructure changes**: Construction, clearing,")
L.append("   paving — persistent spectral shifts the harmonic model cannot explain.")
L.append("2. **Seasonal pattern disruption**: If a site's vegetation cycle changes,")
L.append("   CCDC detects this as a breakpoint.")
L.append("3. **Multi-band regime changes**: Changes across NIR + SWIR bands are")
L.append("   more likely real than single-band artifacts.")
L.append("")
L.append("### What CCDC Cannot Detect")
L.append("")
L.append("1. **Individual vehicle movements**: Sub-pixel at 20m.")
L.append("2. **Short exercises (<2 weeks)**: Insufficient observations.")
L.append("3. **Camouflaged activity**: Surface-only detection.")
L.append("")
L.append("### Complementarity with NB 20/21")
L.append("")
L.append("| Approach | NB 20 | NB 21 | NB 22 |")
L.append("|----------|-------|-------|-------|")
L.append("| Method | Seasonal z-score | IsolationForest | CCDC harmonic breaks |")
L.append("| Detects | Deviations from season | Spectral outliers | Regime changes |")
L.append("| Time scale | Days-weeks | Point-in-time | Months-years |")
L.append("")
L.append("### Production Recommendation")
L.append("")
L.append("1. Run CCDC annually on full S2 archive per monitored site.")
L.append("2. Cross-reference new breakpoints with OSINT/SIGINT.")
L.append("3. Use density maps to prioritize quadrants for monitoring.")
L.append("4. Two-level alert: NB 20 for transient, NB 22 for permanent changes.")
L.append("")
L.append("---")
L.append("")
L.append("## References")
L.append("")
L.append("1. Zhu, Z. & Woodcock, C.E. (2014). \"Continuous change detection and "
         "classification")
L.append("   of land surface using all available Landsat data.\" "
         "*Remote Sensing of Environment*, 144, 152-171.")
L.append("2. GEE: `ee.Algorithms.TemporalSegmentation.Ccdc`")
L.append("")
L.append("*Experiment code: `notebooks/22_ccdc_breakpoints.py`*")
L.append("")

with open(findings_path, 'w') as f:
    f.write('\n'.join(L))
print(f"  ✓ {findings_path}")


# ================================================================
# FINAL SUMMARY
# ================================================================
print("\n" + "=" * 76)
print("FINAL SUMMARY")
print("=" * 76)
print(f"""
  Sites processed:      {len(ccdc_results)} / {len(SITES)}
  Total breakpoints:    {len(all_bp)}
    Zonal:              {len(all_breakpoints)}
    Point:              {len(point_breakpoints)}
  Event matches:        {len(matches)} (±{MATCH_WINDOW}d)

  Per-site:""")
for sn in SITES:
    print(f"    {sn:<16}: {site_bp_counts.get(sn, 0)} breakpoints")
print(f"""
  Classification:""")
for cls, cnt in sorted(class_counts.items(), key=lambda x: -x[1]):
    print(f"    {cls:<25}: {cnt}")
print(f"""
  Output:
    {zonal_csv}
    {point_csv}
    {density_csv}
    {matches_csv}
    {findings_path}
""")
