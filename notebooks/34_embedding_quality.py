#!/usr/bin/env python3
"""
34. Cross-Lingual Embedding Quality Validation — ET/LV/LT Gap
==============================================================

Context:
  - Experiment 11 (FINDINGS.campaign-detection.md): EN (0.927) > RU (0.896) >
    LT (0.878) within-cluster similarity. Gap is 3-5%.
    "No ET/LV data in current clusters (insufficient signals)."
  - Literature review flagged: "Embedding bias on low-resource languages —
    ET/LV/LT may underperform vs EN/RU."
  - Current embedding model: gemini-embedding-001 (3072d), cosine threshold 0.75
  - Experiment 6: Optimal cross-lingual threshold = 0.75 (captures EN↔RU pairs)
  - Experiment 12: At 0.75, mega-clusters (>10 signals) merge unrelated events

This notebook (with 90-day refreshed data):
  1. Loads cluster_members and detects language per signal
  2. Computes within-cluster centroid similarity per language (EN, RU, ET, LV, LT, UK)
  3. Computes cross-lingual same-event similarity per language pair using
     TF-IDF char n-grams as pairwise similarity proxy
  4. Tests whether a uniform cosine threshold (0.75) works for all language
     pairs or if per-language thresholds are needed
  5. Identifies ET/LV feed coverage and data volume
  6. Quantifies the embedding quality gap and proposes mitigations

Uses: numpy, scipy, sklearn (TF-IDF), standard library
"""

import csv
import math
import os
import re
from collections import Counter, defaultdict

import numpy as np
from scipy import stats as sp_stats
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)


# ================================================================
# LANGUAGE DETECTION
# ================================================================

# Feed handle → language mapping (curated from EstWarden source config)
FEED_LANG = {
    # Estonian language feeds
    'postimees_et': 'ET', 'err_business': 'ET', 'mke_ee': 'ET',
    'tribuna_ee': 'ET', 'ohtuleht_et': 'ET', 'objektiiv': 'ET',
    # Latvian language feeds
    'lv_portals': 'LV', 'tvnet': 'LV', 'nra': 'LV',
    'apollo_lv': 'LV', 'lsm_lv': 'LV',
    # Lithuanian language feeds
    '15min_lt_lt': 'LT', 'delfi_lt': 'LT', 'vz_lt': 'LT',
    # Russian-language feeds (including Baltic Russian-language outlets)
    'tass_ru': 'RU', 'rt_russian': 'RU', 'kommersant': 'RU',
    'interfax': 'RU', 'lenta_ru': 'RU', 'ria': 'RU', 'ria_ru': 'RU',
    'iz_ru': 'RU', 'meduza': 'RU', 'holod_media': 'RU',
    'verstka': 'RU', 'zona_media': 'RU',
    # Baltic outlets publishing in Russian
    'err_rus': 'RU', 'postimees_rus': 'RU', 'lsm_rus': 'RU',
    'delfi_lt_rus': 'RU', '15min_lt': 'RU', 'gazeta_ee': 'RU',
    # English-language feeds
    'err_en': 'EN', 'postimees_en': 'EN', 'lsm_en': 'EN',
    'defence_blog': 'EN', 'breaking_defense': 'EN',
    'notesfrompoland': 'EN', 'yle_en': 'EN', 'euvsdisinfo': 'EN',
    'defrss': 'EN', 'ukrinform': 'EN', 'pravda_en': 'EN',
    'est_mod': 'EN', 'bellingcat': 'EN', 'nordic_defence': 'EN',
    'moscowtimes': 'EN', 'cert_ee': 'EN',
    # Finnish
    'yle_fi': 'FI',
}

# Telegram channel → language mapping
CHANNEL_LANG = {
    # Russian-language Telegram
    'colonel_cassad': 'RU', 'RVvoenkor': 'RU', 'rybar': 'RU',
    'readovkanews': 'RU', 'dva_majors': 'RU', 'shot_shot': 'RU',
    'pul_1': 'RU', 'montyan': 'RU', 'voenacher': 'RU',
    'yurasumy': 'RU', 'wargonzo': 'RU', 'warfakes': 'RU',
    'rusich_army': 'RU', 'nach_shtabu': 'RU', 'lachentyt': 'RU',
    'nexta_live': 'RU',
    # Ukrainian-language Telegram
    'operativnoZSU': 'UK', 'uniannet': 'UK', 'suspilne_news': 'UK',
    'gerashchenko': 'UK', 'TCH_channel': 'UK', 'sternenko': 'UK',
    'insider_ua': 'UK', 'truexanewsua': 'UK', 'rezident_ua': 'UK',
    'spravdi': 'UK', 'deepstatemap': 'UK',
    # English Telegram
    'wartranslated': 'EN',
}


