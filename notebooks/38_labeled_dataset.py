#!/usr/bin/env python3
"""
38. Labeled Hostile Campaign Dataset
======================================

Builds a unified labeled dataset for downstream research (Fisher, PLMSE,
community structure, narrative velocity). Merges:

1. cluster_framings.csv (30 framing analyses with is_hostile labels)
2. campaigns_full.csv (37 campaigns with severity/detection_method)
3. narrative_origins.csv (1,343 narrative tracking records)
4. cluster_members.csv (temporal + structural features per cluster)

Computes per-cluster features: state_ratio, category_count, signal_count,
burstiness, temporal span, source diversity. Labels come from framings
(ground truth) and campaigns (proxy: evidence-backed = hostile signal).

Output: output/labeled_clusters.csv — the shared dataset for R-40, R-41, R-43.
"""
import csv
import os
import json
import math
from collections import defaultdict, Counter
from datetime import datetime

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

# ================================================================
# 1. LOAD ALL DATA SOURCES
# ================================================================
print("=" * 72)
print("38. LABELED HOSTILE CAMPAIGN DATASET")
print("=" * 72)

# --- Cluster members: compute per-cluster features ---
print("\nLoading cluster members...")
cluster_signals = defaultdict(list)
with open(f"{DATA}/cluster_members.csv") as f:
    for row in csv.DictReader(f):
        cluster_signals[int(row['cluster_id'])].append(row)
print(f"  {len(cluster_signals)} clusters, {sum(len(v) for v in cluster_signals.values())} signals")

# --- Cluster metadata ---
print("Loading cluster metadata...")
cluster_meta = {}
with open(f"{DATA}/clusters.csv") as f:
    for row in csv.DictReader(f):
        cluster_meta[int(row['id'])] = row
print(f"  {len(cluster_meta)} clusters")

# --- Framing labels (ground truth) ---
print("Loading framing labels...")
framings = {}
with open(f"{DATA}/cluster_framings.csv") as f:
    for row in csv.DictReader(f):
        framings[int(row['cluster_id'])] = {
            'is_hostile': row['is_hostile'] == 't',
            'confidence': float(row['confidence']) if row['confidence'] else 0,
            'operation_name': row.get('operation_name', ''),
            'hostile_narrative': row.get('hostile_narrative', ''),
        }
print(f"  {len(framings)} framing analyses ({sum(1 for f in framings.values() if f['is_hostile'])} hostile, "
      f"{sum(1 for f in framings.values() if not f['is_hostile'])} clean)")

# --- Campaign data ---
print("Loading campaigns...")
campaigns = []
campaign_clusters = {}
with open(f"{DATA}/campaigns_full.csv") as f:
    for row in csv.DictReader(f):
        campaigns.append(row)
        cid = row.get('cluster_id', '').strip()
        if cid:
            try:
                campaign_clusters[int(cid)] = row
            except ValueError:
                pass
print(f"  {len(campaigns)} campaigns ({len(campaign_clusters)} with cluster_id)")

# --- Narrative origins ---
print("Loading narrative origins...")
narrative_by_cluster = {}
with open(f"{DATA}/narrative_origins.csv") as f:
    for row in csv.DictReader(f):
        cid = int(row['cluster_id'])
        narrative_by_cluster[cid] = {
            'is_state_origin': row['is_state_origin'] == 't',
            'first_category': row['first_category'],
            'category_count': int(row['category_count']),
            'categories': row['categories'],
        }
print(f"  {len(narrative_by_cluster)} narrative records")

# ================================================================
# 2. COMPUTE PER-CLUSTER FEATURES
# ================================================================
print("\n" + "=" * 72)
print("2. COMPUTING PER-CLUSTER FEATURES")
print("=" * 72)

STATE_CATEGORIES = {'ru_state', 'russian_state', 'ru_proxy'}
EVIDENCE_METHODS = {'framing_analysis', 'injection_cascade', 'outrage_chain', 'manual_analysis'}


