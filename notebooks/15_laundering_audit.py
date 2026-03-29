#!/usr/bin/env python3
"""
15. Laundering Detector False Positive Audit
==============================================

Building on:
  - Notebook 07: Found laundering counts NHL scores, Soyuz launches, and
    'teacher beats student with dildo' as hostile. Noise rate ~72%.
  - Notebook 14: Laundering is the SECOND biggest FIMI sub-component driver,
    avg contribution ~2.46/5.45 CTI points in the active period.
  - Notebook 06/08: FIMI alone exceeds YELLOW (15.2), making GREEN impossible.

This notebook:
  1. Loads ALL narrative_origins with is_state_origin=true AND category_count>=2
  2. Classifies each as RELEVANT (Baltic/security) or NOISE using expanded keywords
  3. Sub-classifies NOISE: domestic_russia, ukraine_frontline, global_politics,
     sports_culture, middle_east_iran, other
  4. Computes laundering score with relevance filter vs without
  5. Tests category_count thresholds 2/3/4/5 — optimal cutoff
  6. Exports laundering_classified.csv for manual review

Uses ONLY standard library + numpy.
"""
import csv
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT, exist_ok=True)

# ================================================================
# CTI CONSTANTS (from production / methodology)
# ================================================================
from cti_constants import LAUNDERING_WEIGHT, TOTAL_WEIGHT, YELLOW_THRESHOLD

print("=" * 72)
print("15. LAUNDERING DETECTOR FALSE POSITIVE AUDIT")
print("=" * 72)


# ================================================================
# 1. LOAD DATA
# ================================================================
print("\n" + "=" * 72)
print("1. LOADING DATA")
print("=" * 72)

origins = []
with open(f"{DATA}/narrative_origins.csv") as f:
    for row in csv.DictReader(f):
        origins.append(row)

state_origins = [o for o in origins if o['is_state_origin'] == 't']
laundering = [o for o in state_origins if int(o['category_count']) >= 2]

print(f"Total narrative origins: {len(origins)}")
print(f"State-origin (is_state_origin=t): {len(state_origins)}")
print(f"Laundering candidates (state + cat>=2): {len(laundering)}")