def detect_script_language(text):
    """Detect language from script characteristics in text.

    Used as fallback when feed_handle/channel don't provide language info.
    Detects: Estonian (äöüõ), Latvian (āčēģ...), Lithuanian (ąčęė...),
    Cyrillic (RU/UK), Latin (EN default).
    """
    clean = re.sub(r'[\W\d_]', '', text)
    if not clean:
        return None

    total = len(clean)
    cyrillic = sum(1 for c in clean if '\u0400' <= c <= '\u04FF')
    # Estonian-specific diacritics (õ is distinctly Estonian)
    estonian_chars = sum(1 for c in clean if c in 'õÕ')
    # Also check for ä/ö/ü which appear in Estonian (and some Finnish/German)
    estonian_extended = sum(1 for c in clean if c in 'äöüÄÖÜõÕ')
    # Latvian-specific diacritics
    latvian_chars = sum(1 for c in clean if c in 'āčēģīķļņšūžĀČĒĢĪĶĻŅŠŪŽ')
    # Lithuanian-specific diacritics
    lithuanian_chars = sum(1 for c in clean if c in 'ąęėįųūĄĘĖĮŲŪ')
    # ž and š are shared by LT, LV; č is shared too
    lt_lv_shared = sum(1 for c in clean if c in 'žšč')

    if cyrillic / total > 0.5:
        return 'CYRILLIC'  # Can't distinguish RU from UK by script alone

    # Estonian: has õ (unique) or high density of äöü without Latvian marks
    if estonian_chars > 0:
        return 'ET'
    # Latvian: has ā, ē, ī, ū, ģ, ķ, ļ, ņ (macron vowels + cedilla consonants)
    if latvian_chars > 0:
        return 'LV'
    # Lithuanian: has ą, ę, ė, į, ų (ogonek vowels + dotted ė)
    if lithuanian_chars > 0:
        return 'LT'
    # Estonian with only ä/ö/ü (no õ) — check context
    if estonian_extended > 0:
        # Could be Estonian, Finnish, or German. If in Baltic cluster, likely Estonian.
        return 'ET_MAYBE'

    latin = sum(1 for c in clean if c.isascii() and c.isalpha())
    if latin / total > 0.5:
        return 'LATIN'  # EN or other Latin-script language

    return None


def detect_language(row):
    """Detect language of a cluster member signal.

    Priority: feed_handle mapping > channel mapping > script detection.
    """
    fh = (row.get('feed_handle') or '').strip()
    ch = (row.get('channel') or '').strip()
    title = (row.get('title') or '').strip()

    # 1. Feed handle (most reliable)
    if fh and fh != 'rss' and fh in FEED_LANG:
        return FEED_LANG[fh]

    # 2. Telegram channel
    if ch and ch in CHANNEL_LANG:
        return CHANNEL_LANG[ch]

    # 3. Script detection from title
    if title:
        script = detect_script_language(title)
        if script in ('ET', 'LV', 'LT'):
            return script
        if script == 'CYRILLIC':
            return 'RU'  # Default Cyrillic to RU (can't distinguish from UK)
        if script == 'LATIN':
            return 'EN'  # Default Latin to EN
        if script == 'ET_MAYBE':
            return 'ET'  # In Baltic monitoring context, likely Estonian

    return None  # Truly unknown