def compute_features(cluster_id, signals):
    """Compute structural features for a single cluster."""
    n = len(signals)
    if n == 0:
        return None

    # Category analysis
    categories = Counter(s.get('source_category', '') for s in signals)
    categories.pop('', None)  # remove empty
    state_count = sum(v for k, v in categories.items() if k in STATE_CATEGORIES)
    state_ratio = state_count / n if n > 0 else 0

    # Source diversity
    sources = set(s.get('feed_handle', '') or s.get('channel', '') for s in signals)
    sources.discard('')
    source_types = Counter(s['source_type'] for s in signals)

    # Temporal features
    timestamps = []
    for s in signals:
        try:
            ts = datetime.fromisoformat(s['published_at'].replace('+00', '+00:00'))
            timestamps.append(ts)
        except (ValueError, KeyError):
            pass

    timestamps.sort()
    span_hours = 0
    burstiness = 0
    if len(timestamps) >= 2:
        span = (timestamps[-1] - timestamps[0]).total_seconds()
        span_hours = span / 3600

        # Burstiness: B = (CV - 1) / (CV + 1) where CV = std/mean of inter-arrival gaps
        gaps = [(timestamps[i+1] - timestamps[i]).total_seconds()
                for i in range(len(timestamps) - 1)]
        if gaps:
            mean_gap = np.mean(gaps)
            std_gap = np.std(gaps)
            cv = std_gap / mean_gap if mean_gap > 0 else 0
            burstiness = (cv - 1) / (cv + 1) if (cv + 1) != 0 else 0

    return {
        'cluster_id': cluster_id,
        'signal_count': n,
        'state_ratio': round(state_ratio, 4),
        'state_count': state_count,
        'category_count': len(categories),
        'source_count': len(sources),
        'source_type_count': len(source_types),
        'span_hours': round(span_hours, 2),
        'burstiness': round(burstiness, 4),
        'has_state': 1 if state_count > 0 else 0,
        'has_trusted': 1 if any(k not in STATE_CATEGORIES for k in categories) else 0,
        'is_mixed': 1 if (state_count > 0 and any(k not in STATE_CATEGORIES for k in categories)) else 0,
    }


features = {}
for cid, signals in cluster_signals.items():
    f = compute_features(cid, signals)
    if f:
        features[cid] = f

print(f"\nComputed features for {len(features)} clusters")

# Feature distribution
signal_counts = [f['signal_count'] for f in features.values()]
state_ratios = [f['state_ratio'] for f in features.values() if f['signal_count'] >= 3]
print(f"\nSignal count: mean={np.mean(signal_counts):.1f}, median={np.median(signal_counts):.0f}, max={max(signal_counts)}")
print(f"State ratio (N>=3): mean={np.mean(state_ratios):.3f}, median={np.median(state_ratios):.3f}")
print(f"Mixed clusters (state+trusted): {sum(1 for f in features.values() if f['is_mixed'])}")

# ================================================================
# 3. MERGE LABELS
# ================================================================
print("\n" + "=" * 72)
print("3. LABEL ASSIGNMENT")
print("=" * 72)

# Label hierarchy:
# 1. Framing analysis (ground truth, highest confidence)
# 2. Campaign with evidence method (strong proxy for hostile)
# 3. Campaign without evidence (weak proxy, not used as hostile label)
# 4. No label (unlabeled)

labeled = []
for cid, feat in features.items():
    label = None
    label_source = 'unlabeled'
    label_confidence = 0
    hostile_narrative = ''
    operation = ''

    # Check framing labels first
    if cid in framings:
        fr = framings[cid]
        label = fr['is_hostile']
        label_source = 'framing_analysis'
        label_confidence = fr['confidence']
        hostile_narrative = fr['hostile_narrative']
        operation = fr['operation_name']

    # Check campaign data
    elif cid in campaign_clusters:
        camp = campaign_clusters[cid]
        method = camp.get('detection_method', '')
        if method in EVIDENCE_METHODS:
            label = True
            label_source = f'campaign_{method}'
            label_confidence = float(camp.get('confidence', 0) or 0)
            hostile_narrative = ''
            operation = camp.get('name', '')

    row = {**feat,
           'label': 'hostile' if label is True else ('clean' if label is False else 'unlabeled'),
           'label_source': label_source,
           'label_confidence': label_confidence,
           'hostile_narrative': hostile_narrative,
           'operation': operation[:80],
           'is_state_origin': narrative_by_cluster.get(cid, {}).get('is_state_origin', ''),
           }
    labeled.append(row)

hostile = [r for r in labeled if r['label'] == 'hostile']
clean = [r for r in labeled if r['label'] == 'clean']
unlabeled = [r for r in labeled if r['label'] == 'unlabeled']

print(f"\nLabel distribution:")
print(f"  Hostile:   {len(hostile):>5d} (framing: {sum(1 for r in hostile if r['label_source'] == 'framing_analysis')}, "
      f"campaign: {sum(1 for r in hostile if r['label_source'].startswith('campaign_'))})")
print(f"  Clean:     {len(clean):>5d}")
print(f"  Unlabeled: {len(unlabeled):>5d}")

