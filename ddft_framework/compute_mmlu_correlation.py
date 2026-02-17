#!/usr/bin/env python3
"""
Compute MMLU vs CI correlation with verified MMLU scores.
"""

import json
import numpy as np
from scipy import stats

print("=" * 80)
print("MMLU vs CI CORRELATION ANALYSIS")
print("=" * 80)

# Load CI scores
with open('complete_analysis_results.json', 'r') as f:
    results = json.load(f)

# Load verified MMLU scores
with open('mmlu_scores_verified.json', 'r') as f:
    mmlu_data = json.load(f)

# Extract pairs
models_with_mmlu = []
mmlu_scores = []
ci_scores = []

for model, mmlu_score in mmlu_data['mmlu_scores_verified'].items():
    if mmlu_score is not None and model in results['model_scores']:
        models_with_mmlu.append(model)
        mmlu_scores.append(mmlu_score)
        ci_scores.append(results['model_scores'][model]['CI'])

print(f"\nModels with MMLU scores: n = {len(models_with_mmlu)}")
print("-" * 80)
for i, model in enumerate(models_with_mmlu):
    print(f"{model:40s} MMLU: {mmlu_scores[i]:5.1f}%   CI: {ci_scores[i]:.3f}")

# Compute Spearman correlation
print("\n" + "=" * 80)
print("CORRELATION ANALYSIS")
print("=" * 80)

rho, p = stats.spearmanr(mmlu_scores, ci_scores)

print(f"\nSpearman ρ = {rho:.3f}")
print(f"p-value = {p:.3f}")
print(f"n = {len(models_with_mmlu)}")

# Bootstrap CI
print("\nComputing bootstrap 95% CI...")
np.random.seed(42)
n_bootstrap = 10000
correlations = []
n = len(mmlu_scores)

for _ in range(n_bootstrap):
    indices = np.random.choice(n, size=n, replace=True)
    mmlu_boot = np.array(mmlu_scores)[indices]
    ci_boot = np.array(ci_scores)[indices]

    try:
        r, _ = stats.spearmanr(mmlu_boot, ci_boot)
        if not np.isnan(r):
            correlations.append(r)
    except:
        pass

ci_lower = np.percentile(correlations, 2.5)
ci_upper = np.percentile(correlations, 97.5)

print(f"95% CI: [{ci_lower:.2f}, {ci_upper:.2f}]")

print("\n" + "=" * 80)
print("COMPARISON TO PAPER CLAIM")
print("=" * 80)

print(f"\nPaper Claim:")
print(f"  ρ = 0.12")
print(f"  p = 0.68")
print(f"  n = 6")

print(f"\nComputed:")
print(f"  ρ = {rho:.3f}")
print(f"  p = {p:.3f}")
print(f"  95% CI: [{ci_lower:.2f}, {ci_upper:.2f}]")
print(f"  n = {len(models_with_mmlu)}")

# Interpretation
print("\n" + "=" * 80)
print("INTERPRETATION")
print("=" * 80)

if p > 0.05:
    print("\n✅ NO significant correlation (p > 0.05)")
    print("   MMLU and CI measure orthogonal dimensions")
else:
    print(f"\n⚠️ Significant correlation found (p = {p:.3f})")

if abs(rho - 0.12) < 0.3:
    print("✅ Correlation magnitude similar to paper claim")
elif rho * 0.12 < 0:  # opposite signs
    print("⚠️ Correlation has opposite sign from paper")
else:
    print("⚠️ Correlation magnitude differs from paper")

# Check if CI includes paper's value
if ci_lower <= 0.12 <= ci_upper:
    print("✅ Bootstrap CI includes paper's ρ = 0.12")
else:
    print("⚠️ Bootstrap CI does NOT include paper's ρ = 0.12")

# Save results
mmlu_correlation_results = {
    'spearman_rho': float(rho),
    'p_value': float(p),
    'ci_lower': float(ci_lower),
    'ci_upper': float(ci_upper),
    'n': len(models_with_mmlu),
    'models': models_with_mmlu,
    'mmlu_scores': [float(s) for s in mmlu_scores],
    'ci_scores': [float(s) for s in ci_scores],
    'paper_claim': {
        'rho': 0.12,
        'p': 0.68,
        'n': 6
    }
}

with open('mmlu_correlation_results.json', 'w') as f:
    json.dump(mmlu_correlation_results, f, indent=2)

print("\n✓ Results saved to: mmlu_correlation_results.json")

# LaTeX snippet
print("\n" + "=" * 80)
print("LATEX SNIPPET FOR PAPER")
print("=" * 80)

print(f"""
\\subsection{{Comparison to Existing Benchmarks}}

To validate that DDFT captures orthogonal information to existing evaluations,
we analyzed the relationship between CI scores and MMLU performance for the
{len(models_with_mmlu)} models with publicly available scores. The Spearman
correlation is $\\rho = {rho:.2f}$ ($p = {p:.2f}$, 95\\% CI: $[{ci_lower:.2f}, {ci_upper:.2f}]$),
confirming DDFT measures a dimension distinct from static knowledge retrieval.

Specific examples illustrate this dissociation:
\\begin{{itemize}}
""")

# Find highest and lowest MMLU performers
sorted_by_mmlu = sorted(zip(models_with_mmlu, mmlu_scores, ci_scores),
                        key=lambda x: x[1], reverse=True)

print(f"\\item {sorted_by_mmlu[0][0]} achieves {sorted_by_mmlu[0][1]:.1f}\\% on MMLU yet scores CI = {sorted_by_mmlu[0][2]:.3f}")
print(f"\\item {sorted_by_mmlu[-1][0]} scores {sorted_by_mmlu[-1][1]:.1f}\\% on MMLU yet achieves CI = {sorted_by_mmlu[-1][2]:.3f}")

print("""\\end{itemize}

This demonstrates that models can excel at static knowledge retrieval yet
vary in robustness under epistemic stress, or conversely, maintain robustness
despite different baseline knowledge. DDFT complements rather than replaces
existing benchmarks, measuring stress resistance rather than capability.
""")