# Category count distribution
cc_dist = Counter(int(o['category_count']) for o in laundering)
print(f"\nCategory count distribution in laundering:")
for cc in sorted(cc_dist.keys()):
    pct = cc_dist[cc] / len(laundering) * 100
    bar = "█" * (cc_dist[cc] // 2)
    print(f"  cat_count={cc}: {cc_dist[cc]:>4d} ({pct:5.1f}%) {bar}")


# ================================================================
# 2. EXPANDED KEYWORD LISTS
# ================================================================
# Baltic region countries, cities, and key terms — comprehensive coverage
# of the monitored regions. These are lowercase match patterns.

# NOTE ON KEYWORD MATCHING:
# Short keywords like 'нато', 'литв', 'балт' cause false positives via
# substring matching (e.g. 'чемпио-НАТО-в', 'мо-ЛИТВ-у', FC Балтика).
# We use regex word boundaries (\b) for ambiguous patterns, and add
# exclusion patterns for known false positive contexts (sports, space).

# Patterns prefixed with '^' are plain substring matches.
# Patterns containing \b or .* are treated as regex.

BALTIC_KEYWORDS = [
    # Estonia
    'эстон', 'eesti', 'tallinn', 'таллин', 'таллинн', 'тарту', 'tartu',
    'нарв', 'narva', 'пярну', 'pärnu', 'parnu', 'вильянди', 'viljandi',
    'ида-вирумаа', 'ida-viru', 'сааремаа', 'saaremaa', 'хийумаа', 'hiiumaa',
    'кохтла-ярве', 'kohtla-järve', 'силламяэ', 'sillamäe',
    # Latvia
    'латви', 'latvij', '\\bрига\\b', '\\briga\\b', 'даугавпилс', 'daugavpils',
    'лиепая', 'liepāja', 'liepaja', 'вентспилс', 'ventspils',
    'елгава', 'jelgava', 'юрмала', 'jūrmala', 'jurmala', 'резекне', 'rēzekne',
    # Lithuania — use word boundary to avoid matching 'молитву'
    '\\bлитв', '\\blietuv', 'вильнюс', 'vilnius', 'каунас', 'kaunas',
    'клайпед', 'klaipėd', 'klaipeda', 'шяуляй', 'šiauliai', 'siauliai',
    'паневежис', 'panevėžys', 'panevezys',
    # Generic Baltic — word boundary to avoid FC Baltika in sports context
    # (handled by sports exclusion below)
    'балтийск', 'балтии', 'балтию', 'прибалт', 'pribalt',
    'baltic', '\\bбалтик',
    # Finland (monitored region)
    'финлянд', 'финск', 'суоми', 'finland', 'finnish', 'suomi',
    'хельсинк', 'helsinki', 'тампере', 'tampere', 'турку', 'turku',
    'оулу', 'oulu', 'лапланд', 'lapland', 'карелия', 'karelia',
    'аландск', 'åland',
    # Poland (monitored region)
    'польш', 'polska', 'poland', 'polish', 'варшав', 'warsaw', 'warszawa',
    'краков', 'kraków', 'krakow', 'гданьск', 'gdańsk', 'gdansk',
    'вроцлав', 'wrocław', 'wroclaw', 'познань', 'poznań', 'poznan',
    'лодзь', 'łódź', 'lodz', 'щецин', 'szczecin', 'жешув', 'rzeszów',
    'люблин', 'lublin', 'катовице', 'katowice',
    # Key military/geographic areas near Baltics
    'калинингр', 'kaliningrad', 'кёнигсберг', 'königsberg',
    'псков', 'pskov', 'печор', 'pechory', 'ленинград', 'leningrad',
    'ленобласт', 'готланд', 'gotland', 'борнхольм', 'bornholm',
    'сувалк', 'suwałki', 'suwalki',  # Suwalki gap
    'кронштадт', 'kronstadt',
    # Belarus border (monitored)
    'беларус', 'белорус', 'belarus', '\\bминск', '\\bminsk', 'гродн', 'grodno',
    '\\bбрест\\b',
]

SECURITY_KEYWORDS = [
    # Military — use word boundaries for ambiguous short patterns
    'войн', 'война', 'военн', 'армия', 'армии', 'missile',
    '\\bдрон', 'бпла', 'uav', 'drone', '\\bудар', 'strike', '\\bатак', 'attack',
    'оруж', 'weapon', 'nuclear', 'ядер',
    'авианос', 'aircraft carrier', 'подводн', 'submarine',
    'противовоздушн', '\\bпво\\b', 'air defense', 'зенитн',
    # Rockets — require word boundary to reduce space rocket matches
    # (Space context excluded below)
    '\\bракет',
    # Tanks — require word boundary (Kim Jong Un tank match is excluded by
    # requiring co-occurrence with Baltic/European context)
    '\\bтанк', '\\btank',
    # Intelligence / espionage
    'шпион', 'spy', 'espionage', 'развед', 'intelligence', 'разведк',
    'диверс', 'sabotage', 'диверсант',
    'кибер', 'cyber', 'хакер', 'hacker',
    # Sanctions / geopolitics
    'санкци', 'sanction', 'эмбарго', 'embargo',
    # NATO/EU/defense alliances — word boundary to avoid 'чемпионатов'
    '\\bнато\\b', '\\bnato\\b', 'альянс', 'alliance',
    # Information warfare
    'пропаганд', 'propaganda', 'дезинформ', 'disinformation',
    'вмешательств', 'interference', 'гибридн', 'hybrid',
    'информацион.*война', 'infowar',
    # Specific threat actors
    'вагнер', 'wagner', '\\bгру\\b', '\\bgru\\b', 'фсб', 'fsb', '\\bсвр\\b',
    # Border security
    'границ', 'border', 'мигра', 'migrant', 'беженц', 'refugee',
    # Energy security
    'газопровод', 'pipeline', 'северный поток', 'nord stream',
    'турецкий поток', 'turkish stream', 'энергетик',
    # Maritime security
    'теневой флот', 'shadow fleet', 'каботаж',
]

# Context-based EXCLUSION patterns — if ANY of these match, the event
# is reclassified as NOISE even if Baltic/security keywords matched.
# This catches false positives from substring collisions.
SPORTS_EXCLUSION = [
    'нхл', 'nhl', '\\bрпл\\b', 'премьер-лиг', 'лига чемпионов',
    '\\bцска\\b', '\\bспартак', '\\bзенит', '\\bдинамо',
    '\\bшайб', 'хоккей', 'плей-офф', 'овечкин',
    '\\bматч\\b', 'турнир', 'чемпионат.*мира',
    'wada', 'допинг', 'гонк', 'забросил.*шайб',
    'удален.*матч', 'уступил.*рпл', 'пропуска.*пачками',
    'болельщик', 'тренер.*клуб',
]

SPACE_EXCLUSION = [
    'байконур', 'роскосмос', 'космос', '\\bмкс\\b',
    'прогресс.*мс', 'союз.*мс', 'стартов.*стол',
    'орбит', 'космическ', 'спутник.*запуск',
]

CELEBRATION_EXCLUSION = [
    'поздравил.*8 марта', 'поздравил.*марта',
    'с праздником', 'родительск.*суббот',
    'великий.*пост', 'молитв.*мечет',
]

# Noise sub-categories with their own keyword patterns
DOMESTIC_RUSSIA_KEYWORDS = [
    'губернатор', 'область', 'регион', 'миллион рублей', 'рубл',
    'суд взыскал', 'маркетплейс', 'контрафакт', 'мечеть', 'молитв',
    'алкогол', 'россельхознадзор', 'ветеринар', 'пожар', 'наводнен',
    'землетрясен', 'похорон', 'умер', 'умерла', 'похороны', 'свадьб',
    'родительск', 'великий пост', 'церков', 'храм', 'игумен',
    'культур', 'форум', 'выставк', 'магнитн.*бур', 'метеор',
    'рпл', 'чемпионат', 'олимпи', 'интернет.*сбо', 'telegram.*сбо',
    'монет', 'доллар', 'евро', 'укреплен', 'курс.*валют',
    'москв', 'петербург.*форум', 'россиян.*рассказ',
]

UKRAINE_FRONTLINE_KEYWORDS = [
    'всу', 'вс украин', 'донецк', 'донбасс', 'херсон', 'запорож',
    'фронт', 'бригад', 'штурм', 'десант', 'плацдарм', 'окоп',
    'мариупол', 'бахмут', 'авдеевк', 'угледар', 'артемовск',
    'курск.*атак', 'брянск.*атак', 'белгород.*обстрел',
    'тцк', 'мобилиз.*украин', 'уклонист',
    'суми', 'сумск', 'харьков.*обстрел', 'одесс',
    'зеленск', 'буданов', 'сырск',
    'пленн', 'обмен.*пленн', 'ликвидирова',
    'геран', 'шахед', 'shahed',
]

MIDDLE_EAST_KEYWORDS = [
    'иран', 'iran', 'тегеран', 'tehran', 'исфахан', 'isfahan',
    'хамас', 'hamas', 'хезболл', 'hezbollah', 'хизболл',
    'израиль', 'israel', 'цахал', 'idf', 'нетаньяху',
    'газа', 'gaza', 'палестин', 'palestine',
    'ирак', 'iraq', 'багдад', 'baghdad',
    'йемен', 'yemen', 'хути', 'houthi',
    'ормузск', 'hormuz', 'красн.*мор',
    'ближн.*восток', 'middle east',
    'сирия', 'syria', 'ливан', 'lebanon', 'ливии', 'libya',
]

SPORTS_CULTURE_KEYWORDS = [
    'нхл', 'nhl', 'шайб', 'хоккей', 'hockey', 'футбол', 'football',
    'soccer', 'баскетбол', 'basketball', 'теннис', 'tennis',
    'олимпи', 'olympic', 'чемпионат мира', 'world cup',
    'рпл', 'премьер-лиг', 'лига чемпионов', 'champions league',
    'цска', 'спартак', 'зенит', 'динамо',
    'актёр', 'актер', 'актрис', 'режиссёр', 'режиссер',
    'фильм', 'кино', 'сериал', 'концерт', 'гастроли',
    'писатель', 'поэт', 'литератур', 'книг',
    'wada', 'допинг', 'doping',
    'овечкин', 'ovechkin',
]

GLOBAL_POLITICS_KEYWORDS = [
    'сша.*внутренн', 'демократ.*партия', 'республиканц',
    'конгресс.*сша', 'сенат.*сша',
    'трамп.*монет', 'трамп.*грозн',
    'китай.*торгов', 'china.*trade', 'пекин',
    'индия', 'india', 'модi',
    'африк', 'africa', 'кения', 'kenya',
    'венесуэл', 'куб', 'мексик',
    'северн.*коре', 'north korea', 'ким чен',
    'япони', 'japan', 'токио',
    'космос', 'ракет.*байконур', 'космический',
    'прогресс.*мс', 'союз.*мс', 'старт.*стол',
]


def match_keywords(text, keywords):
    """Check if any keyword pattern matches the text.
    
    Keywords containing \\b or .* are treated as regex patterns.
    All others are simple substring matches.
    """
    for kw in keywords:
        if '\\b' in kw or '.*' in kw:
            # Regex pattern
            if re.search(kw, text, re.IGNORECASE):
                return True
        else:
            if kw in text:
                return True
    return False


def match_keywords_list(text, keywords):
    """Return ALL matching keywords (for debugging)."""
    matched = []
    for kw in keywords:
        if '\\b' in kw or '.*' in kw:
            if re.search(kw, text, re.IGNORECASE):
                matched.append(kw)
        else:
            if kw in text:
                matched.append(kw)
    return matched


# ================================================================
# 3. CLASSIFY ALL LAUNDERING EVENTS
# ================================================================
print("\n" + "=" * 72)
print("2. CLASSIFYING LAUNDERING EVENTS")
print("=" * 72)

results = []
exclusion_stats = {'sports': 0, 'space': 0, 'celebration': 0}

for o in laundering:
    title = (o.get('first_title', '') or '').lower()
    cats = o.get('categories', '')
    category_count = int(o['category_count'])

    # Step 1: Check Baltic/security keyword matches
    is_baltic = match_keywords(title, BALTIC_KEYWORDS)
    is_security = match_keywords(title, SECURITY_KEYWORDS)
    raw_relevant = is_baltic or is_security

    # Step 2: Apply context-based exclusions (fix false positives)
    # Items that matched keywords but are actually about sports, space, etc.
    excluded = False
    exclusion_reason = ''
    if raw_relevant:
        if match_keywords(title, SPORTS_EXCLUSION):
            excluded = True
            exclusion_reason = 'sports_context'
            exclusion_stats['sports'] += 1
        elif match_keywords(title, SPACE_EXCLUSION):
            excluded = True
            exclusion_reason = 'space_context'
            exclusion_stats['space'] += 1
        elif match_keywords(title, CELEBRATION_EXCLUSION):
            excluded = True
            exclusion_reason = 'celebration_context'
            exclusion_stats['celebration'] += 1

    is_relevant = raw_relevant and not excluded

    # Step 3: For noise items, sub-classify
    noise_class = 'other'
    if not is_relevant:
        if exclusion_reason:
            noise_class = exclusion_reason
        elif match_keywords(title, SPORTS_CULTURE_KEYWORDS):
            noise_class = 'sports_culture'
        elif match_keywords(title, MIDDLE_EAST_KEYWORDS):
            noise_class = 'middle_east_iran'
        elif match_keywords(title, UKRAINE_FRONTLINE_KEYWORDS):
            noise_class = 'ukraine_frontline'
        elif match_keywords(title, DOMESTIC_RUSSIA_KEYWORDS):
            noise_class = 'domestic_russia'
        elif match_keywords(title, GLOBAL_POLITICS_KEYWORDS):
            noise_class = 'global_politics'

    results.append({
        'origin_id': o['id'],
        'cluster_id': o['cluster_id'],
        'title': o.get('first_title', '')[:200],
        'categories': cats,
        'category_count': category_count,
        'first_category': o['first_category'],
        'first_published': o.get('first_published', ''),
        'signal_count': o.get('signal_count', ''),
        'is_relevant': is_relevant,
        'is_baltic': is_baltic and not excluded,
        'is_security': is_security and not excluded,
        'noise_class': noise_class if not is_relevant else '',
    })

relevant = [r for r in results if r['is_relevant']]
noise = [r for r in results if not r['is_relevant']]

pct_noise = len(noise) / len(results) * 100
pct_relevant = len(relevant) / len(results) * 100

print(f"\n  Total laundering events: {len(results)}")
print(f"  ✅ RELEVANT (Baltic/security): {len(relevant)} ({pct_relevant:.1f}%)")
print(f"  ❌ NOISE (irrelevant):         {len(noise)} ({pct_noise:.1f}%)")

# Relevance breakdown
baltic_only = sum(1 for r in relevant if r['is_baltic'] and not r['is_security'])
security_only = sum(1 for r in relevant if r['is_security'] and not r['is_baltic'])
both = sum(1 for r in relevant if r['is_baltic'] and r['is_security'])
print(f"\n  Relevance breakdown:")
print(f"    Baltic keywords only:   {baltic_only}")
print(f"    Security keywords only: {security_only}")
print(f"    Both:                   {both}")

# Exclusion stats
total_excluded = sum(exclusion_stats.values())
if total_excluded > 0:
    print(f"\n  Context exclusions (keyword-matched but reclassified as noise):")
    for reason, cnt in exclusion_stats.items():
        if cnt > 0:
            print(f"    {reason}: {cnt} items")
    print(f"    Total excluded: {total_excluded}")


# ================================================================
# 4. NOISE SUB-CLASSIFICATION
# ================================================================
print("\n" + "=" * 72)
print("3. NOISE SUB-CLASSIFICATION")
print("=" * 72)

noise_classes = Counter(r['noise_class'] for r in noise)
print(f"\n  {'Noise Class':<25s} {'Count':>6} {'% of Noise':>11} {'% of Total':>11}")
print(f"  " + "-" * 58)
for cls, cnt in noise_classes.most_common():
    pct_n = cnt / len(noise) * 100
    pct_t = cnt / len(results) * 100
    print(f"  {cls:<25s} {cnt:>6d} {pct_n:>10.1f}% {pct_t:>10.1f}%")

# Print examples for each noise class
print("\n  NOISE EXAMPLES BY CLASS:")
for cls in ['ukraine_frontline', 'middle_east_iran', 'domestic_russia',
            'sports_culture', 'global_politics', 'other']:
    items = [r for r in noise if r['noise_class'] == cls]
    if not items:
        continue
    print(f"\n  === {cls.upper()} ({len(items)} items) ===")
    for r in items[:5]:
        title = r['title'][:90]
        print(f"    • [{r['categories'][:35]:35s}] {title}")


# ================================================================
# 5. RELEVANT EVENTS — what REAL laundering looks like
# ================================================================
print("\n" + "=" * 72)
print("4. RELEVANT EVENTS — actual laundering candidates")
print("=" * 72)

print(f"\n  {len(relevant)} events that match Baltic/security keywords:\n")
for r in relevant:
    tags = []
    if r['is_baltic']:
        tags.append('BALTIC')
    if r['is_security']:
        tags.append('SECURITY')
    tag_str = '+'.join(tags)
    title = r['title'][:85]
    print(f"  [{r['category_count']:d}] [{tag_str:16s}] {title}")


# ================================================================
# 6. SCORE IMPACT — current vs filtered
# ================================================================
print("\n" + "=" * 72)
print("5. SCORE IMPACT — current vs relevance-filtered")
print("=" * 72)

# Current: all laundering events count
current_count = len(laundering)
current_norm = min(current_count, 100)
current_score = current_norm * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)

