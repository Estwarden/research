#!/usr/bin/env python3
"""
21. Isolation Forest Anomaly Baselines per Military Site
=========================================================

Previous findings (FINDINGS.satellite-imagery.md):
  - Exp 15: Single-frame IsolationForest detected ships at Kronstadt
    (94% bright NIR) and equipment at Pskov SW quadrant (10% anomaly
    concentration). But: one snapshot = no temporal baseline.
  - NB 20: 3-year seasonal profiles provide deseasonalized z-scores.

This notebook builds TEMPORAL IsolationForest baselines:
  1. Queries GEE for last 20+ cloud-free S2 acquisitions per site
  2. Extracts 6-band zonal statistics (mean/std/p25/p50/p75/p90)
     per quadrant (NW/NE/SW/SE)
  3. Trains one sklearn IsolationForest per site on historical
     spectral distribution
  4. Scores the most recent acquisition against the model
  5. Identifies which quadrant is most anomalous vs historical baseline
  6. Tracks anomaly scores per quadrant over time

Requires: earthengine-api, scikit-learn, numpy
GEE auth: ee.Authenticate() or service account.
"""

import csv
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

try:
    import ee
    ee.Initialize()
    HAS_GEE = True
    print("✓ Google Earth Engine initialized")
except Exception as e:
    HAS_GEE = False
    print(f"✗ GEE init failed: {e}")
    print("  Will attempt cached data or site-level fallback")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(SCRIPT_DIR, '..', 'data')
SAT_DATA = os.path.join(DATA, 'satellite')
OUTPUT = os.path.join(SCRIPT_DIR, '..', 'output')
os.makedirs(SAT_DATA, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)

CACHE_CSV = os.path.join(SAT_DATA, 'quadrant_stats.csv')

print("=" * 76)
print("21. ISOLATION FOREST ANOMALY BASELINES — PER MILITARY SITE")
print("=" * 76)

# ================================================================
# SITE DEFINITIONS (same as NB 20)
# ================================================================
SITES = {
    "Pskov-76VDV": {
        "center": [28.395, 57.785], "type": "airborne",
        "description": "76th Guards Air Assault Division airfield",
    },
    "Cherekha": {
        "center": [28.420, 57.740], "type": "garrison",
        "description": "Cherekha garrison — motor pool and barracks",
    },
    "Luga": {
        "center": [29.846, 58.737], "type": "garrison",
        "description": "Luga training ground and garrison",
    },
    "Chkalovsk": {
        "center": [20.415, 54.775], "type": "airbase",
        "description": "Chkalovsk naval aviation airbase",
    },
    "Kronstadt": {
        "center": [29.768, 59.988], "type": "naval",
        "description": "Kronstadt naval base — Baltic Fleet",
    },
}

ROI_RADIUS_M = 1000
BANDS = ['B2', 'B3', 'B4', 'B8', 'B11', 'B12']
BAND_LABELS = {'B2': 'Blue', 'B3': 'Green', 'B4': 'Red',
               'B8': 'NIR', 'B11': 'SWIR1', 'B12': 'SWIR2'}
SCALE_M = 20
MAX_CLOUD_PCT = 20
N_IMAGES = 25
DATE_START = "2023-01-01"
DATE_END = "2026-03-25"
QUADRANT_NAMES = ['NW', 'NE', 'SW', 'SE']

IFOREST_CONTAMINATION = 0.05
IFOREST_N_ESTIMATORS = 200
IFOREST_SEED = 42
TRAIN_FRAC = 0.6


# ================================================================
# GEE HELPERS
# ================================================================

def make_quadrant_fc(lon, lat, radius_m=ROI_RADIUS_M):
    """FeatureCollection of 4 labeled quadrant rectangles."""
    lat_d = radius_m / 111000
    lon_d = radius_m / (111000 * math.cos(math.radians(lat)))
    boxes = {
        'NW': [lon - lon_d, lat,       lon,       lat + lat_d],
        'NE': [lon,         lat,       lon + lon_d, lat + lat_d],
        'SW': [lon - lon_d, lat - lat_d, lon,       lat],
        'SE': [lon,         lat - lat_d, lon + lon_d, lat],
    }
    return ee.FeatureCollection([
        ee.Feature(ee.Geometry.Rectangle(b), {'quadrant': n})
        for n, b in boxes.items()
    ])


