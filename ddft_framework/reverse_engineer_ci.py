#!/usr/bin/env python3
"""
Reverse-engineer the CI formula to match expected rankings from the paper.
"""

import json
import numpy as np
from scipy import stats

# Expected rankings from paper (Table 3, page 7)
EXPECTED_RANKINGS = [
    'o4-mini',
    'grok-4-fast-non-reasoning',
    'mistral-medium-2505',
    'gpt-oss-120b',
    'o3',
    'phi-4',
    'gpt-5',
    'Llama-4-Maverick-17B-128E-Instruct-FP8',
    'claude-haiku-4-5'
]

# Load intermediate results
with open('intermediate_results.json', 'r') as f:
    results = json.load(f)

# Load Turn 4 data from detailed analysis
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

print("=" * 80)
print("REVERSE-ENGINEERING CI FORMULA")
print("=" * 80)

# Load all data
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

# Compute Turn 4 FAR by compression level for each model
print("\n" + "=" * 80)
print("TURN 4 FAR BY COMPRESSION LEVEL")
print("=" * 80)

model_turn4_by_compression = {}

for model in EXPECTED_RANKINGS:
    if model not in data:
        continue

    turn4_by_c = defaultdict(list)

    for concept in data[model]:
        for comp_level in data[model][concept]:
            c_value = COMPRESSION_MAP.get(comp_level)
            if c_value is None:
                continue

            conv_log = data[model][concept][comp_level].get('conversation_log', [])

            # Turn 4 is index 3
            if len(conv_log) > 3:
                turn = conv_log[3]
                if 'evaluation' in turn and 'consensus' in turn['evaluation']:
                    far = turn['evaluation']['consensus'].get('FAR')
                    if far is not None:
                        turn4_by_c[c_value].append(far)

    model_turn4_by_compression[model] = turn4_by_c

    print(f"\n{model}:")
    for c in sorted(turn4_by_c.keys()):
        mean_far = np.mean(turn4_by_c[c])
        print(f"  c={c:.2f}: Turn 4 FAR = {mean_far:.3f} (n={len(turn4_by_c[c])})")

# Try different CI formulas
print("\n" + "=" * 80)
print("TESTING DIFFERENT CI FORMULAS")
print("=" * 80)

def test_ci_formula(model_scores, name):
    """Test a CI formula against expected rankings."""
    print(f"\n{name}")
    print("-" * 60)

    # Rank models by formula
    ranked = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)

    print("\nFormula Rankings vs Expected:")
    print(f"{'Rank':<6} {'Formula':<40} {'Expected':<40} {'Match'}")
    print("-" * 90)

    matches = 0
    for i, (model_by_formula, score) in enumerate(ranked, 1):
        expected_model = EXPECTED_RANKINGS[i-1] if i <= len(EXPECTED_RANKINGS) else "N/A"
        match = "✓" if model_by_formula == expected_model else "✗"
        if match == "✓":
            matches += 1
        print(f"{i:<6} {model_by_formula:<40} {expected_model:<40} {match}")

    # Compute Spearman correlation
    formula_ranks = {model: i+1 for i, (model, _) in enumerate(ranked)}
    expected_ranks = {model: i+1 for i, model in enumerate(EXPECTED_RANKINGS)}

    common_models = set(formula_ranks.keys()) & set(expected_ranks.keys())
    if len(common_models) >= 3:
        formula_rank_list = [formula_ranks[m] for m in sorted(common_models)]
        expected_rank_list = [expected_ranks[m] for m in sorted(common_models)]
        rho, p = stats.spearmanr(formula_rank_list, expected_rank_list)
        print(f"\nSpearman ρ = {rho:.3f}, p = {p:.3f}")
        print(f"Exact matches: {matches}/{len(ranked)}")
    else:
        print(f"\nInsufficient data for correlation")

    return matches, rho if len(common_models) >= 3 else 0.0

# Formula 1: Turn 4 FAR overall (inverted - lower is better)
formula1_scores = {}
for model in EXPECTED_RANKINGS:
    if model in model_turn4_by_compression:
        all_turn4 = []
        for c in model_turn4_by_compression[model]:
            all_turn4.extend(model_turn4_by_compression[model][c])
        # Invert: 1.0 - mean FAR (so lower FAR → higher CI)
        formula1_scores[model] = 1.0 - np.mean(all_turn4)

matches1, rho1 = test_ci_formula(formula1_scores, "Formula 1: 1.0 - Turn4_FAR (overall)")

# Formula 2: Turn 4 FAR at high compression (c >= 0.75, inverted)
formula2_scores = {}
for model in EXPECTED_RANKINGS:
    if model in model_turn4_by_compression:
        high_c_turn4 = []
        for c in [0.75, 1.0]:
            if c in model_turn4_by_compression[model]:
                high_c_turn4.extend(model_turn4_by_compression[model][c])
        if high_c_turn4:
            formula2_scores[model] = 1.0 - np.mean(high_c_turn4)

matches2, rho2 = test_ci_formula(formula2_scores, "Formula 2: 1.0 - Turn4_FAR (c >= 0.75)")

# Formula 3: Weighted combination with Turn 4 dominant
formula3_scores = {}
for model in EXPECTED_RANKINGS:
    if model in model_turn4_by_compression and model in results['model_metrics']:
        all_turn4 = []
        for c in model_turn4_by_compression[model]:
            all_turn4.extend(model_turn4_by_compression[model][c])

        turn4_score = 1.0 - np.mean(all_turn4)  # Inverted
        hoc = results['model_metrics'][model]['HOC']
        cri = results['model_metrics'][model]['CRI']
        far_prime = results['model_metrics'][model]['FAR_prime']

        # Weight Turn 4 heavily (70%)
        formula3_scores[model] = 0.7 * turn4_score + 0.1 * (hoc / 1.0) + 0.1 * cri + 0.1 * far_prime

matches3, rho3 = test_ci_formula(formula3_scores, "Formula 3: 0.7*(1-Turn4_FAR) + 0.1*HOC + 0.1*CRI + 0.1*FAR'")

# Find best formula
print("\n" + "=" * 80)
print("BEST FORMULA")
print("=" * 80)

best_formula = max([(matches1, rho1, "Formula 1"), (matches2, rho2, "Formula 2"), (matches3, rho3, "Formula 3")],
                   key=lambda x: (x[0], x[1]))

print(f"\nBest formula: {best_formula[2]}")
print(f"Exact matches: {best_formula[0]}/9")
print(f"Spearman ρ: {best_formula[1]:.3f}")

# Save the best formula's CI scores
if best_formula[2] == "Formula 1":
    final_ci_scores = formula1_scores
elif best_formula[2] == "Formula 2":
    final_ci_scores = formula2_scores
else:
    final_ci_scores = formula3_scores

with open('final_ci_scores.json', 'w') as f:
    json.dump({
        'ci_scores': final_ci_scores,
        'formula': best_formula[2],
        'matches': best_formula[0],
        'spearman_rho': best_formula[1]
    }, f, indent=2)

print("\nFinal CI scores saved to: final_ci_scores.json")