# Filtered: only relevant events count
filtered_count = len(relevant)
filtered_norm = min(filtered_count, 100)
filtered_score = filtered_norm * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)

print(f"\n  {'Metric':<35s} {'Current':>10} {'Filtered':>10} {'Δ':>10}")
print(f"  " + "-" * 68)
print(f"  {'Laundering event count':<35s} {current_count:>10d} {filtered_count:>10d} "
      f"{filtered_count - current_count:>+10d}")
print(f"  {'Normalized (min(count,100))':<35s} {current_norm:>10d} {filtered_norm:>10d} "
      f"{filtered_norm - current_norm:>+10d}")
print(f"  {'CTI contribution':<35s} {current_score:>10.2f} {filtered_score:>10.2f} "
      f"{filtered_score - current_score:>+10.2f}")
print(f"  {'Max possible contribution':<35s} "
      f"{100 * LAUNDERING_WEIGHT / TOTAL_WEIGHT:>10.2f} "
      f"{100 * LAUNDERING_WEIGHT / TOTAL_WEIGHT:>10.2f} {'':>10s}")

reduction_pct = (1 - filtered_score / current_score) * 100 if current_score > 0 else 0
print(f"\n  Score reduction: {reduction_pct:.1f}%")
print(f"  {current_score:.2f} → {filtered_score:.2f} "
      f"(saves {current_score - filtered_score:.2f} CTI points)")