def mask_clouds(image):
    """SCL-based pixel cloud mask. Keeps vegetation/soil/water/snow."""
    scl = image.select('SCL')
    ok = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7)).Or(scl.eq(11))
    return image.updateMask(ok)


def extract_site_quadrant_data(site_name, site_info):
    """Extract per-quadrant 6-band zonal stats from GEE.

    Processes one image at a time to stay within GEE's concurrent
    aggregation limits. Each getInfo() evaluates one reduceRegions
    call (1 image × 4 quadrants × combined reducer).

    Returns list of dicts with keys: site, date, quadrant, cloud_pct,
    plus 36 stat columns (6 bands × 6 stats).
    """
    lon, lat = site_info['center']
    quad_fc = make_quadrant_fc(lon, lat)
    roi = ee.Geometry.Point([lon, lat]).buffer(ROI_RADIUS_M).bounds()

    reducer = (ee.Reducer.mean()
               .combine(ee.Reducer.stdDev(), sharedInputs=True)
               .combine(ee.Reducer.percentile([25, 50, 75, 90]),
                        sharedInputs=True))

    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(roi)
                  .filterDate(DATE_START, DATE_END)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD_PCT))
                  .sort('system:time_start', False)
                  .limit(N_IMAGES))

    img_list = collection.toList(N_IMAGES)
    n_avail = img_list.size().getInfo()

    if n_avail == 0:
        return []

    # Process one image at a time — avoids "Too many concurrent aggregations"
    records = []
    for i in range(n_avail):
        img = ee.Image(img_list.get(i))
        masked = mask_clouds(img).select(BANDS)
        date_ee = img.date().format('YYYY-MM-dd')
        cloud_ee = img.get('CLOUDY_PIXEL_PERCENTAGE')
        fc = masked.reduceRegions(
            collection=quad_fc,
            reducer=reducer,
            scale=SCALE_M,
        )
        fc = fc.map(lambda f, _d=date_ee, _c=cloud_ee:
                     f.set('date', _d, 'cloud_pct', _c))

        try:
            result = fc.getInfo()
            for feat in result.get('features', []):
                props = feat.get('properties', {})
                if props.get('date'):
                    props['site'] = site_name
                    records.append(props)
        except Exception as e:
            print(f"img {i} err: {e}", end=" ", flush=True)

    return records


# ================================================================
# PHASE 1: Data extraction (GEE with CSV cache)
# ================================================================
print("\n" + "=" * 76)
print("PHASE 1: Per-quadrant 6-band zonal statistics")
print("=" * 76)

all_records = []

# Try loading cached data first
if os.path.exists(CACHE_CSV):
    with open(CACHE_CSV) as f:
        reader = csv.DictReader(f)
        all_records = list(reader)
    sites_cached = set(r['site'] for r in all_records)
    print(f"\n  Loaded cache: {len(all_records)} rows, "
          f"sites: {sorted(sites_cached)}")
    # Convert numeric fields
    meta_keys = {'site', 'date', 'quadrant'}
    for r in all_records:
        for k, v in r.items():
            if k not in meta_keys and v != '':
                try:
                    r[k] = float(v)
                except (ValueError, TypeError):
                    pass

