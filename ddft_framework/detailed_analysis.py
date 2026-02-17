#!/usr/bin/env python3
"""
Detailed DDFT Analysis - Debug HOC and compute Turn 4 correlations
"""

import json
import numpy as np
from scipy import stats

# Load intermediate results
with open('intermediate_results.json', 'r') as f:
    results = json.load(f)

# Load raw data
import glob
from collections import defaultdict
from pathlib import Path

COMPRESSION_MAP = {
    'c00': 0.0,
    'c025': 0.25,
    'c05': 0.5,
    'c075': 0.75,
    'c10': 1.0
}

MODELS = [
    'o4-mini',
    'o3',
    'gpt-5',
    'claude-haiku-4-5',
    'grok-4-fast-non-reasoning',
    'mistral-medium-2505',
    'phi-4',
    'gpt-oss-120b',
    'Llama-4-Maverick-17B-128E-Instruct-FP8'
]

print("=" * 80)
print("DETAILED ANALYSIS: HOC VALUES AND TURN 4")
print("=" * 80)

# Load all data again
data = {}
for filepath in glob.glob('results/ddft_*.json'):
    filename = Path(filepath).stem
    parts = filename.split('_')
    if len(parts) < 4:
        continue

    model = parts[1]
    concept = parts[2]
    compression = parts[3]

    if model not in data:
        data[model] = {}
    if concept not in data[model]:
        data[model][concept] = {}

    with open(filepath, 'r') as f:
        data[model][concept][compression] = json.load(f)

# Analyze HOC calculation for each model
print("\n" + "=" * 80)
print("HOC CALCULATION DETAILS")
print("=" * 80)

for model in MODELS:
    if model not in data:
        continue

    print(f"\n{model}:")
    print("-" * 60)

    # Compute mean FAR at each compression level
    far_by_c = defaultdict(list)

    for concept in data[model]:
        for comp_level in data[model][concept]:
            c_value = COMPRESSION_MAP.get(comp_level)
            if c_value is None:
                continue

            conv_log = data[model][concept][comp_level].get('conversation_log', [])
            for turn in conv_log:
                if 'evaluation' in turn and 'consensus' in turn['evaluation']:
                    far = turn['evaluation']['consensus'].get('FAR')
                    if far is not None:
                        far_by_c[c_value].append(far)

    # Show mean FAR at each compression level
    for c in sorted(far_by_c.keys()):
        mean_far = np.mean(far_by_c[c])
        n = len(far_by_c[c])
        above_threshold = "✓ ABOVE 0.70" if mean_far >= 0.70 else "✗ BELOW 0.70"
        print(f"  c={c:.2f}: mean FAR = {mean_far:.3f} (n={n:3d}) {above_threshold}")

    # Compute HOC
    hoc = 0.0
    for c in sorted([0.0, 0.25, 0.5, 0.75, 1.0], reverse=True):
        if c in far_by_c and len(far_by_c[c]) > 0:
            mean_far = np.mean(far_by_c[c])
            if mean_far >= 0.70:
                hoc = c
                break

    print(f"  → HOC = {hoc:.2f}")

# Analyze Turn 4 performance
print("\n" + "=" * 80)
print("TURN 4 ANALYSIS (Fabrication Trap)")
print("=" * 80)

turn4_data = {}

for model in MODELS:
    if model not in data:
        continue

    turn4_far = []

    for concept in data[model]:
        for comp_level in data[model][concept]:
            conv_log = data[model][concept][comp_level].get('conversation_log', [])

            # Turn 4 is index 3 (0-indexed)
            if len(conv_log) > 3:
                turn = conv_log[3]
                if 'evaluation' in turn and 'consensus' in turn['evaluation']:
                    far = turn['evaluation']['consensus'].get('FAR')
                    if far is not None:
                        turn4_far.append(far)

    if turn4_far:
        turn4_data[model] = {
            'mean_far': np.mean(turn4_far),
            'std_far': np.std(turn4_far),
            'n': len(turn4_far)
        }

        print(f"\n{model}:")
        print(f"  Mean FAR (Turn 4): {turn4_data[model]['mean_far']:.3f}")
        print(f"  Std FAR (Turn 4):  {turn4_data[model]['std_far']:.3f}")
        print(f"  n = {turn4_data[model]['n']}")

# Compute Turn 4 vs CI correlation
print("\n" + "=" * 80)
print("TURN 4 vs CI CORRELATION")
print("=" * 80)

models_sorted = sorted([m for m in MODELS if m in results['model_metrics'] and m in turn4_data])
ci_scores = [results['model_metrics'][m]['CI'] for m in models_sorted]
turn4_fars = [turn4_data[m]['mean_far'] for m in models_sorted]

if len(ci_scores) >= 3:
    rho, p = stats.spearmanr(turn4_fars, ci_scores)
    print(f"\nSpearman ρ = {rho:.3f}, p = {p:.3f}")
    print(f"n = {len(ci_scores)}")
    print("\nExpected from paper: ρ = -0.817, p = 0.007")
    print("\nNote: Negative correlation expected (lower Turn 4 FAR → lower CI)")
else:
    print(f"\nInsufficient data (n={len(ci_scores)})")

# Show model rankings by Turn 4 FAR
print("\n" + "=" * 80)
print("MODEL RANKINGS BY TURN 4 FAR (Error Detection)")
print("=" * 80)

ranked_models = sorted(turn4_data.items(), key=lambda x: x[1]['mean_far'], reverse=True)
print("\nRank  Model                                    Turn 4 FAR")
print("-" * 70)
for i, (model, stats_dict) in enumerate(ranked_models, 1):
    print(f"{i:2d}.   {model:40s} {stats_dict['mean_far']:.3f}")

print("\n" + "=" * 80)
print("EXPECTED RANKINGS FROM PAPER (Table 3, page 7)")
print("=" * 80)
print("""
1. o4-mini
2. grok-4-fast-non-reasoning
3. mistral-medium-2505
4. gpt-oss-120b
5. o3
6. phi-4
7. gpt-5
8. Llama-4-Maverick-17B-128E-Instruct-FP8
9. claude-haiku-4-5
""")
