#!/usr/bin/env python3
"""
37. Fabrication Same-Event Gate
================================

nb31 found that fabrication alerts with score=10 often compare signals from
DIFFERENT EVENTS, not actual fabrication. The detector conflates topic drift
with deliberate falsification.

Fix: Add a title similarity check between root and downstream signals.
If cosine similarity < threshold, the pair is different events, not fabrication.

Method:
1. Load all fabrication alerts with root/downstream titles
2. Compute title similarity using character n-gram overlap (no ML needed)
3. Analyze score distribution by similarity bucket
4. Recommend same-event gate threshold
5. Estimate precision improvement

Data: fabrication_alerts.csv (50 alerts)
"""
import csv
import os
import re
import math
from collections import Counter

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

# ================================================================
# 1. LOAD FABRICATION ALERTS
# ================================================================
print("=" * 72)
print("37. FABRICATION SAME-EVENT GATE")
print("=" * 72)

alerts = []
with open(f"{DATA}/fabrication_alerts.csv") as f:
    for row in csv.DictReader(f):
        alerts.append(row)

print(f"\nLoaded {len(alerts)} fabrication alerts")

# Score distribution
scores = [int(row['fabrication_score']) for row in alerts]
print(f"\nScore distribution:")
for s in sorted(set(scores)):
    count = scores.count(s)
    print(f"  Score {s:>2d}: {count:>3d} alerts ({count/len(alerts)*100:.0f}%)")


# ================================================================
# 2. TITLE SIMILARITY (CHARACTER N-GRAM JACCARD)
# ================================================================
print("\n" + "=" * 72)
print("2. TITLE SIMILARITY ANALYSIS")
print("=" * 72)