if not all_records:
    if not HAS_GEE:
        print("\n  ✗ No cached data and no GEE — cannot proceed")
        print("  Run with GEE auth to build cache, or copy quadrant_stats.csv")
        sys.exit(1)

    for site_name, site_info in SITES.items():
        print(f"\n  {site_name} ({site_info['type']})... ", end="", flush=True)
        t0 = time.time()
        try:
            recs = extract_site_quadrant_data(site_name, site_info)
            elapsed = time.time() - t0
            n_imgs = len(set(r['date'] for r in recs))
            print(f"{len(recs)} obs ({n_imgs} images) in {elapsed:.0f}s")
            all_records.extend(recs)
        except Exception as e:
            print(f"FAILED: {e}")

    # Save cache
    if all_records:
        all_keys = set()
        for r in all_records:
            all_keys.update(r.keys())
        ordered = ['site', 'date', 'quadrant', 'cloud_pct']
        stat_keys = sorted(k for k in all_keys if k not in set(ordered))
        fieldnames = ordered + stat_keys
        with open(CACHE_CSV, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            w.writeheader()
            w.writerows(all_records)
        print(f"\n  ✓ Cached to {CACHE_CSV} ({len(all_records)} rows)")

if not all_records:
    print("  ✗ No data obtained — exiting")
    sys.exit(1)


# ================================================================
# PHASE 2: Discover feature columns and build matrices
# ================================================================
print("\n" + "=" * 76)
print("PHASE 2: Feature matrix construction")
print("=" * 76)

# Discover stat feature columns from the data
META_KEYS = {'site', 'date', 'quadrant', 'cloud_pct'}
sample = all_records[0]
FEATURE_COLS = sorted(
    k for k in sample.keys()
    if k not in META_KEYS
    and isinstance(sample.get(k), (int, float))
    and sample.get(k) is not None
)
print(f"\n  Feature columns discovered: {len(FEATURE_COLS)}")
if FEATURE_COLS:
    print(f"  Examples: {FEATURE_COLS[:6]}...")

# Group by site
site_records = defaultdict(list)
for r in all_records:
    site_records[r['site']].append(r)

# Print data summary per site
print(f"\n  {'Site':<16} {'Obs':>5} {'Images':>7} {'Quads':>6} "
      f"{'Date range':<25} {'Nulls':>6}")
print(f"  {'─'*16} {'─'*5} {'─'*7} {'─'*6} {'─'*25} {'─'*6}")
for sn in SITES:
    recs = site_records.get(sn, [])
    if not recs:
        print(f"  {sn:<16} {'—':>5}")
        continue
    dates = sorted(set(r['date'] for r in recs))
    quads = set(r['quadrant'] for r in recs)
    # Count nulls
    n_nulls = sum(1 for r in recs
                  if any(r.get(c) is None or
                         (isinstance(r.get(c), float) and math.isnan(r.get(c)))
                         for c in FEATURE_COLS))
    print(f"  {sn:<16} {len(recs):>5} {len(dates):>7} {len(quads):>6} "
          f"{dates[0]} → {dates[-1]:<12} {n_nulls:>6}")


def build_feature_matrix(records, feature_cols):
    """Convert records to numpy feature matrix, dropping rows with nulls.

    Returns: X (n_samples × n_features), valid_records (list of dicts)
    """
    valid = []
    for r in records:
        vals = []
        skip = False
        for c in feature_cols:
            v = r.get(c)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                skip = True
                break
            vals.append(float(v))
        if not skip:
            valid.append((r, vals))

    if not valid:
        return np.array([]), []

    X = np.array([v for _, v in valid])
    valid_recs = [r for r, _ in valid]
    return X, valid_recs


# ================================================================
# PHASE 3: Train IsolationForest per site
# ================================================================
print("\n" + "=" * 76)
print("PHASE 3: IsolationForest training (one model per site)")
print("=" * 76)
print(f"""
  Parameters:
    contamination = {IFOREST_CONTAMINATION} (expected anomaly rate)
    n_estimators  = {IFOREST_N_ESTIMATORS}
    train_frac    = {TRAIN_FRAC} (oldest {TRAIN_FRAC*100:.0f}% of images)
    features      = {len(FEATURE_COLS)} per quadrant
""")

site_models = {}     # site → trained IsolationForest
site_scalers = {}    # site → fitted StandardScaler
site_train_X = {}    # site → training feature matrix
site_train_recs = {} # site → training records
site_all_X = {}      # site → full feature matrix
site_all_recs = {}   # site → full records

for site_name in SITES:
    recs = site_records.get(site_name, [])
    if not recs:
        print(f"\n  {site_name}: NO DATA — skipping")
        continue

    X, valid_recs = build_feature_matrix(recs, FEATURE_COLS)
    if len(valid_recs) < 10:
        print(f"\n  {site_name}: only {len(valid_recs)} valid obs — "
              f"need ≥10, skipping")
        continue

    # Sort by date (oldest first) for temporal split
    date_order = sorted(range(len(valid_recs)),
                        key=lambda i: valid_recs[i]['date'])
    X = X[date_order]
    valid_recs = [valid_recs[i] for i in date_order]

    # Split: oldest TRAIN_FRAC for training, rest for held-out scoring
    n_train_imgs = max(10, int(len(set(r['date'] for r in valid_recs))
                                * TRAIN_FRAC))
    train_dates = sorted(set(r['date'] for r in valid_recs))[:n_train_imgs]
    train_mask = np.array([r['date'] in set(train_dates) for r in valid_recs])

    X_train = X[train_mask]
    X_all = X

    if len(X_train) < 10:
        print(f"\n  {site_name}: only {len(X_train)} training obs — "
              f"using all data for training")
        X_train = X_all
        train_mask = np.ones(len(X_all), dtype=bool)

    # Standardize features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_all_scaled = scaler.transform(X_all)

    # Train IsolationForest
    model = IsolationForest(
        n_estimators=IFOREST_N_ESTIMATORS,
        contamination=IFOREST_CONTAMINATION,
        random_state=IFOREST_SEED,
        n_jobs=-1,
    )
    model.fit(X_train_scaled)

    # Store results
    site_models[site_name] = model
    site_scalers[site_name] = scaler
    site_train_X[site_name] = X_train_scaled
    site_train_recs[site_name] = [r for r, m in zip(valid_recs, train_mask) if m]
    site_all_X[site_name] = X_all_scaled
    site_all_recs[site_name] = valid_recs

    # Score all observations
    scores = model.decision_function(X_all_scaled)
    labels = model.predict(X_all_scaled)
    n_anom = np.sum(labels == -1)
    n_train_anom = np.sum(model.predict(X_train_scaled) == -1)

    print(f"\n  {site_name} ({SITES[site_name]['type']})")
    print(f"    Training:   {len(X_train)} obs "
          f"({len(train_dates)} images × {len(QUADRANT_NAMES)} quads)")
    print(f"    Total:      {len(X_all)} obs")
    print(f"    Anomalies:  {n_anom}/{len(X_all)} "
          f"({100*n_anom/len(X_all):.1f}%)")
    print(f"    Train anom: {n_train_anom}/{len(X_train)} "
          f"({100*n_train_anom/len(X_train):.1f}%)")
    print(f"    Score range: [{scores.min():.3f}, {scores.max():.3f}] "
          f"(more negative = more anomalous)")


# ================================================================
# PHASE 4: Score most recent acquisition — anomaly quadrant map
# ================================================================
print("\n" + "=" * 76)
print("PHASE 4: Most Recent Acquisition — Anomaly Quadrant Map")
print("=" * 76)

for site_name in SITES:
    if site_name not in site_models:
        continue

    model = site_models[site_name]
    scaler = site_scalers[site_name]
    all_recs = site_all_recs[site_name]
    X_all = site_all_X[site_name]

    # Get the most recent date
    latest_date = max(r['date'] for r in all_recs)
    latest_mask = np.array([r['date'] == latest_date for r in all_recs])
    latest_recs = [r for r, m in zip(all_recs, latest_mask) if m]
    X_latest = X_all[latest_mask]

    if len(X_latest) == 0:
        continue

    scores = model.decision_function(X_latest)
    labels = model.predict(X_latest)

    print(f"\n{'─' * 70}")
    print(f"{site_name} — Most recent: {latest_date}")
    print(f"{'─' * 70}")
    print(f"  {'Quadrant':<10} {'Score':>8} {'Label':>8} {'Verdict':<20}")
    print(f"  {'─'*10} {'─'*8} {'─'*8} {'─'*20}")

    quad_scores = {}
    for rec, score, label in zip(latest_recs, scores, labels):
        quad = rec.get('quadrant', '?')
        status = "🔴 ANOMALOUS" if label == -1 else "✅ Normal"
        print(f"  {quad:<10} {score:>+8.3f} {label:>8} {status}")
        quad_scores[quad] = score

    # Identify most anomalous quadrant
    if quad_scores:
        worst = min(quad_scores, key=quad_scores.get)
        print(f"\n  → Most anomalous quadrant: {worst} "
              f"(score={quad_scores[worst]:+.3f})")

    # Compare to historical baseline for this quadrant
    all_scores = model.decision_function(X_all)
    all_by_quad = defaultdict(list)
    for rec, s in zip(all_recs, all_scores):
        all_by_quad[rec.get('quadrant', '?')].append(s)

    print(f"\n  Historical anomaly scores by quadrant:")
    print(f"  {'Quadrant':<10} {'Mean':>8} {'Std':>8} {'Min':>8} "
          f"{'P10':>8} {'Latest':>8} {'z-hist':>8}")
    print(f"  {'─'*10} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
    for q in QUADRANT_NAMES:
        hist = np.array(all_by_quad.get(q, []))
        if len(hist) == 0:
            continue
        latest_s = quad_scores.get(q, float('nan'))
        mu, sigma = hist.mean(), hist.std()
        z = (latest_s - mu) / sigma if sigma > 1e-6 else 0.0
        p10 = np.percentile(hist, 10)
        print(f"  {q:<10} {mu:>+8.3f} {sigma:>8.3f} {hist.min():>+8.3f} "
              f"{p10:>+8.3f} {latest_s:>+8.3f} {z:>+8.2f}")


# ================================================================
# PHASE 5: Temporal anomaly tracking per quadrant
# ================================================================
print("\n" + "=" * 76)
print("PHASE 5: Temporal Anomaly Tracking")
print("=" * 76)
print("""
  For each site, track the IForest anomaly score per quadrant over time.
  Rising anomaly rate (more negative scores) in a quadrant suggests
  spectral change — potential activity shift.
""")

for site_name in SITES:
    if site_name not in site_models:
        continue

    model = site_models[site_name]
    all_recs = site_all_recs[site_name]
    X_all = site_all_X[site_name]
    all_scores = model.decision_function(X_all)
    all_labels = model.predict(X_all)

    print(f"\n{'─' * 76}")
    print(f"{site_name} — Anomaly Timeline")
    print(f"{'─' * 76}")

    # Group by date
    by_date = defaultdict(list)
    for rec, s, l in zip(all_recs, all_scores, all_labels):
        by_date[rec['date']].append({
            'quadrant': rec.get('quadrant', '?'),
            'score': s,
            'label': l,
        })

    # Print timeline: date, per-quad score, anomaly count
    dates_sorted = sorted(by_date.keys())
    train_dates_set = set(r['date'] for r in site_train_recs.get(site_name, []))

    print(f"  {'Date':<12} {'Set':>5} ", end="")
    for q in QUADRANT_NAMES:
        print(f" {q:>8}", end="")
    print(f" {'Anom':>5}")
    print(f"  {'─'*12} {'─'*5} " + " ".join(f"{'─'*8}" for _ in QUADRANT_NAMES)
          + f" {'─'*5}")

    for date in dates_sorted:
        entries = by_date[date]
        split = "TRAIN" if date in train_dates_set else "TEST"
        q_map = {e['quadrant']: e for e in entries}
        n_anom = sum(1 for e in entries if e['label'] == -1)
        line = f"  {date:<12} {split:>5} "
        for q in QUADRANT_NAMES:
            e = q_map.get(q)
            if e:
                flag = "!" if e['label'] == -1 else " "
                line += f" {e['score']:>+7.3f}{flag}"
            else:
                line += f" {'—':>8}"
        line += f" {n_anom:>5}"
        print(line)

    # Anomaly rate per quadrant over time
    print(f"\n  Anomaly rate by quadrant:")
    print(f"  {'Quadrant':<10} {'Total obs':>10} {'Anomalies':>10} "
          f"{'Rate':>8} {'Avg score':>10}")
    print(f"  {'─'*10} {'─'*10} {'─'*10} {'─'*8} {'─'*10}")

    for q in QUADRANT_NAMES:
        q_entries = [e for entries in by_date.values() for e in entries
                     if e['quadrant'] == q]
        n_total = len(q_entries)
        n_anom = sum(1 for e in q_entries if e['label'] == -1)
        avg_score = np.mean([e['score'] for e in q_entries]) if q_entries else 0
        rate = 100 * n_anom / max(n_total, 1)
        flag = " ← hotspot" if rate > 10 else ""
        print(f"  {q:<10} {n_total:>10} {n_anom:>10} {rate:>7.1f}% "
              f"{avg_score:>+10.3f}{flag}")

    # Detect quadrant anomaly trend (is anomaly rate increasing over time?)
    print(f"\n  Temporal trend (recent vs historical anomaly rate):")
    mid_date = dates_sorted[len(dates_sorted)//2]
    for q in QUADRANT_NAMES:
        early = [e for d in dates_sorted if d <= mid_date
                 for e in by_date[d] if e['quadrant'] == q]
        late = [e for d in dates_sorted if d > mid_date
                for e in by_date[d] if e['quadrant'] == q]
        if not early or not late:
            continue
        early_rate = 100 * sum(1 for e in early if e['label'] == -1) / len(early)
        late_rate = 100 * sum(1 for e in late if e['label'] == -1) / len(late)
        delta = late_rate - early_rate
        trend = "↑ RISING" if delta > 5 else "↓ falling" if delta < -5 else "→ stable"
        print(f"    {q}: {early_rate:.0f}% → {late_rate:.0f}% ({trend})")


# ================================================================
# PHASE 6: Cross-site anomaly comparison
# ================================================================
print("\n" + "=" * 76)
print("PHASE 6: Cross-Site Anomaly Comparison")
print("=" * 76)

print(f"\n  {'Site':<16} {'Type':<10} {'Obs':>5} {'Train':>5} "
      f"{'Anom%':>6} {'Worst quad':>12} {'Worst rate':>10}")
print(f"  {'─'*16} {'─'*10} {'─'*5} {'─'*5} {'─'*6} {'─'*12} {'─'*10}")

for site_name, site_info in SITES.items():
    if site_name not in site_models:
        print(f"  {site_name:<16} {'NO MODEL':>10}")
        continue

    model = site_models[site_name]
    all_recs = site_all_recs[site_name]
    X_all = site_all_X[site_name]
    labels = model.predict(X_all)
    n_train = len(site_train_recs[site_name])
    n_anom = np.sum(labels == -1)
    anom_pct = 100 * n_anom / len(labels)

    # Find worst quadrant
    by_q = defaultdict(lambda: {'total': 0, 'anom': 0})
    for rec, lab in zip(all_recs, labels):
        q = rec.get('quadrant', '?')
        by_q[q]['total'] += 1
        if lab == -1:
            by_q[q]['anom'] += 1

    worst_q = max(by_q, key=lambda q: by_q[q]['anom'] / max(by_q[q]['total'], 1))
    worst_rate = 100 * by_q[worst_q]['anom'] / max(by_q[worst_q]['total'], 1)

    print(f"  {site_name:<16} {site_info['type']:<10} {len(labels):>5} "
          f"{n_train:>5} {anom_pct:>5.1f}% {worst_q:>12} {worst_rate:>9.1f}%")


# ================================================================
# PHASE 7: Feature importance (which bands drive anomalies?)
# ================================================================
print("\n" + "=" * 76)
print("PHASE 7: Feature Importance — What Drives Anomalies?")
print("=" * 76)
print("""
  IsolationForest doesn't have direct feature importances, but we can
  compare the feature distributions of anomalous vs normal observations.
  Large differences indicate which bands/stats drive anomaly detection.
""")

for site_name in SITES:
    if site_name not in site_models:
        continue

    model = site_models[site_name]
    X_all = site_all_X[site_name]
    labels = model.predict(X_all)

    normal_mask = labels == 1
    anom_mask = labels == -1

    if np.sum(anom_mask) < 2:
        continue

    X_normal = X_all[normal_mask]
    X_anom = X_all[anom_mask]

    print(f"\n  {site_name} — Top feature differences (anomalous vs normal):")
    print(f"  {'Feature':<25} {'Normal μ':>10} {'Anom μ':>10} {'Δ (std)':>10}")
    print(f"  {'─'*25} {'─'*10} {'─'*10} {'─'*10}")

    diffs = []
    for j, col in enumerate(FEATURE_COLS):
        mu_n = X_normal[:, j].mean()
        mu_a = X_anom[:, j].mean()
        pooled_std = X_all[:, j].std()
        d = (mu_a - mu_n) / pooled_std if pooled_std > 1e-6 else 0
        diffs.append((col, mu_n, mu_a, d))

    # Top 10 by absolute difference
    diffs.sort(key=lambda x: abs(x[3]), reverse=True)
    for col, mu_n, mu_a, d in diffs[:10]:
        flag = " ←" if abs(d) > 1.0 else ""
        print(f"  {col:<25} {mu_n:>+10.3f} {mu_a:>+10.3f} {d:>+10.3f}{flag}")


# ================================================================
# PHASE 8: Comparison with Experiment 15 findings
# ================================================================
print("\n" + "=" * 76)
print("PHASE 8: Comparison with Exp 15 (Single-Frame IForest)")
print("=" * 76)
print("""
  Exp 15 single-frame findings:
    Kronstadt NW: 9.7% anomaly, 94% bright NIR → ships
    Pskov SW: 10.0% anomaly → equipment park
    Chkalovsk NW: 7.2% anomaly → infrastructure

  With temporal baseline, do these quadrants remain consistently anomalous
  (persistent features) or do they vary (activity changes)?
""")

exp15_hotspots = {
    "Kronstadt": ("NW", "Ships/port — bright NIR"),
    "Pskov-76VDV": ("SW", "Equipment park — 10% anomaly"),
    "Chkalovsk": ("NW", "Infrastructure — 7.2% anomaly"),
}

for site_name, (exp15_quad, exp15_desc) in exp15_hotspots.items():
    if site_name not in site_models:
        print(f"\n  {site_name}: no model — cannot compare")
        continue

    model = site_models[site_name]
    all_recs = site_all_recs[site_name]
    X_all = site_all_X[site_name]
    scores = model.decision_function(X_all)
    labels = model.predict(X_all)

    # Get anomaly rate for the Exp 15 hotspot quadrant vs others
    hotspot_scores = []
    other_scores = []
    for rec, s, l in zip(all_recs, scores, labels):
        q = rec.get('quadrant', '?')
        if q == exp15_quad:
            hotspot_scores.append((s, l))
        else:
            other_scores.append((s, l))

    hs_anom_rate = (100 * sum(1 for _, l in hotspot_scores if l == -1)
                    / max(len(hotspot_scores), 1))
    ot_anom_rate = (100 * sum(1 for _, l in other_scores if l == -1)
                    / max(len(other_scores), 1))
    hs_avg_score = np.mean([s for s, _ in hotspot_scores]) if hotspot_scores else 0
    ot_avg_score = np.mean([s for s, _ in other_scores]) if other_scores else 0

    print(f"\n  {site_name} — Exp 15 hotspot: {exp15_quad} ({exp15_desc})")
    print(f"    {exp15_quad} quadrant:  {hs_anom_rate:.1f}% anomaly rate, "
          f"avg score {hs_avg_score:+.3f}")
    print(f"    Other quads:  {ot_anom_rate:.1f}% anomaly rate, "
          f"avg score {ot_avg_score:+.3f}")
    if hs_anom_rate > ot_anom_rate * 1.5:
        print(f"    → CONFIRMED: {exp15_quad} is persistently more anomalous "
              f"({hs_anom_rate/max(ot_anom_rate,0.1):.1f}× baseline)")
    elif hs_anom_rate > ot_anom_rate:
        print(f"    → PARTIALLY confirmed: slight elevation")
    else:
        print(f"    → NOT confirmed by temporal baseline")


# ================================================================
# SUMMARY
# ================================================================
print("\n" + "=" * 76)
print("SUMMARY")
print("=" * 76)

n_sites_trained = len(site_models)
n_total_obs = sum(len(v) for v in site_all_recs.values())
n_total_anom = 0
for sn in site_models:
    labels = site_models[sn].predict(site_all_X[sn])
    n_total_anom += np.sum(labels == -1)

print(f"""
  Sites with IForest models: {n_sites_trained}/{len(SITES)}
  Total quadrant observations: {n_total_obs}
  Total anomalies detected: {n_total_anom} ({100*n_total_anom/max(n_total_obs,1):.1f}%)

  Key advance over Exp 15 (single-frame):
    - Each site now has a TEMPORAL baseline from {N_IMAGES} acquisitions
    - Anomalies are relative to each site's own spectral history
    - Persistent features (ships, infrastructure) distinguished from
      transient changes (deployments, exercises)
    - Per-quadrant tracking enables spatial activity monitoring

  Production integration:
    1. Run IForest scoring on each new acquisition
    2. Compare per-quadrant anomaly score to historical baseline
    3. Alert on quadrants with score below site's p5 threshold
    4. Track anomaly rate trends per quadrant (rising = activity change)

  Formula (for Go production code):
    // Per-quadrant anomaly detection
    features := extractQuadrantBandStats(acquisition, site, quadrant)
    scaled := scaler.Transform(features)  // from site-specific scaler
    score := iforest.DecisionFunction(scaled)
    if score < siteThreshold[site] {{
        alertAnomaly(site, quadrant, score)
    }}

  Limitations:
    - {IFOREST_CONTAMINATION*100:.0f}% contamination assumed — actual anomaly
      rate unknown
    - Snow/ice transitions may still cause false positives despite SCL masking
    - Small ROI (2km²) — anomalies at site periphery may be missed
    - IForest is unsupervised — anomaly ≠ threat (may be construction,
      seasonal change, or sensor artifact)

  Cache: {CACHE_CSV}
  Rerun with fresh data: delete cache file to re-extract from GEE.
""")
