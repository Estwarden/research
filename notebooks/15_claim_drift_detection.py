# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 15. Claim Drift Detection — Measuring Fabrication per Hop
#
# **Paper:** "Simulating Misinformation Propagation in Social Networks using LLMs"
# — Maurya et al. (arXiv, Nov 2025)
#
# **URL:** https://arxiv.org/abs/2511.10384
#
# ## Key Idea
# Track how claims MUTATE as they propagate. Compare each signal's claims against
# the original source. Quantify factual drift with a Misinformation Index.
#
# ## Application to EstWarden
# The Bild map case: Bild said "cannot rule out" → channels said "1-2 months, laws passed."
# We need to detect this mutation automatically.
#
# ## Method
# 1. For each event cluster, identify the ROOT signal (earliest, highest-credibility source)
# 2. Extract specific claims from root (dates, numbers, legal refs, named entities)
# 3. Extract claims from each subsequent signal
# 4. Compare: what claims appear in later signals but NOT in the root?
# 5. Score: Misinformation Index = (fabricated claims) / (total claims)

# %% [markdown]
# ## Setup

# %%
import os
import re
import json
import numpy as np
import pandas as pd
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# %% [markdown]
# ## 1. Claim Extraction (Heuristic — No LLM Required)
#
# Extract specific, verifiable claims from text:
# - Time references ("1-2 months", "by summer", "60 days")
# - Numbers and statistics
# - Legal/institutional references ("law passed", "закон принят")
# - Certainty markers ("will attack", "final stage", "beschlossene Sache")
# - Named entities (people, organizations, places)

# %%
# Claim extraction patterns (multilingual: EN, UK, RU, DE)
CLAIM_PATTERNS = {
    'time_reference': [
        r'\d+[-–]\d+\s*(month|months|місяц|месяц|Monate)',
        r'within\s+\d+\s*(days|weeks|months)',
        r'протягом\s+\d+',
        r'через\s+\d+',
        r'by\s+(summer|winter|spring|fall|autumn|january|february|march|april|may|june|july|august|september|october|november|december)',
        r'до\s+(літа|зими|весни|осені)',
        r'final\s+stage',
        r'фінальн\w+\s+стад',
        r'последн\w+\s+стад',
        r'Endphase',
    ],
    'legal_claim': [
        r'law[s]?\s+(passed|enacted|approved)',
        r'закон\w*\s+(прийнят|приня|ухвален)',
        r'Gesetz\w*\s+(verabschiedet|beschlossen)',
        r'legislation',
        r'законодав',
    ],
    'certainty_marker': [
        r'will\s+attack',
        r'is\s+preparing\s+to\s+attack',
        r'нападе\s+на',
        r'готується\s+до\s+нападу',
        r'beschlossene\s+Sache',
        r'вже\s+вирішено',
        r'решение\s+принято',
        r'imminent',
        r'неминуч',
    ],
    'question_marker': [
        r'\?',
        r'whether',
        r'could\s+be',
        r'cannot\s+rule\s+out',
        r'nicht\s+ausschließen',
        r'можливо',
        r'не\s+можна\s+виключити',
    ],
    'numeric_claim': [
        r'\d+[,.]?\d*\s*(thousand|million|billion|тисяч|мільйон)',
        r'\d+%',
        r'\d+\s*(troops|soldiers|tanks|aircraft|солдат|танк)',
    ],
}


def extract_claims(text):
    """Extract verifiable claims from text using regex patterns."""
    if not isinstance(text, str):
        return {}
    
    claims = {}
    for claim_type, patterns in CLAIM_PATTERNS.items():
        matches = []
        for pattern in patterns:
            found = re.findall(pattern, text, re.IGNORECASE)
            if found:
                matches.extend(found if isinstance(found[0], str) else [str(f) for f in found])
        if matches:
            claims[claim_type] = matches
    
    return claims


# Test
test_bild = "We cannot rule out that this is preparing a Russian invasion following the 2014 model."
test_smolii = "FINAL STAGE — 1-2 MONTHS. Putin will attack Estonia. Laws have been passed for invasion."

print("=== Bild (source) ===")
print(extract_claims(test_bild))
print("\n=== Smolii (amplifier) ===")
print(extract_claims(test_smolii))

# %% [markdown]
# ## 2. Claim Drift Computation
#
# Compare claims between root signal and each subsequent signal.
# Claims that appear in later signals but NOT in root = fabricated.

# %%
def compute_claim_drift(root_claims, signal_claims):
    """
    Compute claim drift between root signal and an amplifying signal.
    
    Returns:
        drift_score: float 0-1 (0 = faithful reproduction, 1 = complete fabrication)
        fabricated: dict of claim types that were added
        removed: dict of claim types that were dropped (e.g., question marks)
    """
    fabricated = {}
    removed = {}
    
    all_types = set(list(root_claims.keys()) + list(signal_claims.keys()))
    
    for claim_type in all_types:
        root_has = claim_type in root_claims
        signal_has = claim_type in signal_claims
        
        if signal_has and not root_has:
            fabricated[claim_type] = signal_claims[claim_type]
        elif root_has and not signal_has:
            removed[claim_type] = root_claims[claim_type]
    
    # Special case: question markers removed = certainty manufactured
    if 'question_marker' in removed and 'certainty_marker' in fabricated:
        fabricated['certainty_manufactured'] = True
    
    # Drift score
    total_claim_types = len(all_types) if all_types else 1
    n_fabricated = len(fabricated)
    drift_score = n_fabricated / total_claim_types
    
    return drift_score, fabricated, removed


