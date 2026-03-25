#!/usr/bin/env python3
"""
28. Intent-Based Inoculation (IBI) Prompt Test
===============================================

Context:
  - Literature review (arXiv:2603.14525v1): Intent-Based Inoculation boosts
    zero-shot F1 by 9-20% on cross-lingual disinfo tasks
  - Experiment 25: Fisher discriminant (state_ratio + fimi_score) F1=0.92
  - Experiment 14: LLM confidence doesn't separate hostile from clean
  - Production framing prompt compares state vs trusted coverage factually
  - 18 LLM-analyzed framing cases (6 hostile, 12 clean) with ground truth

This notebook:
  1. Loads all 18 LLM-analyzed framing analyses with ground truth
  2. Prepares signal summaries per cluster (state vs trusted coverage)
  3. Runs CURRENT-style prompt on each via local LLM (phi4-reasoning:14b)
  4. Runs IBI prompt ("if a hostile actor wanted to undermine NATO/Baltic
     security, would this coverage serve that goal?")
  5. Compares: agreement matrix, flipped labels, precision/recall
  6. Tests on phi4-reasoning:14b and deepseek-r1:14b for robustness

Uses: standard library + numpy + json + urllib (for Anthropic Messages API)
Inference: Anthropic claude-sonnet-4-6 (fast, high quality)
"""

import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

# Remote inference endpoint
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
DEFAULT_MODEL = 'claude-sonnet-4-6-20250514'
FALLBACK_MODEL = 'deepseek-r1:14b'

# ================================================================
# CATEGORY MAPPING
# ================================================================
STATE_CATS = {'russian_state', 'ru_state', 'pro_kremlin', 'RU_STATE'}
TRUSTED_CATS = {'estonian_media', 'baltic_media', 'government',
                'counter_disinfo', 'T1', 'T2', 't1', 't2', 'polish_media',
                'finnish_media', 'lithuanian_media', 'latvian_media',
                'trusted', 'ukraine_media', 'defense_osint',
                'russian_independent', 'russian_language_ee'}


def classify_category(cat):
    """Classify signal source into state/trusted/other."""
    cat = cat.strip()
    if cat.lower() in {c.lower() for c in STATE_CATS}:
        return 'state'
    if cat.lower() in {c.lower() for c in TRUSTED_CATS}:
        return 'trusted'
    if cat == '' or cat.lower() in {'', 'data_source'}:
        return 'unknown'
    return 'other'


# ================================================================
# DATA LOADING
# ================================================================