# ================================================================
# 4. FEATURE COMPARISON: HOSTILE vs CLEAN
# ================================================================
print("\n" + "=" * 72)
print("4. FEATURE COMPARISON")
print("=" * 72)

if hostile and clean:
    for feat_name in ['signal_count', 'state_ratio', 'category_count', 'source_count',
                      'span_hours', 'burstiness']:
        h_vals = [r[feat_name] for r in hostile]
        c_vals = [r[feat_name] for r in clean]
        print(f"\n  {feat_name}:")
        print(f"    Hostile (N={len(h_vals)}): mean={np.mean(h_vals):.3f}, median={np.median(h_vals):.3f}")
        print(f"    Clean  (N={len(c_vals)}): mean={np.mean(c_vals):.3f}, median={np.median(c_vals):.3f}")

        # Welch's t-test
        if len(h_vals) >= 2 and len(c_vals) >= 2:
            m_h, m_c = np.mean(h_vals), np.mean(c_vals)
            v_h, v_c = np.var(h_vals, ddof=1), np.var(c_vals, ddof=1)
            n_h, n_c = len(h_vals), len(c_vals)
            se = math.sqrt(v_h/n_h + v_c/n_c) if (v_h/n_h + v_c/n_c) > 0 else 1e-10
            t = (m_h - m_c) / se
            print(f"    Welch's t = {t:.3f}")

# ================================================================
# 5. SAVE LABELED DATASET
# ================================================================
print("\n" + "=" * 72)
print("5. SAVE LABELED DATASET")
print("=" * 72)

fields = ['cluster_id', 'signal_count', 'state_ratio', 'state_count',
          'category_count', 'source_count', 'source_type_count',
          'span_hours', 'burstiness', 'has_state', 'has_trusted', 'is_mixed',
          'label', 'label_source', 'label_confidence', 'hostile_narrative',
          'operation', 'is_state_origin']

with open(f"{OUTPUT}/labeled_clusters.csv", "w") as f:
    f.write(','.join(fields) + '\n')
    for row in sorted(labeled, key=lambda r: (r['label'] != 'hostile', r['cluster_id'])):
        values = []
        for field in fields:
            val = str(row.get(field, ''))
            if ',' in val or '"' in val or '\n' in val:
                val = '"' + val.replace('"', '""') + '"'
            values.append(val)
        f.write(','.join(values) + '\n')

print(f"\nSaved {len(labeled)} clusters to output/labeled_clusters.csv")
print(f"  Hostile: {len(hostile)}, Clean: {len(clean)}, Unlabeled: {len(unlabeled)}")

# Also save a summary for quick reference
summary = {
    'total_clusters': len(labeled),
    'hostile': len(hostile),
    'clean': len(clean),
    'unlabeled': len(unlabeled),
    'hostile_from_framing': sum(1 for r in hostile if r['label_source'] == 'framing_analysis'),
    'hostile_from_campaign': sum(1 for r in hostile if r['label_source'].startswith('campaign_')),
    'hostile_narratives': list(set(r['hostile_narrative'] for r in hostile if r['hostile_narrative'])),
}

import json
with open(f"{OUTPUT}/labeled_dataset_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"  Summary saved to output/labeled_dataset_summary.json")

# ================================================================
# ASSESSMENT
# ================================================================
print("\n" + "=" * 72)
print("ASSESSMENT")
print("=" * 72)
target_hostile = 33  # for Fisher p<0.01
gap = max(0, target_hostile - len(hostile))
print(f"""
Current labeled hostile clusters: {len(hostile)}
Target for Fisher p<0.01:         {target_hostile}
Gap:                              {gap} more hostile clusters needed

Label sources:
- Framing analysis: ground truth, highest confidence. {sum(1 for r in hostile if r['label_source'] == 'framing_analysis')} hostile.
- Evidence-backed campaigns: strong proxy. {sum(1 for r in hostile if r['label_source'].startswith('campaign_'))} hostile.

To reach N={target_hostile} hostile labels:
1. Run framing analysis on more mixed clusters (state + trusted media).
2. Cross-reference with EUvsDisinfo cases (manual labeling, ~2h effort).
3. Backfill Bild map and similar known campaigns as labeled cases.
4. Wait for the pipeline to accumulate new hostile framings (~2/week rate).

At current detection rate ({len(hostile)} hostile in ~50 days), reaching
N={target_hostile} will take approximately {gap * 50 // max(len(hostile), 1)} more days.

This dataset is ready for use in:
- R-40: Fisher + Hawkes revalidation
- R-41: Origin-agnostic velocity
- R-43: Community structure classification
""")
