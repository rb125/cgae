#!/usr/bin/env python3
"""
Recompute architecture correlation with CORRECTED classifications.
"""

import json
import numpy as np
from scipy import stats

# Load previous results
with open('complete_analysis_results.json', 'r') as f:
    results = json.load(f)

# Load corrected architecture
with open('model_metadata_CORRECTED.json', 'r') as f:
    corrected = json.load(f)

print("=" * 80)
print("RECOMPUTING WITH CORRECTED ARCHITECTURE CLASSIFICATIONS")
print("=" * 80)

# Model CI scores (from previous analysis)
ci_scores = results['model_scores']

# Sort models
models = sorted(ci_scores.keys())
ci_values = [ci_scores[m]['CI'] for m in models]
reasoning_corrected = [corrected['reasoning_binary_CORRECTED'][m] for m in models]

print("\nCorrected Classifications:")
print("-" * 60)
for model in models:
    old_class = "Reasoning" if model in ['o4-mini', 'o3', 'gpt-5', 'claude-haiku-4-5'] else "Non-Reasoning"
    new_class = "Reasoning" if reasoning_corrected[models.index(model)] == 1 else "Non-Reasoning"
    change = " ← CHANGED" if old_class != new_class else ""
    print(f"{model:40s} {new_class:15s} (CI={ci_scores[model]['CI']:.3f}){change}")

# Compute correlation
print("\n" + "=" * 80)
print("CORRECTED ARCHITECTURE CORRELATION")
print("=" * 80)

r_corrected, p_corrected = stats.pearsonr(reasoning_corrected, ci_values)

# Bootstrap CI
np.random.seed(42)
n_bootstrap = 10000
correlations = []
n = len(reasoning_corrected)

for _ in range(n_bootstrap):
    indices = np.random.choice(n, size=n, replace=True)
    x_boot = np.array(reasoning_corrected)[indices]
    y_boot = np.array(ci_values)[indices]

    try:
        r, _ = stats.pearsonr(x_boot, y_boot)
        if not np.isnan(r):
            correlations.append(r)
    except:
        pass

ci_lower = np.percentile(correlations, 2.5)
ci_upper = np.percentile(correlations, 97.5)

print(f"\nCORRECTED Results:")
print(f"  r = {r_corrected:.3f}")
print(f"  p = {p_corrected:.3f}")
print(f"  95% CI: [{ci_lower:.2f}, {ci_upper:.2f}]")
print(f"  n = {len(models)}")

print(f"\nPrevious (INCORRECT) Results:")
print(f"  r = -0.782")
print(f"  p = 0.013")
print(f"  95% CI: [-0.98, -0.40]")

print(f"\nPaper Claim:")
print(f"  r = 0.153")
print(f"  p = 0.695")

print("\n" + "=" * 80)
print("INTERPRETATION")
print("=" * 80)

if abs(r_corrected - 0.153) < 0.3:
    print("\n✅ CORRECTED classification MATCHES paper claim!")
    print("   Both show weak/no correlation between reasoning-alignment and CI")
elif p_corrected > 0.05:
    print("\n✅ CORRECTED classification shows NO significant correlation")
    print("   Consistent with paper's finding (p > 0.05)")
else:
    print("\n⚠️ CORRECTED classification still differs from paper")
    print("   May indicate remaining classification issues or paper error")

# Analyze by phenotype
print("\n" + "=" * 80)
print("CI SCORES BY ARCHITECTURE TYPE")
print("=" * 80)

reasoning_ci = [ci_values[i] for i, r in enumerate(reasoning_corrected) if r == 1]
nonreasoning_ci = [ci_values[i] for i, r in enumerate(reasoning_corrected) if r == 0]

print(f"\nReasoning models (n={len(reasoning_ci)}):")
print(f"  Mean CI: {np.mean(reasoning_ci):.3f}")
print(f"  Std CI:  {np.std(reasoning_ci):.3f}")
print(f"  Range:   [{min(reasoning_ci):.3f}, {max(reasoning_ci):.3f}]")

print(f"\nNon-reasoning models (n={len(nonreasoning_ci)}):")
print(f"  Mean CI: {np.mean(nonreasoning_ci):.3f}")
print(f"  Std CI:  {np.std(nonreasoning_ci):.3f}")
print(f"  Range:   [{min(nonreasoning_ci):.3f}, {max(nonreasoning_ci):.3f}]")

# T-test
from scipy.stats import ttest_ind
t_stat, t_p = ttest_ind(reasoning_ci, nonreasoning_ci)
print(f"\nIndependent t-test:")
print(f"  t = {t_stat:.3f}, p = {t_p:.3f}")

# Save corrected results
corrected_results = {
    'architecture_corrected': {
        'r': float(r_corrected),
        'p': float(p_corrected),
        'ci_lower': float(ci_lower),
        'ci_upper': float(ci_upper),
        'n': len(models)
    },
    'reasoning_mean_ci': float(np.mean(reasoning_ci)),
    'nonreasoning_mean_ci': float(np.mean(nonreasoning_ci)),
    't_test': {
        't': float(t_stat),
        'p': float(t_p)
    },
    'changes': corrected['changes_from_original']
}

with open('corrected_architecture_results.json', 'w') as f:
    json.dump(corrected_results, f, indent=2)

print("\n✓ Saved corrected results to: corrected_architecture_results.json")