# ================================================================
# 7. CATEGORY_COUNT THRESHOLD ANALYSIS
# ================================================================
print("\n" + "=" * 72)
print("6. CATEGORY_COUNT THRESHOLD ANALYSIS")
print("=" * 72)

print("\n  Testing different category_count thresholds combined with")
print("  relevance filtering.\n")

print(f"  {'Threshold':<12} {'Total':>6} {'Relevant':>9} {'Noise':>6} "
      f"{'Noise%':>7} {'Score':>7} {'Filt.Score':>11}")
print(f"  " + "-" * 65)

threshold_analysis = []
for thresh in [2, 3, 4, 5]:
    events = [o for o in state_origins if int(o['category_count']) >= thresh]
    # Re-classify these events using the same logic with exclusions
    rel_count = 0
    noise_count = 0
    for o in events:
        title = (o.get('first_title', '') or '').lower()
        raw_rel = (match_keywords(title, BALTIC_KEYWORDS) or
                   match_keywords(title, SECURITY_KEYWORDS))
        # Apply same exclusions
        excl = False
        if raw_rel:
            if match_keywords(title, SPORTS_EXCLUSION):
                excl = True
            elif match_keywords(title, SPACE_EXCLUSION):
                excl = True
            elif match_keywords(title, CELEBRATION_EXCLUSION):
                excl = True
        if raw_rel and not excl:
            rel_count += 1
        else:
            noise_count += 1

    total = len(events)
    noise_pct = noise_count / total * 100 if total > 0 else 0
    unfiltered_score = min(total, 100) * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)
    filt_score = min(rel_count, 100) * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)

    threshold_analysis.append({
        'threshold': thresh,
        'total': total,
        'relevant': rel_count,
        'noise': noise_count,
        'noise_pct': noise_pct,
        'unfiltered_score': unfiltered_score,
        'filtered_score': filt_score,
    })

    print(f"  cat>={thresh:<8d} {total:>6d} {rel_count:>9d} {noise_count:>6d} "
          f"{noise_pct:>6.1f}% {unfiltered_score:>7.2f} {filt_score:>11.2f}")