# Test with Bild map case
root = extract_claims(test_bild)
amplified = extract_claims(test_smolii)

drift, fab, rem = compute_claim_drift(root, amplified)
print(f"Drift score: {drift:.2f}")
print(f"Fabricated: {fab}")
print(f"Removed: {rem}")

# %% [markdown]
# ## 3. Misinformation Index per Cluster
#
# For each event cluster:
# 1. Find root signal (earliest by published_at, or highest-credibility category)
# 2. Compare all other signals against root
# 3. Compute aggregate Misinformation Index

# %%
def analyze_cluster_drift(signals_df, text_col='title', time_col='published_at', category_col=None):
    """
    Analyze claim drift within a cluster of signals.
    
    Args:
        signals_df: DataFrame with signal texts and metadata
        text_col: column containing signal text
        time_col: column for sorting by time
        category_col: optional column for source credibility
    
    Returns:
        dict with cluster-level metrics
    """
    if len(signals_df) < 2:
        return None
    
    # Sort by time
    sorted_df = signals_df.sort_values(time_col)
    
    # Root = earliest signal
    root_text = sorted_df.iloc[0][text_col]
    root_claims = extract_claims(root_text)
    
    # Analyze each subsequent signal
    drift_scores = []
    all_fabricated = defaultdict(int)
    all_removed = defaultdict(int)
    
    for _, row in sorted_df.iloc[1:].iterrows():
        signal_claims = extract_claims(row[text_col])
        drift, fab, rem = compute_claim_drift(root_claims, signal_claims)
        drift_scores.append(drift)
        
        for claim_type in fab:
            all_fabricated[claim_type] += 1
        for claim_type in rem:
            all_removed[claim_type] += 1
    
    if not drift_scores:
        return None
    
    return {
        'n_signals': len(signals_df),
        'root_text': root_text[:100],
        'root_claims': root_claims,
        'misinformation_index': np.mean(drift_scores),
        'max_drift': max(drift_scores),
        'n_fabricating_signals': sum(1 for d in drift_scores if d > 0),
        'fabricated_claim_types': dict(all_fabricated),
        'removed_claim_types': dict(all_removed),
    }


# Test with synthetic Bild map data
bild_signals = pd.DataFrame({
    'title': [
        "Bereitet Putin einen Angriff auf Estland vor?",  # Bild (root)
        "Putin готується до нападу на Естонію",  # insiderUKR
        "ФІНАЛЬНА СТАДІЯ — 1-2 МІСЯЦІ. Путін нападе на Естонію",  # smolii
        "Закони прийняті для вторгнення в Балтію",  # 5 kanal
        "Russia may target Estonia — Bild report",  # accurate reproduction
    ],
    'published_at': pd.date_range('2026-03-16 08:00', periods=5, freq='2h'),
})

result = analyze_cluster_drift(bild_signals)
if result:
    print(f"\n=== Bild Map Cluster Analysis ===")
    print(f"Misinformation Index: {result['misinformation_index']:.2f}")
    print(f"Max drift: {result['max_drift']:.2f}")
    print(f"Fabricating signals: {result['n_fabricating_signals']}/{result['n_signals']-1}")
    print(f"Fabricated types: {result['fabricated_claim_types']}")
    print(f"Removed types: {result['removed_claim_types']}")

# %% [markdown]
# ## 4. Apply to Real Data

# %%
signals_path = os.path.join(DATA_DIR, 'signals_14d.csv')
if os.path.exists(signals_path):
    df = pd.read_csv(signals_path)
    
    # Find cluster column
    cluster_col = None
    for col in ['cluster_id', 'event_cluster_id']:
        if col in df.columns:
            cluster_col = col
            break
    
    text_col = 'title' if 'title' in df.columns else 'content'
    time_col = 'published_at' if 'published_at' in df.columns else 'created_at'
    
    if cluster_col:
        results = []
        for cid, group in df.groupby(cluster_col):
            if len(group) >= 3:
                r = analyze_cluster_drift(group, text_col=text_col, time_col=time_col)
                if r and r['misinformation_index'] > 0:
                    r['cluster_id'] = cid
                    results.append(r)
        
        if results:
            rdf = pd.DataFrame(results).sort_values('misinformation_index', ascending=False)
            print(f"\n=== Top 10 Clusters by Misinformation Index ===")
            print(rdf[['cluster_id', 'n_signals', 'misinformation_index', 'max_drift', 'n_fabricating_signals']].head(10).to_string())
        else:
            print("No clusters with detectable drift")
    else:
        print("No cluster column found")
else:
    print("No data file — see data/README.md for export instructions")

# %% [markdown]
# ## 5. Interpretation & Next Steps
#
# - **MI > 0.5**: High fabrication — multiple claim types added beyond source
# - **MI 0.2-0.5**: Moderate distortion — some claims added or nuance removed
# - **MI < 0.2**: Mostly faithful — minor variations
# - **Question markers removed + certainty added**: Classic distortion pattern
#
# ### Integration with Pipeline
# 1. Run after event clustering (process/cluster)
# 2. Compare root signal claims vs all signals in cluster
# 3. Alert when MI > 0.3 AND cluster has > 500K cumulative views
# 4. Auto-create campaign when MI > 0.5
#
# ### Limitations
# - Regex-based claim extraction misses subtle fabrication
# - Future: use LLM for claim extraction (more accurate but slower)
# - Cross-lingual: patterns need expansion for more languages