def load_framing_analyses():
    """Load all cluster framings, filter to LLM-analyzed only."""
    analyses = []
    path = os.path.join(DATA, 'cluster_framings.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            # Skip auto-classified (Fisher pre-screen) — no framing text
            if 'Auto-classified' in (row.get('event_fact', '') or ''):
                continue
            is_hostile = row.get('is_hostile', 'f') == 't'
            analyses.append({
                'framing_id': int(row['framing_id']),
                'cluster_id': row['cluster_id'],
                'is_hostile': is_hostile,
                'label': 1 if is_hostile else 0,
                'confidence': float(row.get('confidence', 0) or 0),
                'operation_name': row.get('operation_name', ''),
                'hostile_narrative': row.get('hostile_narrative', ''),
                'event_fact': row.get('event_fact', ''),
                'state_framing': row.get('state_framing', ''),
                'framing_delta': row.get('framing_delta', ''),
            })
    return analyses


def load_cluster_signals():
    """Load signals per cluster from framing_cluster_signals.csv."""
    clusters = defaultdict(list)
    path = os.path.join(DATA, 'framing_cluster_signals.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            cid = row.get('cluster_id', '')
            cat = row.get('source_category', '').strip()
            side = classify_category(cat)
            clusters[cid].append({
                'title': row.get('title', ''),
                'source_category': cat,
                'side': side,
                'feed_handle': row.get('feed_handle', ''),
                'channel': row.get('channel', ''),
                'published_at': row.get('published_at', ''),
            })
    return clusters


def prepare_signal_summary(signals):
    """Create a text summary of state vs trusted signals for a cluster."""
    state_sigs = [s for s in signals if s['side'] == 'state']
    trusted_sigs = [s for s in signals if s['side'] in ('trusted', 'other')]
    # Include unknown-category signals with trusted if they look non-state
    unknown_sigs = [s for s in signals if s['side'] == 'unknown']

    state_titles = [s['title'][:200] for s in state_sigs if s['title'].strip()]
    trusted_titles = [s['title'][:200] for s in trusted_sigs if s['title'].strip()]
    unknown_titles = [s['title'][:200] for s in unknown_sigs if s['title'].strip()]

    summary = "RUSSIAN STATE MEDIA COVERAGE:\n"
    if state_titles:
        for i, t in enumerate(state_titles[:8], 1):
            summary += f"  {i}. {t}\n"
    else:
        summary += "  (no state media signals)\n"

    summary += "\nTRUSTED/INDEPENDENT MEDIA COVERAGE:\n"
    all_trusted = trusted_titles + unknown_titles
    if all_trusted:
        for i, t in enumerate(all_trusted[:8], 1):
            summary += f"  {i}. {t}\n"
    else:
        summary += "  (no trusted media signals)\n"

    return summary, len(state_titles), len(all_trusted)


# ================================================================
# ANTHROPIC INFERENCE
# ================================================================

def anthropic_generate(prompt, model=DEFAULT_MODEL, temperature=0.1, timeout=120):
    """Call Anthropic Messages API. Returns response text or None on failure."""
    url = "https://api.anthropic.com/v1/messages"
    payload = json.dumps({
        "model": model,
        "max_tokens": 2048,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            content = data.get('content', [])
            return content[0]['text'] if content else ''
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"  ERROR: Anthropic request failed: {e}")
        return None
    except Exception as e:
        print(f"  ERROR: unexpected: {e}")
        return None


def check_api():
    """Verify Anthropic API key is set."""
    if not ANTHROPIC_API_KEY:
        # Try loading from pi-bw-get
        try:
            import subprocess
            key = subprocess.check_output(
                ['pi-bw-get', 'Anthropic'], text=True, timeout=10
            ).strip()
            if key:
                global ANTHROPIC_API_KEY
                ANTHROPIC_API_KEY = key
                os.environ['ANTHROPIC_API_KEY'] = key
        except Exception:
            pass
    if ANTHROPIC_API_KEY:
        return [DEFAULT_MODEL]
    return []


# ================================================================
# PROMPT TEMPLATES
# ================================================================

CURRENT_PROMPT = """You are a media framing analyst monitoring Baltic security. Compare how Russian state media and trusted/independent media cover the same event.

EVENT SIGNALS:
{signal_summary}

TASK:
1. What is the factual event being covered?
2. How does Russian state media frame this event?
3. How does trusted/independent media frame this event?
4. Is there a significant framing difference that constitutes hostile information manipulation?

CLASSIFICATION:
- HOSTILE: State media introduces fabricated claims, uses hedging language to cast doubt on verified facts, omits critical context to mislead, or amplifies a narrative to serve Russian strategic interests in a way that goes beyond normal editorial differences.
- CLEAN: Normal editorial differences, legitimate reporting from different perspectives, or factual coverage without manipulation.

Respond with EXACTLY this format:
VERDICT: HOSTILE or CLEAN
CONFIDENCE: 0.0-1.0
REASONING: One paragraph explaining your classification."""

IBI_PROMPT = """You are a counter-disinformation analyst. A hostile actor wants to undermine NATO cohesion, destabilize Baltic states (Estonia, Latvia, Lithuania), and promote the narrative that Western institutions are weak or failing.

Examine how Russian state media covers this event compared to trusted/independent media. Ask yourself: "If I were running an information operation against NATO/Baltic security, would this coverage pattern serve my goals?"

EVENT SIGNALS:
{signal_summary}

INTENT-BASED ANALYSIS:
1. What is the factual event?
2. Does Russian state media's framing serve hostile strategic goals (undermining NATO, destabilizing Baltics, promoting Western weakness)?
3. Are there specific manipulation techniques: fabrication, hedging ("allegedly", "as claimed"), selective omission of context, coordinated amplification?
4. Would a hostile information operator be satisfied with this coverage, or is it just normal journalism?

CLASSIFICATION:
- HOSTILE: The framing pattern would serve a hostile actor's goals of undermining NATO/Baltic security through identifiable manipulation techniques (not just editorial bias).
- CLEAN: Normal journalism. Even if state media has a different angle, it does not constitute deliberate information manipulation serving hostile strategic goals.

Respond with EXACTLY this format:
VERDICT: HOSTILE or CLEAN
CONFIDENCE: 0.0-1.0
REASONING: One paragraph explaining your classification."""


def parse_verdict(response):
    """Parse VERDICT, CONFIDENCE, and REASONING from LLM response."""
    if not response:
        return {'verdict': None, 'confidence': 0.0, 'reasoning': 'NO RESPONSE'}

    # Strip thinking tags if present (phi4-reasoning, deepseek-r1)
    text = response.strip()
    if '</think>' in text:
        text = text.split('</think>')[-1].strip()

    # Strip markdown bold formatting (**VERDICT:** → VERDICT:)
    text_clean = re.sub(r'\*\*([A-Z]+):\*\*', r'\1:', text)

    # Extract verdict
    verdict = None
    v_match = re.search(r'VERDICT:\s*(HOSTILE|CLEAN)', text_clean, re.IGNORECASE)
    if v_match:
        verdict = v_match.group(1).upper()
    else:
        # Fallback: look for keywords in the non-thinking portion
        text_lower = text_clean.lower()
        if 'hostile' in text_lower and 'clean' not in text_lower:
            verdict = 'HOSTILE'
        elif 'clean' in text_lower:
            verdict = 'CLEAN'

    # Extract confidence
    confidence = 0.5
    c_match = re.search(r'CONFIDENCE:\s*([\d.]+)', text_clean, re.IGNORECASE)
    if c_match:
        try:
            confidence = float(c_match.group(1))
        except ValueError:
            pass

    # Extract reasoning
    reasoning = ''
    r_match = re.search(r'REASONING:\s*(.+)', text_clean, re.DOTALL | re.IGNORECASE)
    if r_match:
        reasoning = r_match.group(1).strip()[:500]

    return {'verdict': verdict, 'confidence': confidence, 'reasoning': reasoning}


# ================================================================
# METRICS
# ================================================================

def compute_metrics(y_true, y_pred):
    """Compute precision, recall, F1, accuracy from binary arrays."""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    tp = np.sum((y_pred == 1) & (y_true == 1))
    fp = np.sum((y_pred == 1) & (y_true == 0))
    fn = np.sum((y_pred == 0) & (y_true == 1))
    tn = np.sum((y_pred == 0) & (y_true == 0))

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
    acc = (tp + tn) / len(y_true) if len(y_true) > 0 else 0

    return {
        'precision': prec, 'recall': rec, 'f1': f1, 'accuracy': acc,
        'tp': int(tp), 'fp': int(fp), 'fn': int(fn), 'tn': int(tn),
    }


# ================================================================
# MAIN
# ================================================================

def main():
    np.random.seed(42)

    print("=" * 78)
    print("28. INTENT-BASED INOCULATION (IBI) PROMPT TEST")
    print("=" * 78)
    print("\nRef: arXiv:2603.14525v1 — IBI boosts zero-shot F1 by 9-20%")
    print("     on cross-lingual disinformation detection tasks.")

    # ------------------------------------------------------------------
    # 1. CHECK INFERENCE AVAILABILITY
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 1: INFERENCE SETUP")
    print("=" * 78)

    available_models = check_api()
    if not available_models:
        print("\n  ERROR: Cannot authenticate with Anthropic API.")
        print("  Set ANTHROPIC_API_KEY or ensure pi-bw-get works.")
        print("  RALPH:SKIP — inference endpoint unreachable")
        sys.exit(1)

    print(f"\n  Ollama endpoint: reachable")
    print(f"  Available models: {', '.join(available_models)}")

    models_to_test = []
    if DEFAULT_MODEL in available_models:
        models_to_test.append(DEFAULT_MODEL)
        print(f"  Primary model: {DEFAULT_MODEL} ✅")
    if FALLBACK_MODEL in available_models:
        models_to_test.append(FALLBACK_MODEL)
        print(f"  Fallback model: {FALLBACK_MODEL} ✅")

    if not models_to_test:
        print(f"\n  ERROR: Neither {DEFAULT_MODEL} nor {FALLBACK_MODEL} available.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. LOAD DATA
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 2: DATA LOADING")
    print("=" * 78)

    analyses = load_framing_analyses()
    cluster_signals = load_cluster_signals()

    hostile = [a for a in analyses if a['is_hostile']]
    clean = [a for a in analyses if not a['is_hostile']]
    print(f"\n  LLM-analyzed framings: {len(analyses)} total")
    print(f"    Hostile: {len(hostile)}")
    print(f"    Clean:   {len(clean)}")

    # Show labeled cases
    print(f"\n  {'ID':>4s}  {'CID':>6s}  {'Label':>6s}  {'Conf':>4s}  {'Event'}")
    print("  " + "-" * 72)
    for a in analyses:
        label = "HOST" if a['is_hostile'] else "CLEAN"
        ef = (a['event_fact'] or '')[:55]
        print(f"  {a['framing_id']:4d}  {a['cluster_id']:>6s}  {label:>6s}  "
              f"{a['confidence']:.1f}   {ef}")

    # ------------------------------------------------------------------
    # 3. PREPARE SIGNAL SUMMARIES
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 3: SIGNAL SUMMARIES PER CLUSTER")
    print("=" * 78)

    summaries = {}
    for a in analyses:
        cid = a['cluster_id']
        sigs = cluster_signals.get(cid, [])
        summary, n_state, n_trusted = prepare_signal_summary(sigs)
        summaries[cid] = {
            'text': summary,
            'n_state': n_state,
            'n_trusted': n_trusted,
            'n_total': len(sigs),
        }
        print(f"\n  Cluster {cid} ({'HOSTILE' if a['is_hostile'] else 'CLEAN'}):")
        print(f"    Signals: {len(sigs)} total, {n_state} state, {n_trusted} trusted")

    # ------------------------------------------------------------------
    # 4. RUN BOTH PROMPTS PER MODEL
    # ------------------------------------------------------------------

    all_results = {}

    for model in models_to_test:
        print("\n" + "=" * 78)
        print(f"SECTION 4: RUNNING PROMPTS WITH {model}")
        print("=" * 78)

        # Warm up model
        print(f"\n  Warming up {model}...")
        warmup = anthropic_generate("Say 'ready' in one word.", model=model, timeout=60)
        if warmup is None:
            print(f"  WARNING: Model {model} failed warmup, skipping.")
            continue
        print(f"  Model ready.")

        results_current = []
        results_ibi = []

        for i, a in enumerate(analyses):
            cid = a['cluster_id']
            label = "HOSTILE" if a['is_hostile'] else "CLEAN"
            sig_summary = summaries[cid]['text']

            print(f"\n  [{i+1}/{len(analyses)}] Cluster {cid} (ground truth: {label})")

            # --- CURRENT PROMPT ---
            prompt_current = CURRENT_PROMPT.format(signal_summary=sig_summary)
            print(f"    Running CURRENT prompt...", end='', flush=True)
            t0 = time.time()
            resp_current = anthropic_generate(prompt_current, model=model, timeout=180)
            dt = time.time() - t0
            parsed_current = parse_verdict(resp_current)
            print(f" {parsed_current['verdict'] or 'PARSE_FAIL'} "
                  f"(conf={parsed_current['confidence']:.2f}, {dt:.1f}s)")
            results_current.append({
                'cluster_id': cid,
                'ground_truth': label,
                'verdict': parsed_current['verdict'],
                'confidence': parsed_current['confidence'],
                'reasoning': parsed_current['reasoning'][:200],
                'time_s': dt,
            })

            # --- IBI PROMPT ---
            prompt_ibi = IBI_PROMPT.format(signal_summary=sig_summary)
            print(f"    Running IBI prompt...", end='', flush=True)
            t0 = time.time()
            resp_ibi = anthropic_generate(prompt_ibi, model=model, timeout=180)
            dt = time.time() - t0
            parsed_ibi = parse_verdict(resp_ibi)
            print(f" {parsed_ibi['verdict'] or 'PARSE_FAIL'} "
                  f"(conf={parsed_ibi['confidence']:.2f}, {dt:.1f}s)")
            results_ibi.append({
                'cluster_id': cid,
                'ground_truth': label,
                'verdict': parsed_ibi['verdict'],
                'confidence': parsed_ibi['confidence'],
                'reasoning': parsed_ibi['reasoning'][:200],
                'time_s': dt,
            })

            # Brief pause between requests to avoid overloading
            time.sleep(1)

        all_results[model] = {
            'current': results_current,
            'ibi': results_ibi,
        }

    # ------------------------------------------------------------------
    # 5. ANALYSIS PER MODEL
    # ------------------------------------------------------------------

    for model, model_results in all_results.items():
        print("\n" + "=" * 78)
        print(f"SECTION 5: RESULTS FOR {model}")
        print("=" * 78)

        results_current = model_results['current']
        results_ibi = model_results['ibi']

        # Build ground truth and prediction arrays
        y_true = []
        y_current = []
        y_ibi = []
        valid_indices = []

        for i, a in enumerate(analyses):
            gt = 1 if a['is_hostile'] else 0
            cur_v = results_current[i]['verdict']
            ibi_v = results_ibi[i]['verdict']

            y_true.append(gt)
            y_current.append(1 if cur_v == 'HOSTILE' else 0 if cur_v == 'CLEAN' else -1)
            y_ibi.append(1 if ibi_v == 'HOSTILE' else 0 if ibi_v == 'CLEAN' else -1)

            if cur_v is not None and ibi_v is not None:
                valid_indices.append(i)

        y_true = np.array(y_true)
        y_current = np.array(y_current)
        y_ibi = np.array(y_ibi)

        n_valid = len(valid_indices)
        n_current_fail = np.sum(y_current == -1)
        n_ibi_fail = np.sum(y_ibi == -1)

        print(f"\n  Parse results:")
        print(f"    CURRENT prompt: {n_valid - int(n_current_fail)} valid, "
              f"{int(n_current_fail)} parse failures")
        print(f"    IBI prompt:     {n_valid - int(n_ibi_fail)} valid, "
              f"{int(n_ibi_fail)} parse failures")

        # -- Detailed per-case comparison table --
        print(f"\n  {'CID':>6s}  {'Truth':>6s}  {'CURRENT':>8s}  {'IBI':>8s}  "
              f"{'Agree':>5s}  {'CurOK':>5s}  {'IBI_OK':>5s}  Event")
        print("  " + "-" * 78)

        agree_count = 0
        cur_correct = 0
        ibi_correct = 0
        flipped = []

        for i, a in enumerate(analyses):
            gt_str = "HOST" if a['is_hostile'] else "CLEAN"
            cur_str = results_current[i]['verdict'] or "FAIL"
            ibi_str = results_ibi[i]['verdict'] or "FAIL"

            agree = "✅" if cur_str == ibi_str else "❌"
            if cur_str == ibi_str:
                agree_count += 1

            cur_ok = "✅" if cur_str == ("HOSTILE" if a['is_hostile'] else "CLEAN") else "❌"
            ibi_ok = "✅" if ibi_str == ("HOSTILE" if a['is_hostile'] else "CLEAN") else "❌"

            if cur_str == ("HOSTILE" if a['is_hostile'] else "CLEAN"):
                cur_correct += 1
            if ibi_str == ("HOSTILE" if a['is_hostile'] else "CLEAN"):
                ibi_correct += 1

            if cur_str != ibi_str:
                flipped.append({
                    'cluster_id': a['cluster_id'],
                    'ground_truth': gt_str,
                    'current': cur_str,
                    'ibi': ibi_str,
                    'event': (a['event_fact'] or '')[:50],
                    'cur_reasoning': results_current[i]['reasoning'][:150],
                    'ibi_reasoning': results_ibi[i]['reasoning'][:150],
                })

            ef = (a['event_fact'] or '')[:40]
            print(f"  {a['cluster_id']:>6s}  {gt_str:>6s}  {cur_str:>8s}  {ibi_str:>8s}  "
                  f"{agree:>5s}  {cur_ok:>5s}  {ibi_ok:>5s}  {ef}")

        # -- Metrics --
        print(f"\n  SUMMARY:")
        print(f"    Agreement rate: {agree_count}/{len(analyses)} "
              f"({agree_count/len(analyses)*100:.0f}%)")
        print(f"    CURRENT correct: {cur_correct}/{len(analyses)} "
              f"({cur_correct/len(analyses)*100:.0f}%)")
        print(f"    IBI correct:     {ibi_correct}/{len(analyses)} "
              f"({ibi_correct/len(analyses)*100:.0f}%)")

        # Compute metrics for valid predictions only
        valid_mask = (y_current >= 0) & (y_ibi >= 0)
        if np.sum(valid_mask) > 0:
            yt = y_true[valid_mask]
            yc = y_current[valid_mask]
            yi = y_ibi[valid_mask]

            m_cur = compute_metrics(yt, yc)
            m_ibi = compute_metrics(yt, yi)

            print(f"\n  {'Metric':<15s}  {'CURRENT':>10s}  {'IBI':>10s}  {'Delta':>10s}")
            print("  " + "-" * 50)
            for metric in ['precision', 'recall', 'f1', 'accuracy']:
                delta = m_ibi[metric] - m_cur[metric]
                sign = '+' if delta >= 0 else ''
                print(f"  {metric:<15s}  {m_cur[metric]:10.3f}  {m_ibi[metric]:10.3f}  "
                      f"{sign}{delta:9.3f}")
            print(f"\n  CURRENT confusion: TP={m_cur['tp']} FP={m_cur['fp']} "
                  f"FN={m_cur['fn']} TN={m_cur['tn']}")
            print(f"  IBI confusion:     TP={m_ibi['tp']} FP={m_ibi['fp']} "
                  f"FN={m_ibi['fn']} TN={m_ibi['tn']}")

            # -- Agreement matrix --
            print(f"\n  AGREEMENT MATRIX (CURRENT vs IBI):")
            print(f"  {'':>15s}  {'IBI=HOSTILE':>12s}  {'IBI=CLEAN':>12s}")
            a_hh = np.sum((yc == 1) & (yi == 1))
            a_hc = np.sum((yc == 1) & (yi == 0))
            a_ch = np.sum((yc == 0) & (yi == 1))
            a_cc = np.sum((yc == 0) & (yi == 0))
            print(f"  {'CUR=HOSTILE':>15s}  {a_hh:>12d}  {a_hc:>12d}")
            print(f"  {'CUR=CLEAN':>15s}  {a_ch:>12d}  {a_cc:>12d}")

            # Cohen's kappa
            n_total = np.sum(valid_mask)
            po = (a_hh + a_cc) / n_total
            pe = ((a_hh + a_hc) * (a_hh + a_ch) +
                  (a_ch + a_cc) * (a_hc + a_cc)) / (n_total ** 2)
            kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
            print(f"\n  Cohen's κ (inter-prompt agreement): {kappa:.3f}")
            if kappa > 0.8:
                print("    Interpretation: Almost perfect agreement")
            elif kappa > 0.6:
                print("    Interpretation: Substantial agreement")
            elif kappa > 0.4:
                print("    Interpretation: Moderate agreement")
            else:
                print("    Interpretation: Fair or poor agreement")

        # -- Flipped labels --
        if flipped:
            print(f"\n  FLIPPED LABELS ({len(flipped)} cases):")
            print("  " + "-" * 72)
            for fl in flipped:
                cur_correct = fl['current'] == fl['ground_truth']
                ibi_correct = fl['ibi'] == fl['ground_truth']
                if ibi_correct and not cur_correct:
                    flip_type = "IBI CORRECTS"
                elif cur_correct and not ibi_correct:
                    flip_type = "IBI BREAKS"
                else:
                    flip_type = "BOTH WRONG" if not cur_correct else "BOTH RIGHT"

                print(f"\n    Cluster {fl['cluster_id']} — {flip_type}")
                print(f"      Ground truth: {fl['ground_truth']}")
                print(f"      CURRENT:      {fl['current']}")
                print(f"      IBI:          {fl['ibi']}")
                print(f"      Event: {fl['event']}")
                print(f"      CUR reasoning: {fl['cur_reasoning'][:120]}")
                print(f"      IBI reasoning: {fl['ibi_reasoning'][:120]}")
        else:
            print(f"\n  No flipped labels — prompts agree on all cases.")

        # -- Confidence comparison --
        print(f"\n  CONFIDENCE COMPARISON:")
        cur_confs = [r['confidence'] for r in results_current]
        ibi_confs = [r['confidence'] for r in results_ibi]
        print(f"    CURRENT mean conf: {np.mean(cur_confs):.3f} "
              f"(std={np.std(cur_confs):.3f})")
        print(f"    IBI mean conf:     {np.mean(ibi_confs):.3f} "
              f"(std={np.std(ibi_confs):.3f})")

        # Hostile vs clean confidence split
        h_cur_conf = [r['confidence'] for r, a in zip(results_current, analyses)
                      if a['is_hostile']]
        c_cur_conf = [r['confidence'] for r, a in zip(results_current, analyses)
                      if not a['is_hostile']]
        h_ibi_conf = [r['confidence'] for r, a in zip(results_ibi, analyses)
                      if a['is_hostile']]
        c_ibi_conf = [r['confidence'] for r, a in zip(results_ibi, analyses)
                      if not a['is_hostile']]

        if h_cur_conf and c_cur_conf:
            print(f"\n    CURRENT hostile conf: {np.mean(h_cur_conf):.3f}, "
                  f"clean conf: {np.mean(c_cur_conf):.3f}")
        if h_ibi_conf and c_ibi_conf:
            print(f"    IBI hostile conf:     {np.mean(h_ibi_conf):.3f}, "
                  f"clean conf: {np.mean(c_ibi_conf):.3f}")

        # -- Timing --
        cur_times = [r['time_s'] for r in results_current]
        ibi_times = [r['time_s'] for r in results_ibi]
        print(f"\n  TIMING:")
        print(f"    CURRENT mean: {np.mean(cur_times):.1f}s "
              f"(total: {np.sum(cur_times):.0f}s)")
        print(f"    IBI mean:     {np.mean(ibi_times):.1f}s "
              f"(total: {np.sum(ibi_times):.0f}s)")

    # ------------------------------------------------------------------
    # 6. CROSS-MODEL COMPARISON (if 2 models tested)
    # ------------------------------------------------------------------
    if len(all_results) >= 2:
        print("\n" + "=" * 78)
        print("SECTION 6: CROSS-MODEL COMPARISON")
        print("=" * 78)

        model_names = list(all_results.keys())
        m1, m2 = model_names[0], model_names[1]

        print(f"\n  Comparing {m1} vs {m2}:")

        for prompt_type in ['current', 'ibi']:
            r1 = all_results[m1][prompt_type]
            r2 = all_results[m2][prompt_type]

            agree = sum(1 for a, b in zip(r1, r2)
                        if a['verdict'] == b['verdict'])
            print(f"\n    {prompt_type.upper()} prompt agreement: "
                  f"{agree}/{len(r1)} ({agree/len(r1)*100:.0f}%)")

            # Which model is more accurate?
            m1_correct = sum(1 for r, a in zip(r1, analyses)
                            if r['verdict'] == ('HOSTILE' if a['is_hostile'] else 'CLEAN'))
            m2_correct = sum(1 for r, a in zip(r2, analyses)
                            if r['verdict'] == ('HOSTILE' if a['is_hostile'] else 'CLEAN'))
            print(f"    {m1} correct: {m1_correct}/{len(analyses)}")
            print(f"    {m2} correct: {m2_correct}/{len(analyses)}")

    # ------------------------------------------------------------------
    # 7. STABILITY TEST — RUN IBI 3x ON HARDEST CASES
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SECTION 7: STABILITY TEST — IBI PROMPT CONSISTENCY")
    print("=" * 78)

    # Pick the primary model for stability testing
    test_model = models_to_test[0]
    print(f"\n  Model: {test_model}")
    print("  Running IBI prompt 3x on 5 borderline cases to test consistency.")

    # Select cases: all hostile + first 2 clean that the LLM might struggle with
    # (those with higher state_ratio)
    stability_cases = []
    for a in analyses:
        if a['is_hostile']:
            stability_cases.append(a)
    # Add clean cases that have state coverage
    for a in analyses:
        if not a['is_hostile'] and len(stability_cases) < 8:
            cid = a['cluster_id']
            s = summaries.get(cid, {})
            if s.get('n_state', 0) >= 1:
                stability_cases.append(a)

    stability_cases = stability_cases[:8]  # Cap at 8 for time

    print(f"  Testing {len(stability_cases)} cases x 3 runs = "
          f"{len(stability_cases)*3} inferences")

    stability_results = {}
    for a in stability_cases:
        cid = a['cluster_id']
        gt = "HOSTILE" if a['is_hostile'] else "CLEAN"
        sig_summary = summaries[cid]['text']
        prompt = IBI_PROMPT.format(signal_summary=sig_summary)

        verdicts = []
        for run in range(3):
            # Use slightly different temperature to test robustness
            temp = 0.1 + run * 0.15  # 0.1, 0.25, 0.4
            resp = anthropic_generate(prompt, model=test_model,
                                   temperature=temp, timeout=180)
            parsed = parse_verdict(resp)
            verdicts.append(parsed['verdict'])
            time.sleep(0.5)

        consistent = len(set(v for v in verdicts if v)) <= 1
        stability_results[cid] = {
            'ground_truth': gt,
            'verdicts': verdicts,
            'consistent': consistent,
        }

        v_str = ', '.join(v or 'FAIL' for v in verdicts)
        status = "✅ STABLE" if consistent else "⚠️ UNSTABLE"
        print(f"    Cluster {cid} ({gt}): [{v_str}] {status}")

    n_stable = sum(1 for v in stability_results.values() if v['consistent'])
    n_tested = len(stability_results)
    print(f"\n  Stability: {n_stable}/{n_tested} cases consistent across 3 runs "
          f"({n_stable/n_tested*100:.0f}%)")

    # ------------------------------------------------------------------
    # 8. FINDINGS SUMMARY
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("FINDINGS SUMMARY")
    print("=" * 78)

    # Compute best model/prompt results
    best_f1_current = 0
    best_f1_ibi = 0
    best_model = None

    for model, model_results in all_results.items():
        valid_mask = np.ones(len(analyses), dtype=bool)
        yt = np.array([1 if a['is_hostile'] else 0 for a in analyses])

        yc = np.array([1 if r['verdict'] == 'HOSTILE' else 0
                        for r in model_results['current']])
        yi = np.array([1 if r['verdict'] == 'HOSTILE' else 0
                        for r in model_results['ibi']])

        m_c = compute_metrics(yt, yc)
        m_i = compute_metrics(yt, yi)

        if m_c['f1'] >= best_f1_current:
            best_f1_current = m_c['f1']
            best_f1_ibi = m_i['f1']
            best_model = model
            best_m_c = m_c
            best_m_i = m_i

    ibi_improves = best_f1_ibi > best_f1_current
    ibi_delta = best_f1_ibi - best_f1_current

    print(f"""
1. EXPERIMENT SETUP
   - Dataset: {len(analyses)} LLM-analyzed framings ({sum(1 for a in analyses if a['is_hostile'])} hostile, {sum(1 for a in analyses if not a['is_hostile'])} clean)
   - Models tested: {', '.join(all_results.keys())}
   - Two prompts: CURRENT (factual comparison) vs IBI (intent-based framing)
   - Ground truth: production labels from human-validated framing analysis

2. PROMPT COMPARISON (best model: {best_model or 'N/A'})
   CURRENT prompt: F1={best_f1_current:.3f} (P={best_m_c['precision']:.3f}, R={best_m_c['recall']:.3f})
   IBI prompt:     F1={best_f1_ibi:.3f} (P={best_m_i['precision']:.3f}, R={best_m_i['recall']:.3f})
   Delta:          {'+'if ibi_delta>=0 else ''}{ibi_delta:.3f}
   
   IBI {"IMPROVES" if ibi_improves else "DOES NOT IMPROVE"} over CURRENT prompt.

3. KEY OBSERVATIONS
   - arXiv:2603.14525v1 claims 9-20% F1 boost from IBI framing
   - On our Baltic/NATO disinformation task with local 14B models:
     F1 delta = {'+' if ibi_delta >= 0 else ''}{ibi_delta*100:.1f}%
   - Note: our task is framing COMPARISON (state vs trusted), not
     single-document classification. IBI may work differently here.

4. STABILITY
   - {n_stable}/{n_tested} cases consistent across 3 runs ({n_stable/n_tested*100:.0f}%)
   - Local 14B models produce {"stable" if n_stable/n_tested > 0.7 else "unstable"} verdicts

5. LIMITATIONS
   - Local 14B models are much weaker than production Gemini
   - Cross-lingual signal titles (RU/EN/ET) may confuse small models
   - N=18 is too small for statistical significance
   - IBI prompt tested on same data that defined the task — no held-out set

6. RECOMMENDATION""")

    if ibi_improves and ibi_delta >= 0.05:
        print(f"""   ✅ IBI prompt shows meaningful improvement (+{ibi_delta*100:.1f}% F1).
   Consider A/B testing in production with Gemini for larger-scale validation.
   The IBI prompt forces the LLM to reason about adversarial intent,
   which may catch subtle manipulation that factual comparison misses.
   
   RECOMMENDED IBI PROMPT (for production testing):
   ---
   {IBI_PROMPT[:500]}...
   ---""")
    elif ibi_improves:
        print(f"""   ⚠️ IBI shows marginal improvement (+{ibi_delta*100:.1f}% F1) — not conclusive.
   The improvement is within noise for N=18. Need larger labeled dataset
   to determine if IBI reliably improves framing detection.
   Worth testing in production A/B but don't expect large gains.""")
    else:
        print(f"""   ❌ IBI does not improve on the CURRENT prompt ({ibi_delta*100:+.1f}% F1).
   Possible explanations:
   a) Our task (cross-source framing comparison) is already well-suited
      to the CURRENT factual prompt — IBI doesn't add signal
   b) 14B local models may lack capacity to benefit from IBI framing
   c) The 9-20% boost from arXiv:2603.14525v1 may not transfer to
      multi-source comparison tasks (vs single-document classification)
   
   The CURRENT prompt should remain in production. IBI could still be
   tested with Gemini-class models for a fair comparison.""")

    print(f"\n{'='*78}")
    print("DONE")
    print(f"{'='*78}")


if __name__ == '__main__':
    main()