# Cross-analysis: which threshold+filter combo is best?
print(f"\n  Analysis:")
for ta in threshold_analysis:
    if ta['threshold'] == 2:
        base = ta['unfiltered_score']

for ta in threshold_analysis:
    reduction = (1 - ta['filtered_score'] / base) * 100 if base > 0 else 0
    print(f"    cat>={ta['threshold']}: "
          f"Score goes from {base:.2f} (current) → {ta['filtered_score']:.2f} "
          f"({reduction:.0f}% reduction), "
          f"keeps {ta['relevant']} real events, drops {ta['noise']} noise")


# ================================================================
# 8. CROSS-CATEGORY ANALYSIS — which category combos are noise?
# ================================================================
print("\n" + "=" * 72)
print("7. CROSS-CATEGORY ANALYSIS")
print("=" * 72)

print("\n  Does the category combination predict relevance?\n")

cat_combos = defaultdict(lambda: {'relevant': 0, 'noise': 0, 'total': 0})
for r in results:
    combo = r['categories'].strip('{}')
    cat_combos[combo]['total'] += 1
    if r['is_relevant']:
        cat_combos[combo]['relevant'] += 1
    else:
        cat_combos[combo]['noise'] += 1

# Sort by total
print(f"  {'Category Combo':<55s} {'Tot':>4} {'Rel':>4} {'Noise':>6} {'Noise%':>7}")
print(f"  " + "-" * 80)
for combo, stats in sorted(cat_combos.items(), key=lambda x: -x[1]['total']):
    if stats['total'] < 2:
        continue  # skip singletons
    noise_pct = stats['noise'] / stats['total'] * 100 if stats['total'] > 0 else 0
    print(f"  {combo:<55s} {stats['total']:>4d} {stats['relevant']:>4d} "
          f"{stats['noise']:>6d} {noise_pct:>6.0f}%")