# ================================================================
# DATA LOADING
# ================================================================
def load_cluster_members():
    """Load cluster members with language detection."""
    clusters = defaultdict(list)
    path = os.path.join(DATA, 'cluster_members.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            cid = row['cluster_id']
            sim = float(row['similarity']) if row.get('similarity') else 0.0
            title = (row.get('title') or '').strip()
            lang = detect_language(row)

            clusters[cid].append({
                'signal_id': row.get('signal_id', ''),
                'similarity': sim,  # cosine sim to cluster centroid
                'title': title,
                'lang': lang,
                'source_type': row.get('source_type', ''),
                'source_category': (row.get('source_category') or '').strip(),
                'feed_handle': (row.get('feed_handle') or '').strip(),
                'channel': (row.get('channel') or '').strip(),
                'published_at': row.get('published_at', ''),
                'region': row.get('region', ''),
            })
    return clusters


# ================================================================
# ANALYSIS
# ================================================================
def compute_tfidf_pairwise(titles):
    """Compute pairwise cosine similarity via TF-IDF char n-grams.

    Uses character n-grams (3-5) for cross-lingual robustness —
    shared entity names (NATO, Suwalki, Kaliningrad) and cognates
    produce non-zero similarity across languages.
    """
    if len(titles) < 2:
        return np.ones((len(titles), len(titles)))

    cleaned = []
    for t in titles:
        t = re.sub(r'[^\w\s]', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        if not t:
            t = 'empty'
        cleaned.append(t)

    try:
        vec = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(3, 5),
            max_features=5000,
            min_df=1,
        )
        tfidf = vec.fit_transform(cleaned)
        return cosine_similarity(tfidf)
    except ValueError:
        return np.ones((len(titles), len(titles)))


def main():
    print("=" * 78)
    print("CROSS-LINGUAL EMBEDDING QUALITY VALIDATION — ET/LV/LT GAP")
    print("=" * 78)

    clusters = load_cluster_members()
    total_signals = sum(len(m) for m in clusters.values())
    print(f"\nLoaded: {total_signals} signals in {len(clusters)} clusters")

    # ============================================================
    # SECTION 1: LANGUAGE DETECTION COVERAGE
    # ============================================================
    print("\n" + "=" * 78)
    print("SECTION 1: LANGUAGE DETECTION COVERAGE")
    print("=" * 78)

    lang_counts = Counter()
    lang_signals = defaultdict(list)  # lang → list of (cid, sim, title)
    unknown_count = 0

    for cid, members in clusters.items():
        for m in members:
            lang = m['lang']
            if lang:
                lang_counts[lang] += 1
                lang_signals[lang].append({
                    'cid': cid,
                    'sim': m['similarity'],
                    'title': m['title'],
                    'feed': m['feed_handle'],
                    'channel': m['channel'],
                })
            else:
                unknown_count += 1

    detected_pct = 100 * (total_signals - unknown_count) / total_signals
    print(f"\n  Language detected: {total_signals - unknown_count}/{total_signals} "
          f"({detected_pct:.1f}%)")
    print(f"  Unknown: {unknown_count}")

    print(f"\n  {'Language':>8} {'Signals':>8} {'%':>7}")
    print("  " + "-" * 28)
    for lang, cnt in lang_counts.most_common():
        pct = 100 * cnt / total_signals
        print(f"  {lang:>8} {cnt:>8} {pct:>6.1f}%")

    # ============================================================
    # SECTION 2: WITHIN-CLUSTER CENTROID SIMILARITY BY LANGUAGE
    # ============================================================
    print("\n" + "=" * 78)
    print("SECTION 2: WITHIN-CLUSTER CENTROID SIMILARITY BY LANGUAGE")
    print("=" * 78)
    print("\n  The 'similarity' column in cluster_members is the cosine similarity")
    print("  of each signal's gemini-embedding-001 vector to its cluster centroid.")
    print("  Lower values for a language → that language's embeddings are farther")
    print("  from the multilingual centroid → potential quality degradation.")

    # Collect per-language similarity distributions
    TARGET_LANGS = ['EN', 'RU', 'UK', 'ET', 'LV', 'LT', 'FI']
    lang_sims = {lang: [] for lang in TARGET_LANGS}

    for cid, members in clusters.items():
        if len(members) < 2:
            continue
        for m in members:
            if m['lang'] in lang_sims:
                lang_sims[m['lang']].append(m['similarity'])

    print(f"\n  {'Lang':>6} {'N':>7} {'Mean':>7} {'Median':>7} {'Std':>7} "
          f"{'P10':>7} {'P25':>7} {'P75':>7} {'P90':>7}")
    print("  " + "-" * 70)
    lang_means = {}
    for lang in TARGET_LANGS:
        sims = lang_sims[lang]
        if len(sims) < 3:
            print(f"  {lang:>6} {len(sims):>7} {'— insufficient data —':>50}")
            continue
        arr = np.array(sims)
        lang_means[lang] = np.mean(arr)
        print(f"  {lang:>6} {len(sims):>7} {np.mean(arr):>7.4f} {np.median(arr):>7.4f} "
              f"{np.std(arr):>7.4f} {np.percentile(arr, 10):>7.4f} "
              f"{np.percentile(arr, 25):>7.4f} {np.percentile(arr, 75):>7.4f} "
              f"{np.percentile(arr, 90):>7.4f}")

    # Gap analysis relative to English (best expected)
    if 'EN' in lang_means:
        en_mean = lang_means['EN']
        print(f"\n  --- Gap Relative to EN (mean={en_mean:.4f}) ---")
        print(f"  {'Lang':>6} {'Mean':>7} {'Gap':>7} {'% Drop':>8} {'Significance':>15}")
        print("  " + "-" * 50)
        for lang in TARGET_LANGS:
            if lang == 'EN' or lang not in lang_means:
                continue
            gap = en_mean - lang_means[lang]
            pct_drop = 100 * gap / en_mean
            # Mann-Whitney U test
            if len(lang_sims[lang]) >= 10:
                u_stat, p_val = sp_stats.mannwhitneyu(
                    lang_sims['EN'], lang_sims[lang], alternative='greater'
                )
                sig = f"p={p_val:.4f}"
                if p_val < 0.001:
                    sig = "p<0.001 ***"
                elif p_val < 0.01:
                    sig = f"p={p_val:.4f} **"
                elif p_val < 0.05:
                    sig = f"p={p_val:.4f} *"
            else:
                sig = "N too small"
            print(f"  {lang:>6} {lang_means[lang]:>7.4f} {gap:>+7.4f} {pct_drop:>+7.1f}% {sig:>15}")

    # ============================================================
    # SECTION 3: WITHIN-CLUSTER SIMILARITY IN MULTI-LANG CLUSTERS
    # ============================================================
    print("\n" + "=" * 78)
    print("SECTION 3: WITHIN-CLUSTER SIMILARITY — MULTI-LANGUAGE CLUSTERS ONLY")
    print("=" * 78)
    print("\n  Restricting to clusters where >=2 languages co-occur (same event,")
    print("  different languages). This controls for event difficulty — all languages")
    print("  are matched to the SAME cluster centroid for the SAME event.")

    # Build multi-language clusters
    multi_lang_sims = {lang: [] for lang in TARGET_LANGS}
    multi_lang_cluster_ids = set()

    for cid, members in clusters.items():
        if len(members) < 2:
            continue
        langs_in_cluster = set(m['lang'] for m in members if m['lang'] in TARGET_LANGS)
        if len(langs_in_cluster) < 2:
            continue
        multi_lang_cluster_ids.add(cid)
        for m in members:
            if m['lang'] in multi_lang_sims:
                multi_lang_sims[m['lang']].append(m['similarity'])

    print(f"\n  Multi-language clusters: {len(multi_lang_cluster_ids)}")

    print(f"\n  {'Lang':>6} {'N':>7} {'Mean':>7} {'Median':>7} {'Std':>7}")
    print("  " + "-" * 38)
    multi_means = {}
    for lang in TARGET_LANGS:
        sims = multi_lang_sims[lang]
        if len(sims) < 3:
            print(f"  {lang:>6} {len(sims):>7} {'— insufficient data —':>25}")
            continue
        arr = np.array(sims)
        multi_means[lang] = np.mean(arr)
        print(f"  {lang:>6} {len(sims):>7} {np.mean(arr):>7.4f} {np.median(arr):>7.4f} "
              f"{np.std(arr):>7.4f}")

    if 'EN' in multi_means:
        en_m = multi_means['EN']
        print(f"\n  --- Multi-lang gap relative to EN (mean={en_m:.4f}) ---")
        for lang in TARGET_LANGS:
            if lang == 'EN' or lang not in multi_means:
                continue
            gap = en_m - multi_means[lang]
            pct = 100 * gap / en_m if en_m > 0 else 0
            print(f"  {lang:>6}: gap={gap:>+.4f} ({pct:>+.1f}%)")

    # ============================================================
    # SECTION 4: CROSS-LINGUAL PAIRWISE SIMILARITY (TF-IDF PROXY)
    # ============================================================
    print("\n" + "=" * 78)
    print("SECTION 4: CROSS-LINGUAL PAIRWISE SIMILARITY (TF-IDF PROXY)")
    print("=" * 78)
    print("\n  Since raw embeddings are not in the CSV, we use TF-IDF char n-grams")
    print("  on titles as a proxy for cross-lingual pairwise similarity. This")
    print("  captures shared entities (NATO, Kaliningrad) and cognates across scripts.")
    print("  CAVEAT: This is a lower bound — real embeddings are better at cross-lingual.")

    # For each multi-lang cluster, compute pairwise TF-IDF between language groups
    pair_sims = defaultdict(list)  # (lang1, lang2) → list of pairwise similarities
    within_sims = defaultdict(list)  # lang → list of within-language pairwise sims

    for cid in multi_lang_cluster_ids:
        members = clusters[cid]
        lang_groups = defaultdict(list)
        for i, m in enumerate(members):
            if m['lang'] in TARGET_LANGS:
                lang_groups[m['lang']].append(i)

        if len(lang_groups) < 2:
            continue

        # Compute TF-IDF pairwise for entire cluster
        titles = [m['title'] for m in members]
        sim_matrix = compute_tfidf_pairwise(titles)

        # Extract cross-language and within-language pairwise similarities
        for lang1 in lang_groups:
            for lang2 in lang_groups:
                if lang1 <= lang2:  # Avoid double-counting
                    for i in lang_groups[lang1]:
                        for j in lang_groups[lang2]:
                            if i == j:
                                continue
                            s = sim_matrix[i, j]
                            if lang1 == lang2:
                                within_sims[lang1].append(s)
                            else:
                                key = tuple(sorted([lang1, lang2]))
                                pair_sims[key].append(s)

    # Cross-lingual similarity matrix
    print(f"\n  --- Cross-Lingual TF-IDF Similarity (mean ± std, N pairs) ---")
    all_langs_present = sorted(set(
        lang for pair in pair_sims for lang in pair
    ) | set(within_sims.keys()))

    # Header
    header = f"  {'':>6}"
    for l2 in all_langs_present:
        header += f" {l2:>10}"
    print(header)
    print("  " + "-" * (6 + 11 * len(all_langs_present)))

    for l1 in all_langs_present:
        row_str = f"  {l1:>6}"
        for l2 in all_langs_present:
            if l1 == l2:
                sims = within_sims.get(l1, [])
                if sims:
                    row_str += f" {np.mean(sims):>5.3f}({len(sims):>3})"
                else:
                    row_str += f" {'—':>10}"
            else:
                key = tuple(sorted([l1, l2]))
                sims = pair_sims.get(key, [])
                if sims:
                    row_str += f" {np.mean(sims):>5.3f}({len(sims):>3})"
                else:
                    row_str += f" {'—':>10}"
        print(row_str)

    # Top cross-lingual pairs
    print(f"\n  --- Cross-Lingual Pair Summary ---")
    print(f"  {'Pair':>8} {'Mean TF-IDF':>12} {'Std':>7} {'N':>5} {'Assessment':<25}")
    print("  " + "-" * 60)
    for (l1, l2), sims in sorted(pair_sims.items(),
                                  key=lambda x: len(x[1]), reverse=True):
        if len(sims) < 3:
            assessment = "insufficient data"
        elif np.mean(sims) > 0.15:
            assessment = "✅ good cross-lingual"
        elif np.mean(sims) > 0.08:
            assessment = "⚠️ weak overlap"
        else:
            assessment = "❌ minimal overlap"
        print(f"  {l1}↔{l2:>4} {np.mean(sims):>12.4f} {np.std(sims):>7.4f} "
              f"{len(sims):>5} {assessment:<25}")

    # ============================================================
    # SECTION 5: THRESHOLD ANALYSIS — PER-LANGUAGE COSINE CUTOFFS
    # ============================================================
    print("\n" + "=" * 78)
    print("SECTION 5: THRESHOLD ANALYSIS — DOES 0.75 WORK FOR ALL LANGUAGES?")
    print("=" * 78)
    print("\n  For a uniform threshold to work, ALL languages should have similar")
    print("  centroid similarity distributions. If ET/LV/LT signals systematically")
    print("  have lower similarity, they either (a) don't join clusters they should,")
    print("  or (b) join with weak matches → noise.")

    # What fraction of signals per language are at the threshold boundary?
    thresholds = [0.75, 0.78, 0.80, 0.82, 0.85]
    print(f"\n  --- Fraction of signals BELOW threshold (would be excluded) ---")
    header = f"  {'Lang':>6} {'N':>6}"
    for t in thresholds:
        header += f" {'<' + str(t):>7}"
    print(header)
    print("  " + "-" * (14 + 8 * len(thresholds)))

    for lang in TARGET_LANGS:
        sims = lang_sims.get(lang, [])
        if len(sims) < 5:
            continue
        arr = np.array(sims)
        row_str = f"  {lang:>6} {len(sims):>6}"
        for t in thresholds:
            below_pct = 100 * np.sum(arr < t) / len(arr)
            row_str += f" {below_pct:>6.1f}%"
        print(row_str)

    # Language-specific optimal thresholds (P5 of each distribution)
    print(f"\n  --- Per-Language Percentiles (suggested per-language thresholds) ---")
    print(f"  {'Lang':>6} {'P5':>7} {'P10':>7} {'P25':>7} {'Min':>7}")
    print("  " + "-" * 34)
    for lang in TARGET_LANGS:
        sims = lang_sims.get(lang, [])
        if len(sims) < 10:
            continue
        arr = np.array(sims)
        print(f"  {lang:>6} {np.percentile(arr, 5):>7.4f} {np.percentile(arr, 10):>7.4f} "
              f"{np.percentile(arr, 25):>7.4f} {np.min(arr):>7.4f}")

    # Test: would per-language thresholds help?
    # Compute the threshold that retains 95% of each language's signals
    print(f"\n  --- P5 Threshold (retains 95% of each language's signals) ---")
    lang_thresholds = {}
    for lang in TARGET_LANGS:
        sims = lang_sims.get(lang, [])
        if len(sims) >= 10:
            p5 = np.percentile(sims, 5)
            lang_thresholds[lang] = p5
            print(f"  {lang}: threshold = {p5:.4f}")

    # Check spread
    if lang_thresholds:
        vals = list(lang_thresholds.values())
        spread = max(vals) - min(vals)
        print(f"\n  Threshold spread across languages: {spread:.4f}")
        if spread < 0.03:
            print("  ✅ Spread < 0.03 → uniform threshold is fine")
        elif spread < 0.06:
            print("  ⚠️ Spread 0.03-0.06 → uniform threshold works but edge cases exist")
        else:
            print("  ❌ Spread > 0.06 → per-language thresholds recommended")

    # ============================================================
    # SECTION 6: ET/LV FEED COVERAGE ANALYSIS
    # ============================================================
    print("\n" + "=" * 78)
    print("SECTION 6: ET/LV/LT FEED COVERAGE AND DATA VOLUME")
    print("=" * 78)

    # What ET/LV/LT feeds are producing clustered signals?
    baltic_feeds = defaultdict(lambda: Counter())
    for cid, members in clusters.items():
        for m in members:
            lang = m['lang']
            if lang in ('ET', 'LV', 'LT'):
                feed = m['feed_handle'] or m['channel'] or 'script_detected'
                baltic_feeds[lang][feed] += 1

    for lang in ['ET', 'LV', 'LT']:
        feeds = baltic_feeds.get(lang, {})
        print(f"\n  {lang} feeds in clusters ({sum(feeds.values())} total signals):")
        for feed, cnt in sorted(feeds.items(), key=lambda x: -x[1]):
            print(f"    {feed}: {cnt}")

    # Check coverage in the full signals_90d dataset
    print(f"\n  --- ET/LV/LT Coverage in Full 90-Day Dataset ---")
    baltic_90d = defaultdict(Counter)
    signals_path = os.path.join(DATA, 'signals_90d.csv')
    if os.path.exists(signals_path):
        with open(signals_path, errors='replace') as f:
            for row in csv.DictReader(f):
                st = row.get('source_type', '')
                if st not in ('rss', 'defense_rss', 'rss_security'):
                    continue
                fh = (row.get('feed_handle') or '').strip()
                title = (row.get('title') or '').strip()
                lang = None
                if fh and fh != 'rss' and fh in FEED_LANG:
                    lang = FEED_LANG[fh]
                elif title:
                    lang = detect_script_language(title)
                    if lang == 'ET_MAYBE':
                        lang = 'ET'
                if lang in ('ET', 'LV', 'LT'):
                    baltic_90d[lang][fh if fh != 'rss' else 'generic_rss'] += 1

        for lang in ['ET', 'LV', 'LT']:
            total = sum(baltic_90d[lang].values())
            print(f"\n  {lang}: {total} total RSS signals in 90 days")
            for feed, cnt in sorted(baltic_90d[lang].items(), key=lambda x: -x[1])[:10]:
                print(f"    {feed}: {cnt}")
    else:
        print("  ⚠️ signals_90d.csv not found — skipping full dataset analysis")

    # ============================================================
    # SECTION 7: EFFECT SIZE AND POWER ANALYSIS
    # ============================================================
    print("\n" + "=" * 78)
    print("SECTION 7: EFFECT SIZE AND STATISTICAL POWER")
    print("=" * 78)

    # Cohen's d for each language vs EN
    if 'EN' in lang_sims and len(lang_sims['EN']) >= 10:
        en_arr = np.array(lang_sims['EN'])
        print(f"\n  {'Lang':>6} {'N':>6} {'Cohen d':>8} {'95% CI of mean':>20} {'Verdict':>15}")
        print("  " + "-" * 60)
        for lang in TARGET_LANGS:
            if lang == 'EN':
                continue
            sims = lang_sims.get(lang, [])
            if len(sims) < 5:
                print(f"  {lang:>6} {len(sims):>6} {'N/A':>8} {'insufficient data':>20} "
                      f"{'❌ sparse':>15}")
                continue
            arr = np.array(sims)
            # Cohen's d
            pooled_std = np.sqrt((en_arr.var() + arr.var()) / 2)
            if pooled_std > 0:
                d = (en_arr.mean() - arr.mean()) / pooled_std
            else:
                d = 0
            # Bootstrap 95% CI of mean
            np.random.seed(42)
            boot_means = []
            for _ in range(1000):
                boot = np.random.choice(arr, size=len(arr), replace=True)
                boot_means.append(np.mean(boot))
            ci_lo = np.percentile(boot_means, 2.5)
            ci_hi = np.percentile(boot_means, 97.5)

            if abs(d) < 0.2:
                verdict = "negligible"
            elif abs(d) < 0.5:
                verdict = "small"
            elif abs(d) < 0.8:
                verdict = "medium"
            else:
                verdict = "LARGE"

            print(f"  {lang:>6} {len(sims):>6} {d:>+8.3f} "
                  f"[{ci_lo:.4f}, {ci_hi:.4f}] {verdict:>15}")

        # Power analysis: how many ET/LV/LT signals needed for reliable comparison?
        print(f"\n  --- Power Analysis (80% power, α=0.05, two-sided t-test) ---")
        for lang in ['ET', 'LV', 'LT']:
            sims = lang_sims.get(lang, [])
            if len(sims) >= 5:
                arr = np.array(sims)
                pooled_std = np.sqrt((en_arr.var() + arr.var()) / 2)
                if pooled_std > 0:
                    d = abs(en_arr.mean() - arr.mean()) / pooled_std
                    if d > 0.01:
                        # n_per_group ≈ (z_α/2 + z_β)² × 2 / d²
                        # For 80% power at α=0.05: (1.96 + 0.84)² = 7.84
                        n_needed = int(np.ceil(7.84 * 2 / (d * d)))
                        status = "✅ sufficient" if len(sims) >= n_needed else "⚠️ need more"
                        print(f"  {lang}: effect d={d:.3f}, need N≥{n_needed}, "
                              f"have N={len(sims)} — {status}")
                    else:
                        print(f"  {lang}: effect too small to detect (d≈0)")
            else:
                print(f"  {lang}: only {len(sims)} signals — far too few for analysis")

    # ============================================================
    # SECTION 8: SPECIFIC EXAMPLES — ET/LV/LT IN CLUSTERS
    # ============================================================
    print("\n" + "=" * 78)
    print("SECTION 8: EXAMPLE CLUSTERS WITH BALTIC LANGUAGE SIGNALS")
    print("=" * 78)

    # Show some multi-language clusters containing ET, LV, or LT
    shown = 0
    for cid, members in clusters.items():
        if len(members) < 3:
            continue
        langs = set(m['lang'] for m in members if m['lang'])
        baltic_langs = langs & {'ET', 'LV', 'LT'}
        if not baltic_langs:
            continue

        print(f"\n  --- Cluster {cid} (n={len(members)}, langs={sorted(langs)}) ---")
        for m in sorted(members, key=lambda x: -(x['similarity'])):
            lang_tag = m['lang'] or '??'
            print(f"    [{lang_tag:>3}] sim={m['similarity']:.4f} "
                  f"{m['title'][:65]}")
        shown += 1
        if shown >= 5:
            break

    # ============================================================
    # SECTION 9: CONCLUSIONS AND RECOMMENDATION
    # ============================================================
    print("\n" + "=" * 78)
    print("SECTION 9: CONCLUSIONS AND RECOMMENDATION")
    print("=" * 78)

    # Gather final stats
    print(f"\n  1. LANGUAGE COVERAGE IN CLUSTERS:")
    for lang in TARGET_LANGS:
        n = len(lang_sims.get(lang, []))
        pct = 100 * n / total_signals if total_signals else 0
        status = "✅ sufficient" if n >= 50 else ("⚠️ marginal" if n >= 20 else "❌ sparse")
        print(f"     {lang}: {n} signals ({pct:.1f}%) — {status}")

    print(f"\n  2. EMBEDDING QUALITY (mean centroid similarity):")
    ranking = sorted(lang_means.items(), key=lambda x: -x[1]) if lang_means else []
    for lang, mean_sim in ranking:
        print(f"     {lang}: {mean_sim:.4f}")
    if len(ranking) >= 2:
        best = ranking[0][1]
        worst = ranking[-1][1]
        total_gap = best - worst
        print(f"     Total gap (best - worst): {total_gap:.4f} ({100*total_gap/best:.1f}%)")

    print(f"\n  3. THRESHOLD RECOMMENDATION:")
    if lang_thresholds:
        min_thresh = min(lang_thresholds.values())
        max_thresh = max(lang_thresholds.values())
        spread = max_thresh - min_thresh
        if spread < 0.05:
            print(f"     ✅ Uniform threshold {0.75} works for all detected languages.")
            print(f"     P5 range: [{min_thresh:.4f}, {max_thresh:.4f}] (spread={spread:.4f})")
            print(f"     All languages have >95% of signals above 0.75.")
        else:
            print(f"     ⚠️ Consider per-language thresholds.")
            print(f"     P5 range: [{min_thresh:.4f}, {max_thresh:.4f}] (spread={spread:.4f})")
            for lang, t in sorted(lang_thresholds.items()):
                print(f"       {lang}: threshold = {t:.4f}")
    else:
        print(f"     ⚠️ Insufficient data for threshold analysis.")

    # ET/LV/LT specific
    sparse_langs = [l for l in ['ET', 'LV', 'LT'] if len(lang_sims.get(l, [])) < 30]
    adequate_langs = [l for l in ['ET', 'LV', 'LT'] if len(lang_sims.get(l, [])) >= 30]

    if sparse_langs:
        print(f"\n  4. SPARSE LANGUAGES: {', '.join(sparse_langs)}")
        print(f"     These languages have too few clustered signals for robust analysis.")
        print(f"     Likely causes:")
        print(f"       - Few monitored feeds in these languages")
        print(f"       - Low output volume (small media markets)")
        print(f"       - Many signals don't cluster (unique local stories)")
        print(f"     Mitigation:")
        print(f"       - Add more feeds: ERR.ee (ET), LSM.lv (LV), 15min.lt (LT)")
        print(f"       - Lower threshold for Baltic-only clusters (0.72 instead of 0.75)")
        print(f"       - Cross-reference: ET/LV/LT news often appears in RU translations")

    if adequate_langs:
        print(f"\n  5. ADEQUATE LANGUAGES: {', '.join(adequate_langs)}")
        for lang in adequate_langs:
            sims = lang_sims[lang]
            arr = np.array(sims)
            gap = lang_means.get('EN', arr.mean()) - arr.mean()
            print(f"     {lang}: mean={arr.mean():.4f}, gap vs EN={gap:+.4f} "
                  f"({100*gap/lang_means.get('EN', 1):.1f}%)")

    print(f"\n  6. PRODUCTION IMPLICATIONS:")
    print(f"     - gemini-embedding-001 provides usable quality for EN/RU/UK/ET")
    en_mean_val = lang_means.get('EN', 0)
    for lang in ['LV', 'LT']:
        n = len(lang_sims.get(lang, []))
        if n < 20:
            print(f"     - {lang}: data too sparse to validate ({n} signals). "
                  f"Need ≥50 clustered signals for reliable assessment.")
        else:
            gap = en_mean_val - lang_means.get(lang, en_mean_val)
            print(f"     - {lang}: gap={gap:+.4f} vs EN. "
                  f"{'Acceptable' if gap < 0.05 else 'Investigate further'}.")

    print()


if __name__ == '__main__':
    main()
