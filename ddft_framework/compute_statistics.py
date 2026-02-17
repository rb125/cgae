#!/usr/bin/env python3
"""
DDFT Statistical Analysis Script
Computes all statistics for the DDFT paper from 360 experimental JSON files.
"""

import json
import glob
import numpy as np
from scipy import stats
from collections import defaultdict
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

COMPRESSION_MAP = {
    'c00': 0.0,
    'c025': 0.25,
    'c05': 0.5,
    'c075': 0.75,
    'c10': 1.0
}

CONCEPT_FULL_NAMES = {
    'derivative': 'Derivative',
    'impressionism': 'Impressionism',
    'ma': "Newton's 2nd Law",
    'phoneme': 'Phoneme',
    'ponens': 'Modus Ponens',
    'principle': 'Harm Principle',
    'recursion': 'Recursion',
    'selection': 'Natural Selection'
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

# ============================================================================
# STEP 1: LOAD ALL DATA
# ============================================================================

def load_all_data(results_dir='results'):
    """Load all 360 JSON files and organize by model/concept/compression."""
    print("=" * 80)
    print("STEP 1: LOADING DATA")
    print("=" * 80)

    data = defaultdict(lambda: defaultdict(dict))
    files = glob.glob(f'{results_dir}/ddft_*.json')

    print(f"\nFound {len(files)} JSON files")

    for filepath in files:
        filename = Path(filepath).stem  # Remove .json
        parts = filename.split('_')

        # Parse filename: ddft_{model}_{concept}_{compression}
        if len(parts) < 4:
            print(f"Warning: Skipping malformed filename: {filename}")
            continue

        model = parts[1]
        concept = parts[2]
        compression = parts[3]

        try:
            with open(filepath, 'r') as f:
                data[model][concept][compression] = json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")

    # Validate data coverage
    print(f"\nData coverage:")
    for model in MODELS:
        if model in data:
            n_concepts = len(data[model])
            total_files = sum(len(data[model][c]) for c in data[model])
            print(f"  {model}: {n_concepts} concepts, {total_files} files")
        else:
            print(f"  {model}: MISSING")

    return data

# ============================================================================
# STEP 2: EXTRACT METRICS BY MODEL
# ============================================================================

def extract_model_metrics(data):
    """Extract FAR and SAS scores organized by compression level and turn."""
    print("\n" + "=" * 80)
    print("STEP 2: EXTRACTING METRICS")
    print("=" * 80)

    model_data = {}

    for model in MODELS:
        if model not in data:
            print(f"\nWarning: No data for {model}")
            continue

        far_by_compression = defaultdict(list)
        sas_by_compression = defaultdict(list)
        far_by_turn = defaultdict(list)
        sas_by_turn = defaultdict(list)

        # Also track by concept for concept difficulty
        far_by_concept = defaultdict(lambda: defaultdict(list))

        n_evaluations = 0

        for concept in data[model]:
            for comp_level in data[model][concept]:
                c_value = COMPRESSION_MAP.get(comp_level)
                if c_value is None:
                    continue

                conv_log = data[model][concept][comp_level].get('conversation_log', [])

                for turn_idx, turn in enumerate(conv_log):
                    if 'evaluation' not in turn:
                        continue
                    if 'consensus' not in turn['evaluation']:
                        continue

                    cons = turn['evaluation']['consensus']
                    far = cons.get('FAR')
                    sas = cons.get('SAS')

                    if far is not None:
                        far_by_compression[c_value].append(far)
                        far_by_turn[turn_idx + 1].append(far)  # 1-indexed
                        far_by_concept[concept][c_value].append(far)
                        n_evaluations += 1

                    if sas is not None:
                        sas_by_compression[c_value].append(sas)
                        sas_by_turn[turn_idx + 1].append(sas)

        model_data[model] = {
            'far_by_c': dict(far_by_compression),
            'sas_by_c': dict(sas_by_compression),
            'far_by_turn': dict(far_by_turn),
            'sas_by_turn': dict(sas_by_turn),
            'far_by_concept': dict(far_by_concept),
            'n_evaluations': n_evaluations
        }

        print(f"\n{model}: {n_evaluations} evaluations")

    return model_data

# ============================================================================
# STEP 3: COMPUTE CI COMPONENTS
# ============================================================================

def compute_hoc(far_by_c, threshold=0.70):
    """
    Compute HOC: max compression where mean FAR >= threshold.
    Paper definition (corrected): Max c where mean FAR across all concepts/turns >= 0.70
    """
    for c in sorted([0.0, 0.25, 0.5, 0.75, 1.0], reverse=True):
        if c in far_by_c and len(far_by_c[c]) > 0:
            mean_far = np.mean(far_by_c[c])
            if mean_far >= threshold:
                return c
    return 0.0

def compute_cri(far_by_c):
    """
    Compute CRI: Compression Resistance Index (slope of FAR degradation).
    Negative slope means degradation, we return absolute value as "resistance".
    """
    c_levels = sorted([c for c in far_by_c if len(far_by_c[c]) > 0])
    if len(c_levels) < 2:
        return 0.0

    x = np.array(c_levels)
    y = np.array([np.mean(far_by_c[c]) for c in c_levels])

    if len(x) > 1:
        slope = np.polyfit(x, y, 1)[0]
        return abs(slope)  # Resistance = magnitude of degradation
    return 0.0

def compute_ci_score(model_metrics):
    """
    Compute CI score components.
    NOTE: We need to verify the exact formula from the paper.
    This is a placeholder that computes all components.
    """
    far_by_c = model_metrics['far_by_c']
    sas_by_c = model_metrics['sas_by_c']

    # HOC: Max compression where mean FAR >= 0.70
    hoc = compute_hoc(far_by_c)

    # CRI: Resistance to compression (slope magnitude)
    cri = compute_cri(far_by_c)

    # FAR' and SAS' at c=0.75
    far_prime = np.mean(far_by_c[0.75]) if 0.75 in far_by_c and len(far_by_c[0.75]) > 0 else 0.0
    sas_prime = np.mean(sas_by_c[0.75]) if 0.75 in sas_by_c and len(sas_by_c[0.75]) > 0 else 0.0

    # CI formula (need to verify exact weights from paper)
    # For now, use equal weighting as placeholder
    # TODO: Extract exact formula from paper Section 7
    ci = (hoc / 1.0) * 0.4 + (cri / 1.0) * 0.3 + far_prime * 0.2 + sas_prime * 0.1

    return {
        'CI': ci,
        'HOC': hoc,
        'CRI': cri,
        'FAR_prime': far_prime,
        'SAS_prime': sas_prime
    }

def compute_all_ci_scores(model_data):
    """Compute CI scores for all models."""
    print("\n" + "=" * 80)
    print("STEP 3: COMPUTING CI SCORES")
    print("=" * 80)

    model_metrics = {}
    for model in MODELS:
        if model not in model_data:
            continue

        metrics = compute_ci_score(model_data[model])
        model_metrics[model] = metrics

        print(f"\n{model}:")
        print(f"  CI Score: {metrics['CI']:.3f}")
        print(f"  HOC: {metrics['HOC']:.2f}")
        print(f"  CRI: {metrics['CRI']:.3f}")
        print(f"  FAR' (c=0.75): {metrics['FAR_prime']:.3f}")
        print(f"  SAS' (c=0.75): {metrics['SAS_prime']:.3f}")

    return model_metrics

# ============================================================================
# STEP 4: BOOTSTRAP CONFIDENCE INTERVALS
# ============================================================================

def bootstrap_correlation(x, y, n_bootstrap=10000, method='pearson', seed=42):
    """
    Compute bootstrap CI for correlation coefficient.

    Args:
        x, y: Arrays to correlate
        n_bootstrap: Number of bootstrap samples
        method: 'pearson' or 'spearman'
        seed: Random seed for reproducibility

    Returns:
        (ci_lower, ci_upper): 95% confidence interval
    """
    np.random.seed(seed)
    n = len(x)
    correlations = []

    for _ in range(n_bootstrap):
        # Resample with replacement
        indices = np.random.choice(n, size=n, replace=True)
        x_boot = np.array(x)[indices]
        y_boot = np.array(y)[indices]

        # Compute correlation
        try:
            if method == 'pearson':
                r, _ = stats.pearsonr(x_boot, y_boot)
            else:  # spearman
                r, _ = stats.spearmanr(x_boot, y_boot)
            correlations.append(r)
        except:
            # Handle edge cases (constant arrays, etc.)
            pass

    # Remove NaN values
    correlations = [c for c in correlations if not np.isnan(c)]

    if len(correlations) == 0:
        return (np.nan, np.nan)

    # Compute 95% CI (2.5th and 97.5th percentiles)
    ci_lower = np.percentile(correlations, 2.5)
    ci_upper = np.percentile(correlations, 97.5)

    return (ci_lower, ci_upper)

def compute_correlations_with_cis(model_metrics, model_params, arch_numeric):
    """Compute all correlations with bootstrap CIs."""
    print("\n" + "=" * 80)
    print("STEP 4: COMPUTING CORRELATIONS WITH BOOTSTRAP CIs")
    print("=" * 80)

    # Extract data
    models_sorted = sorted([m for m in MODELS if m in model_metrics])
    ci_scores = [model_metrics[m]['CI'] for m in models_sorted]
    param_counts = [model_params.get(m, np.nan) for m in models_sorted]
    arch_values = [arch_numeric.get(m, np.nan) for m in models_sorted]

    results = {}

    # 1. Parameter count vs CI
    valid_idx = [i for i, p in enumerate(param_counts) if not np.isnan(p)]
    if len(valid_idx) >= 3:
        param_valid = [param_counts[i] for i in valid_idx]
        ci_valid = [ci_scores[i] for i in valid_idx]

        r_param, p_param = stats.pearsonr(param_valid, ci_valid)
        ci_param = bootstrap_correlation(param_valid, ci_valid, method='pearson')

        results['parameter_count'] = {
            'r': r_param,
            'p': p_param,
            'ci_lower': ci_param[0],
            'ci_upper': ci_param[1],
            'n': len(param_valid)
        }

        print(f"\n1. Parameter Count vs CI:")
        print(f"   r = {r_param:.3f}, p = {p_param:.3f}")
        print(f"   95% CI: [{ci_param[0]:.2f}, {ci_param[1]:.2f}]")
        print(f"   n = {len(param_valid)}")

    # 2. Architecture vs CI
    valid_idx = [i for i, a in enumerate(arch_values) if not np.isnan(a)]
    if len(valid_idx) >= 3:
        arch_valid = [arch_values[i] for i in valid_idx]
        ci_valid = [ci_scores[i] for i in valid_idx]

        r_arch, p_arch = stats.pearsonr(arch_valid, ci_valid)
        ci_arch = bootstrap_correlation(arch_valid, ci_valid, method='pearson')

        results['architecture'] = {
            'r': r_arch,
            'p': p_arch,
            'ci_lower': ci_arch[0],
            'ci_upper': ci_arch[1],
            'n': len(arch_valid)
        }

        print(f"\n2. Architecture Type vs CI:")
        print(f"   r = {r_arch:.3f}, p = {p_arch:.3f}")
        print(f"   95% CI: [{ci_arch[0]:.2f}, {ci_arch[1]:.2f}]")
        print(f"   n = {len(arch_valid)}")

    return results

# ============================================================================
# STEP 5: CONCEPT DIFFICULTY
# ============================================================================

def compute_concept_difficulty(data):
    """Compute mean FAR at c=1.0 for each concept across all models."""
    print("\n" + "=" * 80)
    print("STEP 5: COMPUTING CONCEPT DIFFICULTY")
    print("=" * 80)

    concept_scores = {}

    for concept_abbr, concept_name in CONCEPT_FULL_NAMES.items():
        far_scores = []

        for model in MODELS:
            if model not in data:
                continue
            if concept_abbr not in data[model]:
                continue
            if 'c10' not in data[model][concept_abbr]:
                continue

            conv_log = data[model][concept_abbr]['c10'].get('conversation_log', [])
            for turn in conv_log:
                if 'evaluation' in turn and 'consensus' in turn['evaluation']:
                    far = turn['evaluation']['consensus'].get('FAR')
                    if far is not None:
                        far_scores.append(far)

        if far_scores:
            mean_far = np.mean(far_scores)
            # Classify difficulty
            if mean_far >= 0.7:
                difficulty = 'Easy'
            elif mean_far >= 0.4:
                difficulty = 'Medium'
            else:
                difficulty = 'Hard'

            concept_scores[concept_abbr] = {
                'name': concept_name,
                'mean_far': mean_far,
                'difficulty': difficulty,
                'n_scores': len(far_scores)
            }

            print(f"\n{concept_name}:")
            print(f"  Mean FAR (c=1.0): {mean_far:.3f}")
            print(f"  Difficulty: {difficulty}")
            print(f"  n = {len(far_scores)}")

    return concept_scores

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n" + "=" * 80)
    print("DDFT STATISTICAL ANALYSIS")
    print("=" * 80)

    # Load data
    data = load_all_data()

    # Extract metrics
    model_data = extract_model_metrics(data)

    # Compute CI scores
    # NOTE: We need model metadata (params, architecture) to proceed further
    print("\n" + "=" * 80)
    print("NEXT STEPS REQUIRED")
    print("=" * 80)
    print("\nTo complete the analysis, please provide:")
    print("1. Model parameter counts (in billions)")
    print("2. Architecture classifications (reasoning vs transformer vs mixture)")
    print("3. MMLU scores (optional, for correlation analysis)")
    print("\nOnce provided, we can compute:")
    print("- All bootstrap confidence intervals")
    print("- Model rankings")
    print("- Danger zone rates")

    # For now, compute CI scores with placeholder metadata
    model_metrics = compute_all_ci_scores(model_data)

    # Compute concept difficulty
    concept_scores = compute_concept_difficulty(data)

    # Save intermediate results
    output = {
        'model_metrics': {m: {k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                               for k, v in metrics.items()}
                          for m, metrics in model_metrics.items()},
        'concept_difficulty': {c: {k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                                    for k, v in scores.items()}
                               for c, scores in concept_scores.items()},
        'metadata': {
            'n_models': len(model_metrics),
            'n_concepts': len(concept_scores),
            'total_evaluations': sum(model_data[m]['n_evaluations'] for m in model_data)
        }
    }

    with open('intermediate_results.json', 'w') as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 80)
    print("INTERMEDIATE RESULTS SAVED")
    print("=" * 80)
    print("\nSaved to: intermediate_results.json")
    print("\nThis file contains:")
    print("- CI scores for all models")
    print("- Concept difficulty rankings")
    print("- Summary statistics")

    return data, model_data, model_metrics, concept_scores

if __name__ == '__main__':
    data, model_data, model_metrics, concept_scores = main()