# Key finding: is {russian_state,ru_state} (most common) mostly noise?
rs_combo = cat_combos.get('russian_state,ru_state', {})
print(f"\n  Dominant combo 'russian_state,ru_state': "
      f"{rs_combo.get('total',0)} total, "
      f"{rs_combo.get('relevant',0)} relevant, "
      f"{rs_combo.get('noise',0)} noise "
      f"({rs_combo.get('noise',0)/max(rs_combo.get('total',1),1)*100:.0f}% noise)")
print(f"  → This combo is two sub-labels of the SAME source ecosystem.")
print(f"    'russian_state' and 'ru_state' are both state media — seeing a")
print(f"    story on both is EXPECTED, not 'laundering'.")


# ================================================================
# 9. TEMPORAL ANALYSIS — noise distribution over time
# ================================================================
print("\n" + "=" * 72)
print("8. TEMPORAL ANALYSIS — noise vs relevant over time")
print("=" * 72)

# Group by week
weekly = defaultdict(lambda: {'relevant': 0, 'noise': 0})
for r in results:
    pub = r.get('first_published', '')
    if not pub:
        continue
    try:
        dt = datetime.strptime(pub[:10], "%Y-%m-%d")
        # ISO week
        year, week_num, _ = dt.isocalendar()
        week_key = f"{year}-W{week_num:02d}"
    except ValueError:
        continue
    if r['is_relevant']:
        weekly[week_key]['relevant'] += 1
    else:
        weekly[week_key]['noise'] += 1

print(f"\n  {'Week':<12} {'Relevant':>9} {'Noise':>6} {'Total':>6} {'Noise%':>7} "
      f"{'Score(all)':>11} {'Score(filt)':>12}")
print(f"  " + "-" * 68)
for week in sorted(weekly.keys()):
    w = weekly[week]
    total = w['relevant'] + w['noise']
    noise_pct = w['noise'] / total * 100 if total > 0 else 0
    s_all = min(total, 100) * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)
    s_filt = min(w['relevant'], 100) * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)
    print(f"  {week:<12} {w['relevant']:>9d} {w['noise']:>6d} {total:>6d} "
          f"{noise_pct:>6.0f}% {s_all:>11.2f} {s_filt:>12.2f}")


