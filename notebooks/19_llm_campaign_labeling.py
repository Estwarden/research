#!/usr/bin/env python3
"""
19. LLM-Based Campaign Labeling
================================

Problem: 30 campaigns have no ground truth labels. Manual labeling
introduces human bias. Name-matching labeling is superficial.

Method: Use LLM to classify each campaign based on:
- Campaign name
- Summary text
- Severity
- Signal count
- Source categories present

Classification: HOSTILE_IO (state-directed info op), HYPE_FARMING 
(engagement-driven panic), ORGANIC (legitimate news coverage),
NARRATIVE_TAG (not a real campaign)

Validation: Compare LLM labels with name-matched labels.
Agreement rate = measure of labeling quality.

NOTE: This experiment requires an API key for the LLM.
Set OPENROUTER_API_KEY environment variable.
"""

import csv
import json
import os
import sys
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

CLASSIFICATION_PROMPT = """You are a disinformation analyst. Classify this detected campaign into one of four categories based ONLY on the evidence provided.

Categories:
- HOSTILE_IO: State-directed information operation. Evidence: state media coordination, fabricated content, strategic timing.
- HYPE_FARMING: Engagement-driven content for revenue. Evidence: clickbait patterns, monetization, no state coordination.
- ORGANIC: Legitimate news coverage. Evidence: accurate reporting, no coordination, factual content.
- NARRATIVE_TAG: This is a generic narrative category, not a specific campaign.

Campaign data:
- Name: {name}
- Severity: {severity}
- Confidence: {confidence}
- Signal count: {signal_count}
- Summary: {summary}

Respond with ONLY a JSON object:
{{"label": "HOSTILE_IO|HYPE_FARMING|ORGANIC|NARRATIVE_TAG", "reasoning": "one sentence explanation", "confidence": 0.0-1.0}}
"""


def classify_campaign(campaign, api_key):
    """Classify a single campaign using LLM."""
    prompt = CLASSIFICATION_PROMPT.format(
        name=campaign.get('name', ''),
        severity=campaign.get('severity', ''),
        confidence=campaign.get('confidence', ''),
        signal_count=campaign.get('signal_count', ''),
        summary=campaign.get('summary', '')[:300],
    )

    body = json.dumps({
        "model": "anthropic/claude-sonnet-4-5",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            content = data['choices'][0]['message']['content']
            # Parse JSON from response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
    return None


def main():
    api_key = os.environ.get('OPENROUTER_API_KEY', '')
    if not api_key:
        # Try vault
        try:
            import subprocess
            result = subprocess.run(
                ['wget', '-qO-', '--header', f'X-Vault-Token: {os.environ.get("VAULT_TOKEN", "")}',
                 f'{os.environ.get("VAULT_ADDR", "")}/v1/secret/data/openclaw'],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            api_key = data['data']['data'].get('openrouter_api_key', '')
        except:
            pass

    if not api_key:
        print("ERROR: No OPENROUTER_API_KEY. Set env var or configure vault.")
        sys.exit(1)

    # Load campaigns
    campaigns = []
    path = os.path.join(DATA_DIR, 'labeled_campaigns.csv')
    with open(path) as f:
        campaigns = list(csv.DictReader(f))

    print(f"Campaigns to label: {len(campaigns)}")
    print()

    # Classify each
    results = []
    for i, c in enumerate(campaigns):
        name = c.get('name', '')
        print(f"[{i + 1}/{len(campaigns)}] {name[:60]}...", end=' ')
        
        result = classify_campaign(c, api_key)
        if result:
            label = result.get('label', 'UNKNOWN')
            conf = result.get('confidence', 0)
            reason = result.get('reasoning', '')
            print(f"→ {label} ({conf:.0%})")
            
            c['llm_label'] = label
            c['llm_confidence'] = conf
            c['llm_reasoning'] = reason
        else:
            print("→ FAILED")
            c['llm_label'] = 'ERROR'
            c['llm_confidence'] = 0
            c['llm_reasoning'] = ''
        
        results.append(c)

    # Save results
    output_path = os.path.join(DATA_DIR, 'campaigns_llm_labeled.csv')
    fieldnames = list(results[0].keys())
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved to {output_path}")

    # Compare with name-matched labels
    print()
    print("=" * 70)
    print("VALIDATION: LLM vs Name-Matched Labels")
    print("=" * 70)

    from collections import Counter
    llm_counts = Counter(c.get('llm_label', '?') for c in results)
    name_counts = Counter(c.get('is_hostile_confirmed', '?') for c in results)
    
    print(f"  LLM labels: {dict(llm_counts)}")
    print(f"  Name labels: {dict(name_counts)}")

    # Agreement
    agree = 0
    disagree = []
    for c in results:
        llm = c.get('llm_label', '')
        name = c.get('is_hostile_confirmed', '')
        # Map name labels to LLM categories
        name_mapped = {
            'HOSTILE': 'HOSTILE_IO',
            'NARRATIVE_TAG': 'NARRATIVE_TAG',
        }.get(name, name)
        
        if llm == name_mapped:
            agree += 1
        else:
            disagree.append({
                'name': c.get('name', '')[:50],
                'llm': llm,
                'name_label': name,
            })

    print(f"\n  Agreement: {agree}/{len(results)} = {agree * 100 // len(results)}%")
    
    if disagree:
        print(f"  Disagreements ({len(disagree)}):")
        for d in disagree[:10]:
            print(f"    [{d['name_label']} vs {d['llm']}] {d['name']}")


if __name__ == '__main__':
    main()