def normalize_text(text):
    """Strip URLs, punctuation, lowercase for comparison."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return ' '.join(text.split())


def char_ngrams(text, n=3):
    """Extract character n-grams from text."""
    text = normalize_text(text)
    return Counter(text[i:i+n] for i in range(len(text) - n + 1))


def ngram_similarity(text_a, text_b, n=3):
    """Jaccard similarity on character n-grams. Works cross-lingually."""
    if not text_a or not text_b:
        return 0.0
    a = char_ngrams(text_a, n)
    b = char_ngrams(text_b, n)
    if not a or not b:
        return 0.0
    intersection = sum((a & b).values())
    union = sum((a | b).values())
    return intersection / union if union > 0 else 0.0


def word_overlap(text_a, text_b):
    """Word-level Jaccard overlap."""
    a = set(normalize_text(text_a).split())
    b = set(normalize_text(text_b).split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# Compute similarity for each alert
for alert in alerts:
    root_title = alert.get('root_title', '')
    down_title = alert.get('down_title', '')
    alert['ngram_sim'] = ngram_similarity(root_title, down_title)
    alert['word_sim'] = word_overlap(root_title, down_title)
    alert['score_int'] = int(alert['fabrication_score'])

sims = [a['ngram_sim'] for a in alerts]
print(f"\nN-gram similarity distribution:")
print(f"  Mean:   {np.mean(sims):.4f}")
print(f"  Median: {np.median(sims):.4f}")
print(f"  Min:    {np.min(sims):.4f}")
print(f"  Max:    {np.max(sims):.4f}")
print(f"  P10:    {np.percentile(sims, 10):.4f}")
print(f"  P25:    {np.percentile(sims, 25):.4f}")

# ================================================================
# 3. SCORE vs SIMILARITY CROSS-TAB
# ================================================================
print("\n" + "=" * 72)
print("3. FABRICATION SCORE vs TITLE SIMILARITY")
print("=" * 72)

# Bucket by similarity
SIM_BUCKETS = [(0.0, 0.05, "< 0.05 (different events)"),
               (0.05, 0.15, "0.05-0.15 (low overlap)"),
               (0.15, 0.30, "0.15-0.30 (moderate)"),
               (0.30, 1.01, ">= 0.30 (same event)")]

print(f"\n  {'Similarity Bucket':>30s} {'Count':>5s} {'Avg Score':>9s} {'Max':>4s} {'Categories':>30s}")
print("  " + "-" * 85)

for lo, hi, label in SIM_BUCKETS:
    bucket = [a for a in alerts if lo <= a['ngram_sim'] < hi]
    if not bucket:
        print(f"  {label:>30s} {0:>5d} {'':>9s} {'':>4s}")
        continue
    avg_score = np.mean([a['score_int'] for a in bucket])
    max_score = max(a['score_int'] for a in bucket)
    # Show root->down category patterns
    cats = Counter(f"{a['root_category']}->{a['down_category']}" for a in bucket)
    top_cats = ', '.join(f"{c}" for c, _ in cats.most_common(3))
    print(f"  {label:>30s} {len(bucket):>5d} {avg_score:>9.1f} {max_score:>4d} {top_cats:>30s}")

# ================================================================
# 4. DETAILED VIEW OF LOW-SIMILARITY HIGH-SCORE ALERTS
# ================================================================
print("\n" + "=" * 72)
print("4. LIKELY FALSE POSITIVES (low similarity + high score)")
print("=" * 72)

false_pos = [a for a in alerts if a['ngram_sim'] < 0.10 and a['score_int'] >= 7]
print(f"\nAlerts with similarity < 0.10 AND score >= 7: {len(false_pos)}")
for a in false_pos:
    root = (a.get('root_title', '')[:80]).replace('\n', ' ')
    down = (a.get('down_title', '')[:80]).replace('\n', ' ')
    print(f"\n  Alert {a['id']}: score={a['score_int']}, sim={a['ngram_sim']:.3f}")
    print(f"  Root [{a['root_category']}]: {root}")
    print(f"  Down [{a['down_category']}]: {down}")

# ================================================================
# 5. GATE THRESHOLD ANALYSIS
# ================================================================
print("\n" + "=" * 72)
print("5. SAME-EVENT GATE THRESHOLD ANALYSIS")
print("=" * 72)

# For each threshold, compute what we'd filter and keep
print(f"\n  {'Threshold':>9s} {'Filtered':>8s} {'Kept':>5s} {'Avg Score Kept':>14s} {'Avg Score Filtered':>18s}")
print("  " + "-" * 65)

for threshold in [0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30]:
    kept = [a for a in alerts if a['ngram_sim'] >= threshold]
    filtered = [a for a in alerts if a['ngram_sim'] < threshold]
    avg_kept = np.mean([a['score_int'] for a in kept]) if kept else 0
    avg_filtered = np.mean([a['score_int'] for a in filtered]) if filtered else 0
    print(f"  {threshold:>9.2f} {len(filtered):>8d} {len(kept):>5d} {avg_kept:>14.1f} {avg_filtered:>18.1f}")

# ================================================================
# 6. RELEVANCE FILTER (Baltic/security)
# ================================================================
print("\n" + "=" * 72)
print("6. REGION RELEVANCE CHECK")
print("=" * 72)

# Check how many alerts are about Baltic/security vs other topics
baltic_keywords = {'baltic', 'estonia', 'latvia', 'lithuania', 'finland', 'poland',
                   'nato', 'eesti', 'läti', 'leedu', 'tallinn', 'riga', 'vilnius',
                   'эстони', 'латви', 'литв', 'балтий', 'нато', 'прибалт'}

def is_baltic_relevant(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in baltic_keywords)

baltic_alerts = []
nonbaltic_alerts = []
for a in alerts:
    combined_text = (a.get('root_title', '') + ' ' + a.get('down_title', '') +
                    ' ' + a.get('summary', ''))
    if is_baltic_relevant(combined_text):
        baltic_alerts.append(a)
    else:
        nonbaltic_alerts.append(a)

print(f"\nBaltic/security relevant: {len(baltic_alerts)} ({len(baltic_alerts)/len(alerts)*100:.0f}%)")
print(f"Non-Baltic (noise):       {len(nonbaltic_alerts)} ({len(nonbaltic_alerts)/len(alerts)*100:.0f}%)")

if nonbaltic_alerts:
    print(f"\nNon-Baltic alert topics (should not contribute to Baltic CTI):")
    for a in nonbaltic_alerts[:10]:
        root = (a.get('root_title', '')[:70]).replace('\n', ' ')
        print(f"  [{a['root_category']}] score={a['score_int']}: {root}")

# ================================================================
# 7. COMBINED FILTER IMPACT
# ================================================================
print("\n" + "=" * 72)
print("7. COMBINED FILTER: same-event gate + relevance")
print("=" * 72)

RECOMMENDED_SIM_THRESHOLD = 0.08

passed = [a for a in alerts
          if a['ngram_sim'] >= RECOMMENDED_SIM_THRESHOLD
          and is_baltic_relevant(a.get('root_title', '') + ' ' + a.get('down_title', '') +
                                  ' ' + a.get('summary', ''))]
total_original_score = sum(a['score_int'] for a in alerts)
total_filtered_score = sum(a['score_int'] for a in passed)

print(f"\nOriginal alerts:            {len(alerts)}")
print(f"After same-event gate:      {sum(1 for a in alerts if a['ngram_sim'] >= RECOMMENDED_SIM_THRESHOLD)}")
print(f"After + relevance filter:   {len(passed)}")
print(f"\nRaw score sum:  {total_original_score} -> {total_filtered_score} "
      f"({(1 - total_filtered_score/total_original_score)*100:.0f}% reduction)")

# Save detailed results
with open(f"{OUTPUT}/fabrication_gate_analysis.csv", "w") as f:
    f.write("alert_id,cluster_id,fabrication_score,ngram_similarity,word_similarity,"
            "is_baltic_relevant,root_category,down_category,gate_pass\n")
    for a in alerts:
        combined_text = a.get('root_title', '') + ' ' + a.get('down_title', '') + ' ' + a.get('summary', '')
        relevant = is_baltic_relevant(combined_text)
        gate_pass = a['ngram_sim'] >= RECOMMENDED_SIM_THRESHOLD and relevant
        f.write(f"{a['id']},{a['cluster_id']},{a['score_int']},{a['ngram_sim']:.4f},"
                f"{a['word_sim']:.4f},{relevant},{a['root_category']},{a['down_category']},{gate_pass}\n")

print(f"\nSaved to output/fabrication_gate_analysis.csv")

# ================================================================
# RECOMMENDATIONS
# ================================================================
print("\n" + "=" * 72)
print("RECOMMENDATIONS")
print("=" * 72)
print(f"""
1. SAME-EVENT GATE: Require n-gram title similarity >= {RECOMMENDED_SIM_THRESHOLD}
   between root and downstream signal before fabrication scoring.
   Eliminates pairs that are clearly different events.

2. RELEVANCE FILTER: Require Baltic/security keyword match before
   fabrication alerts contribute to CTI score.
   Eliminates Iran, Middle East, sports noise.

3. BINARY CTI CONTRIBUTION: Use fabrication_present (bool) rather
   than raw score for CTI. Score 4 vs 10 distinction is unreliable
   (LLM-mood-dependent per nb31).

4. HYSTERESIS: New alert >= score 6, confirmed (2+ detections) >= 4.
   Run fabrication detection daily for >= 4 weeks for temporal baseline.

Combined impact: ~{(1 - total_filtered_score/total_original_score)*100:.0f}% reduction in fabrication CTI contribution.
""")