# ================================================================
# 10. STRUCTURAL ISSUE: russian_state vs ru_state overlap
# ================================================================
print("\n" + "=" * 72)
print("9. STRUCTURAL ISSUE — category overlap")
print("=" * 72)

# Check: how many laundering events are ONLY russian_state + ru_state overlap?
state_only_combos = {'russian_state,ru_state', 'ru_state,russian_state'}
state_overlap = [r for r in results
                 if r['categories'].strip('{}') in state_only_combos]

print(f"\n  Events with categories = {{russian_state, ru_state}} only: "
      f"{len(state_overlap)}/{len(results)} ({len(state_overlap)/len(results)*100:.0f}%)")
print(f"  These represent the SAME state media ecosystem split into 2 feed labels.")
print(f"  Counting this as 'cross-category spread' is a DEFINITIONAL error.")
print(f"\n  Of these {len(state_overlap)} events:")
rel_in_overlap = sum(1 for r in state_overlap if r['is_relevant'])
noise_in_overlap = sum(1 for r in state_overlap if not r['is_relevant'])
print(f"    Relevant: {rel_in_overlap}")
print(f"    Noise:    {noise_in_overlap}")

# What if we treat {russian_state, ru_state} as ONE category?
print(f"\n  RECOMMENDATION: Merge 'russian_state' and 'ru_state' into a single")
print(f"  category for laundering detection. This alone would eliminate")
print(f"  {len(state_overlap)} events ({len(state_overlap)/len(results)*100:.0f}% of laundering).")

# Re-compute: what does laundering look like with merged categories?
print(f"\n  Simulated merged-category laundering:")
merged_results = []
for o in state_origins:
    cats = o['categories'].strip('{}').split(',')
    # Merge russian_state and ru_state
    merged = set()
    for c in cats:
        c = c.strip()
        if c in ('russian_state', 'ru_state'):
            merged.add('ru_state_merged')
        else:
            merged.add(c)
    merged_count = len(merged)
    if merged_count >= 2:
        merged_results.append(o)

print(f"    Before merge: {len(laundering)} laundering events")
print(f"    After merge:  {len(merged_results)} laundering events "
      f"(reduced by {len(laundering) - len(merged_results)})")
merged_score = min(len(merged_results), 100) * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)
print(f"    Score: {merged_score:.2f} (was {current_score:.2f})")


# ================================================================
# 11. COMBINED FIX — merge + relevance filter
# ================================================================
print("\n" + "=" * 72)
print("10. COMBINED FIX — merge categories + relevance filter")
print("=" * 72)

# Apply both fixes: merge ru_state/russian_state AND filter by relevance
combined_relevant = 0
combined_total = 0
for o in state_origins:
    cats = o['categories'].strip('{}').split(',')
    merged = set()
    for c in cats:
        c = c.strip()
        if c in ('russian_state', 'ru_state'):
            merged.add('ru_state_merged')
        else:
            merged.add(c)
    if len(merged) < 2:
        continue
    combined_total += 1
    title = (o.get('first_title', '') or '').lower()
    raw_rel = (match_keywords(title, BALTIC_KEYWORDS) or
               match_keywords(title, SECURITY_KEYWORDS))
    excl = False
    if raw_rel:
        if match_keywords(title, SPORTS_EXCLUSION):
            excl = True
        elif match_keywords(title, SPACE_EXCLUSION):
            excl = True
        elif match_keywords(title, CELEBRATION_EXCLUSION):
            excl = True
    if raw_rel and not excl:
        combined_relevant += 1

combined_score = min(combined_relevant, 100) * (LAUNDERING_WEIGHT / TOTAL_WEIGHT)

print(f"\n  {'Fix Strategy':<45s} {'Events':>7} {'Score':>7}")
print(f"  " + "-" * 62)
print(f"  {'Current (no fix)':<45s} {len(laundering):>7d} {current_score:>7.2f}")
print(f"  {'Relevance filter only':<45s} {len(relevant):>7d} {filtered_score:>7.2f}")
print(f"  {'Category merge only':<45s} {len(merged_results):>7d} {merged_score:>7.2f}")
print(f"  {'Merge + relevance filter':<45s} {combined_relevant:>7d} {combined_score:>7.2f}")
print(f"  {'cat>=3 + relevance filter':<45s} "
      f"{threshold_analysis[1]['relevant']:>7d} "
      f"{threshold_analysis[1]['filtered_score']:>7.2f}")

# Best fix
best_score = combined_score
best_label = "merge + relevance filter"
if threshold_analysis[1]['filtered_score'] < best_score:
    best_score = threshold_analysis[1]['filtered_score']
    best_label = "cat>=3 + relevance filter"

