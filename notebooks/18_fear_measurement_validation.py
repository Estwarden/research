#!/usr/bin/env python3
"""
18. Fear Measurement Validation
================================

Problem: Keyword-based fear detection produces inflated scores because
military/defense reporting naturally contains words like "missile", "strike".

Method: Compare three approaches:
1. Raw keyword matching (FLAWED baseline)
2. Category-filtered matching (exclude defense sources)
3. Context-aware matching (only count when target is Baltic/Estonian)

Validate by checking:
- Does excluding defense sources change the result significantly?
- Is Baltic-specific fear different from general fear?
- Which sources produce the most TARGETED (Baltic-focused) fear?

Data: signals_14d.csv from EstWarden prod DB
"""

import csv
import math
import re
import os
from collections import defaultdict, Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

FEAR_PATTERNS = [
    r'attack|invasion|war|missile|bomb|strike|threat|danger',
    r'нападение|вторжение|война|ракет|удар|угроза|опасн',
    r'напад|вторгнення|війна|ракет|удар|загроза|небезпек',
]

BALTIC_FEAR_PATTERNS = [
    r'(?:attack|invasion|threat|danger).*(?:estonia|baltic|narva|tallinn)',
    r'(?:estonia|baltic|narva|tallinn).*(?:attack|invasion|threat|danger)',
    r'(?:нападен|вторж|угроз).*(?:эстон|прибалт|нарв|таллин)',
    r'(?:эстон|прибалт|нарв|таллин).*(?:нападен|вторж|угроз)',
    r'(?:напад|вторгн|загроз).*(?:естон|балт|нарв|таллін)',
]

PANIC_PATTERNS = [
    r'BREAKING|URGENT|⚡|‼|🚨|СРОЧНО|ТЕРМІНОВО',
    r'imminent|immediate|final.stage',
]

DEFENSE_SOURCES = {'milwatch', 'defense_rss', 'gdelt', 'deepstate'}


def has_pattern(text, patterns):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def mean(x):
    return sum(x) / len(x) if x else 0


def main():
    signals = []
    path = os.path.join(DATA_DIR, 'signals_14d.csv')
    with open(path, errors='replace') as f:
        for row in csv.DictReader(f):
            title = row.get('title', '') or ''
            pub = row.get('published_at', '') or ''
            cat = row.get('category', '') or ''
            src = row.get('source_type', '') or ''
            if title.strip() and pub:
                signals.append({
                    'title': title, 'date': pub[:10],
                    'category': cat, 'source': src,
                    'is_defense': src in DEFENSE_SOURCES,
                })

    public = [s for s in signals if not s['is_defense']]
    defense = [s for s in signals if s['is_defense']]

    print("=" * 70)
    print("APPROACH 1: Raw keyword matching (FLAWED)")
    print("=" * 70)
    raw_fear = sum(1 for s in signals if has_pattern(s['title'], FEAR_PATTERNS))
    print(f"  All signals: {raw_fear}/{len(signals)} = {raw_fear * 100 // len(signals)}% contain fear keywords")

    print()
    print("=" * 70)
    print("APPROACH 2: Category-filtered (exclude defense)")
    print("=" * 70)
    pub_fear = sum(1 for s in public if has_pattern(s['title'], FEAR_PATTERNS))
    def_fear = sum(1 for s in defense if has_pattern(s['title'], FEAR_PATTERNS))
    print(f"  Public signals: {pub_fear}/{len(public)} = {pub_fear * 100 // len(public)}%")
    print(f"  Defense signals: {def_fear}/{len(defense)} = {def_fear * 100 // len(defense)}% (expected high)")
    print(f"  Inflation from defense: {(raw_fear * 100 // len(signals)) - (pub_fear * 100 // len(public))} percentage points")

    print()
    print("=" * 70)
    print("APPROACH 3: Context-aware (Baltic-specific)")
    print("=" * 70)
    baltic_fear = sum(1 for s in signals if has_pattern(s['title'], BALTIC_FEAR_PATTERNS))
    baltic_pub = sum(1 for s in public if has_pattern(s['title'], BALTIC_FEAR_PATTERNS))
    print(f"  All signals: {baltic_fear}/{len(signals)} = {baltic_fear * 1000 // len(signals) / 10}%")
    print(f"  Public only: {baltic_pub}/{len(public)} = {baltic_pub * 1000 // len(public) / 10}%")

    print()
    print("=" * 70)
    print("FEAR BY SOURCE CATEGORY")
    print("=" * 70)
    by_cat = defaultdict(lambda: {'total': 0, 'fear': 0, 'baltic': 0, 'panic': 0})
    for s in public:
        cat = s['category'] or s['source'] or 'unknown'
        by_cat[cat]['total'] += 1
        if has_pattern(s['title'], FEAR_PATTERNS):
            by_cat[cat]['fear'] += 1
        if has_pattern(s['title'], BALTIC_FEAR_PATTERNS):
            by_cat[cat]['baltic'] += 1
        if has_pattern(s['title'], PANIC_PATTERNS):
            by_cat[cat]['panic'] += 1

    print(f"{'Category':<28} {'N':>6} {'Fear%':>6} {'Baltic%':>8} {'Panic%':>7}")
    print("-" * 60)
    for cat in sorted(by_cat.keys(), key=lambda x: -by_cat[x]['fear']):
        d = by_cat[cat]
        if d['total'] >= 20:
            fp = d['fear'] * 100 / d['total']
            bp = d['baltic'] * 100 / d['total']
            pp = d['panic'] * 100 / d['total']
            print(f"  {cat:<26} {d['total']:>6} {fp:>5.1f}% {bp:>7.1f}% {pp:>6.1f}%")

    print()
    print("=" * 70)
    print("DAILY TREND (public only)")
    print("=" * 70)
    by_date = defaultdict(list)
    for s in public:
        by_date[s['date']].append(s)

    daily = []
    for date in sorted(by_date.keys()):
        sigs = by_date[date]
        fp = sum(1 for s in sigs if has_pattern(s['title'], FEAR_PATTERNS)) / len(sigs) * 100
        daily.append(fp)
        bar = '█' * int(fp)
        print(f"  {date} n={len(sigs):>5} fear={fp:>5.1f}% {bar}")

    first = daily[:len(daily) // 2]
    second = daily[len(daily) // 2:]
    print(f"\n  Week 1: {mean(first):.1f}%")
    print(f"  Week 2: {mean(second):.1f}%")
    ratio = mean(second) / mean(first) if mean(first) > 0 else 1
    print(f"  Trend: {'RISING' if ratio > 1.15 else 'DECLINING' if ratio < 0.85 else 'STABLE'}")

    print()
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"  Raw fear (flawed):       {raw_fear * 100 // len(signals)}%")
    print(f"  Filtered fear (better):  {pub_fear * 100 // len(public)}%")
    print(f"  Baltic-specific (best):  {baltic_pub * 1000 // len(public) / 10}%")
    print(f"  Inflation from defense:  {(raw_fear * 100 // len(signals)) - (pub_fear * 100 // len(public))}pp")
    print()
    print("  LESSON: Keyword matching without context inflates fear scores.")
    print("  Defense reporting is NOT fear content — it must be excluded.")
    print("  Baltic-specific fear is near zero — global conflicts dominate.")


if __name__ == '__main__':
    main()