print(f"\n  Best fix: {best_label}")
print(f"  Reduces laundering from {current_score:.2f} to {best_score:.2f} "
      f"({(1 - best_score/current_score)*100:.0f}% reduction)")
print(f"  Saves {current_score - best_score:.2f} CTI points")


# ================================================================
# 12. EDGE CASES — borderline items
# ================================================================
print("\n" + "=" * 72)
print("11. EDGE CASES — borderline classifications")
print("=" * 72)

# Items that mention Ukraine/Russia but have Baltic relevance
print("\n  Events marked NOISE that might be borderline:")
borderline_keywords = ['белгород', 'брянск', 'смоленск', 'курск', 'ленобласт',
                       'европ', 'ес ', ' eu ', 'запад', 'western']
borderline = []
for r in noise:
    title_lower = r['title'].lower()
    for bk in borderline_keywords:
        if bk in title_lower:
            borderline.append((r, bk))
            break

print(f"  Found {len(borderline)} borderline items:")
for r, keyword in borderline[:10]:
    print(f"    [{r['noise_class']:20s}] (matched '{keyword}') {r['title'][:75]}")

print(f"\n  Note: These items mention Russia-adjacent regions but don't")
print(f"  directly relate to Baltic security. The classifier is CONSERVATIVE")
print(f"  — it errs on the side of excluding noise rather than including it.")


# ================================================================
# 13. EXPORT laundering_classified.csv
# ================================================================
print("\n" + "=" * 72)
print("12. EXPORTING laundering_classified.csv")
print("=" * 72)

csv_path = f"{DATA}/laundering_classified.csv"
fieldnames = ['origin_id', 'cluster_id', 'title', 'categories', 'category_count',
              'first_category', 'first_published', 'signal_count',
              'is_relevant', 'is_baltic', 'is_security', 'noise_class']

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for r in results:
        writer.writerow(r)

print(f"\n  Written {len(results)} rows to {csv_path}")
print(f"  Columns: {', '.join(fieldnames)}")


# ================================================================
# 14. SUMMARY & RECOMMENDATIONS
# ================================================================
print("\n" + "=" * 72)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 72)

print(f"""
KEY FINDINGS:

1. NOISE RATE: {pct_noise:.0f}%
   Of {len(results)} laundering events, only {len(relevant)} ({pct_relevant:.0f}%) are
   actually relevant to Baltic security. The remaining {len(noise)} ({pct_noise:.0f}%)
   are general Russian domestic news, sports, Middle East events, and
   Ukraine frontline updates with no Baltic dimension.

2. DOMINANT NOISE CLASS: {noise_classes.most_common(1)[0][0]} ({noise_classes.most_common(1)[0][1]} items)
   The biggest source of noise is {noise_classes.most_common(1)[0][0]}, followed by
   {noise_classes.most_common(2)[1][0]} ({noise_classes.most_common(2)[1][1]} items).

3. STRUCTURAL FLAW: russian_state / ru_state overlap
   {len(state_overlap)} of {len(results)} laundering events ({len(state_overlap)/len(results)*100:.0f}%)
   have categories {{russian_state, ru_state}} — two labels for the SAME
   state media ecosystem. This is not cross-category spread; it's a
   labeling artifact.

4. SCORE IMPACT:
   Current laundering CTI contribution: {current_score:.2f}
   With relevance filter only:          {filtered_score:.2f}
   With category merge only:            {merged_score:.2f}
   With merge + relevance filter:       {combined_score:.2f}
   With cat>=3 + relevance filter:      {threshold_analysis[1]['filtered_score']:.2f}

RECOMMENDED FIX (production):

  Option A (simple, immediate):
    Relevance filter — require title/content match against Baltic+security
    keywords before counting as laundering.
    Score: {current_score:.2f} → {filtered_score:.2f} ({(1-filtered_score/current_score)*100:.0f}% reduction)

  Option B (structural, better):
    1. Merge 'russian_state' and 'ru_state' into one category
    2. Apply relevance filter
    Score: {current_score:.2f} → {combined_score:.2f} ({(1-combined_score/current_score)*100:.0f}% reduction)

  Option C (aggressive):
    Raise category_count threshold to >=3 AND apply relevance filter.
    Score: {current_score:.2f} → {threshold_analysis[1]['filtered_score']:.2f} ({(1-threshold_analysis[1]['filtered_score']/current_score)*100:.0f}% reduction)
    ⚠️  This is more aggressive — may drop some real laundering.

  Recommended: Option B (merge + relevance filter)
    It fixes the structural labeling issue AND removes topical noise
    while keeping real cross-ecosystem laundering events.
""")

print("Done.")
