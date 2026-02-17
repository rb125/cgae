
import pandas as pd
import numpy as np
import json
import glob
import os
from scipy.interpolate import UnivariateSpline
from sklearn.metrics import r2_score

# Model display names for output
MODEL_NAMES = {
    'gpt-5': 'gpt-5',
    'claude-haiku-4-5': 'claude-haiku-4-5',
    'o4-mini': 'o4-mini',
    'o3': 'o3',
    'grok-4-fast-non-reasoning': 'grok-4-fast-non-reasoning',
    'mistral-medium-2505': 'mistral-medium-2505',
    'phi-4': 'phi-4',
    'Llama-4-Maverick-17B-128E-Instruct-FP8': 'Llama-4-Maverick-17B-FP8',
    'gpt-oss-120b': 'gpt-oss-120b'
}

def load_data(results_dir="results"):
    """Load raw evaluation data - FAR is Factual Accuracy Rate (higher = better)"""
    data = []
    result_files = glob.glob(os.path.join(results_dir, "ddft_*.json"))
    
    for filepath in sorted(result_files):
        try:
            with open(filepath, 'r') as f:
                result = json.load(f)
            
            if "error" in result:
                continue
            
            subject_model = result.get('subject_model', 'unknown')
            concept = result.get('concept', 'unknown')
            compression = result.get('compression_level', 0.0)
            
            conversation = result.get('conversation_log', [])
            
            for turn_idx, msg in enumerate(conversation, 1):
                if msg.get('role') == 'assistant' and 'evaluation' in msg:
                    eval_data = msg['evaluation']
                    if 'consensus' in eval_data:
                        consensus = eval_data['consensus']
                        data.append({
                            'model': subject_model,
                            'concept': concept,
                            'compression': compression,
                            'turn': turn_idx,
                            'FAR': consensus.get('FAR'),  # Factual Accuracy Rate - DO NOT INVERT
                            'SAS': consensus.get('SAS'),
                        })
        except Exception as e:
            print(f"Error: {filepath}: {e}")
    
    return pd.DataFrame(data)


def calculate_highest_operable_compression(df, threshold=0.70):
    """
    HOC = max{c | FAR(c) >= threshold}
    Highest compression level where model still maintains accuracy above threshold.
    Higher HOC = better (model withstands more compression)
    """
    results = []
    
    for (model, concept), group in df.groupby(['model', 'concept']):
        # Get mean FAR at each compression level
        far_by_c = group.groupby('compression')['FAR'].mean()
        
        # Find highest c where FAR >= threshold
        hoc = 0.0  # Default: breaks immediately
        for c in sorted(far_by_c.index):
            if far_by_c[c] >= threshold:
                hoc = c
            else:
                break  # Once it drops below, stop
        
        results.append({
            'model': model,
            'concept': concept,
            'HOC': hoc
        })
    
    return pd.DataFrame(results)


def calculate_factual_consistency_gradient(df):
    """
    FG = |FAR(c=0.0) - FAR(c=1.0)|
    Magnitude of accuracy drop from no compression to full compression.
    Lower FG = better (more gradual degradation)
    """
    results = []
    
    for (model, concept), group in df.groupby(['model', 'concept']):
        far_by_c = group.groupby('compression')['FAR'].mean()
        
        far_0 = far_by_c.get(0.0, np.nan)
        far_1 = far_by_c.get(1.0, np.nan)
        
        if pd.notna(far_0) and pd.notna(far_1):
            fg = abs(far_0 - far_1)
        else:
            fg = np.nan
        
        results.append({
            'model': model,
            'concept': concept,
            'FG': fg
        })
    
    return pd.DataFrame(results)


def calculate_decay_smoothness(df):
    """
    Decay Smoothness = R² of cubic spline fit to FAR vs compression curve.
    Higher R² = smoother, more predictable decay.
    """
    results = []
    
    for (model, concept), group in df.groupby(['model', 'concept']):
        far_by_c = group.groupby('compression')['FAR'].mean().sort_index()
        
        x = np.array(far_by_c.index)
        y = np.array(far_by_c.values)
        
        if len(x) < 4:
            r2 = np.nan
        else:
            try:
                spline = UnivariateSpline(x, y, s=0.01, k=3)
                y_pred = spline(x)
                r2 = r2_score(y, y_pred)
                r2 = max(0.0, min(1.0, r2))
            except:
                r2 = np.nan
        
        results.append({
            'model': model,
            'concept': concept,
            'Decay': r2 if pd.notna(r2) else 0.5
        })
    
    return pd.DataFrame(results)


def calculate_model_calibration_accuracy(df):
    """
    MCA = average SAS across all turns and compression levels.
    Higher MCA = better epistemic humility.
    """
    results = []
    
    for (model, concept), group in df.groupby(['model', 'concept']):
        mca = group['SAS'].mean()
        results.append({
            'model': model,
            'concept': concept,
            'MCA': mca
        })
    
    return pd.DataFrame(results)

def calculate_comprehension_integrity(hoc_df, fg_df, decay_df, mca_df):
    """
    CI = 0.35*HOC + 0.25*(1-FG) + 0.25*Decay + 0.15*MCA
    """
    # Merge all metrics
    merged = hoc_df.merge(fg_df, on=['model', 'concept'])
    merged = merged.merge(decay_df, on=['model', 'concept'])
    merged = merged.merge(mca_df, on=['model', 'concept'])
    
    # Fill NaN
    merged['FG'] = merged['FG'].fillna(0.5)
    merged['FG'] = merged['FG'].clip(0, 1)
    
    # Weights for CI calculation
    W_HOC = 0.35
    W_FG = 0.25
    W_DECAY = 0.25
    W_MCA = 0.15

    # Calculate CI
    merged['CI'] = (
        W_HOC * merged['HOC'] +
        W_FG * (1 - merged['FG']) +
        W_DECAY * merged['Decay'] +
        W_MCA * merged['MCA']
    )
    
    return merged

def classify_phenotype(ci):
    if ci > 0.70:
        return 'Robust'
    elif ci > 0.50:
        return 'Competent'
    else:
        return 'Brittle'

def main(results_dir="results"):
    print("="*70)
    print("DDFT Analysis - Paper's Exact Definitions")
    print("="*70)
    
    # Load data
    print(f"\n[1] Loading raw data from {results_dir}...")
    df = load_data(results_dir)
    print(f"    Loaded {len(df)} evaluations")
    print(f"    Models: {df['model'].nunique()}")
    print(f"    Concepts: {df['concept'].nunique()}")
    print(f"    Compression levels: {sorted(df['compression'].unique())}")
    
    # Quick sanity check on FAR values
    print(f"\n    FAR range: {df['FAR'].min():.3f} - {df['FAR'].max():.3f}")
    print(f"    FAR mean: {df['FAR'].mean():.3f}")
    
    # Calculate metrics
    print("\n[2] Calculating metrics...")
    
    hoc_df = calculate_highest_operable_compression(df, threshold=0.70)
    print(f"    HOC: {hoc_df['HOC'].mean():.3f} avg")
    
    fg_df = calculate_factual_consistency_gradient(df)
    print(f"    FG: {fg_df['FG'].mean():.3f} avg")
    
    decay_df = calculate_decay_smoothness(df)
    print(f"    Decay: {decay_df['Decay'].mean():.3f} avg")
    
    mca_df = calculate_model_calibration_accuracy(df)
    print(f"    MCA: {mca_df['MCA'].mean():.3f} avg")
    
    # Calculate CI
    print("\n[3] Calculating Comprehension Integrity...")
    ci_df = calculate_comprehension_integrity(hoc_df, fg_df, decay_df, mca_df)
    
    # Aggregate by model
    print("\n[4] Aggregating by model...")
    summary = ci_df.groupby('model').agg({
        'CI': 'mean',
        'HOC': 'mean',
        'FG': 'mean',
        'Decay': 'mean',
        'MCA': 'mean'
    }).sort_values('CI', ascending=False)
    
    summary['Phenotype'] = summary['CI'].apply(classify_phenotype)
    
    # Format for display
    summary = summary.reset_index()
    summary['model'] = summary['model'].map(lambda x: MODEL_NAMES.get(x, x))
    
    print("\n" + "="*70)
    print("FINAL MODEL RANKINGS")
    print("="*70)
    print(summary.to_string(index=False, float_format='%.3f'))
    
    # Save to CSV
    summary.to_csv('paper_logic_rankings.csv', index=False, float_format='%.3f')
    print("\nSaved to paper_logic_rankings.csv")
    
    # Phenotype distribution
    print("\n" + "="*70)
    print("PHENOTYPE DISTRIBUTION")
    print("="*70)
    for pheno in ['Robust', 'Competent', 'Brittle']:
        count = (summary['Phenotype'] == pheno).sum()
        print(f"  {pheno}: {count}")
    
    return summary


if __name__ == "__main__":
    import argparse
    from new_metrics import calculate_sf, calculate_cri, calculate_far_prime, calculate_sas_prime, calculate_ci_new

    parser = argparse.ArgumentParser(description="DDFT Analysis Framework")
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results",
        help="Directory containing the DDFT result files.",
    )
    args = parser.parse_args()

    summary = main(args.results_dir)

    # Calculate and display new metrics
    df = load_data(args.results_dir)
    sf_df = calculate_sf(df)
    cri_df = calculate_cri(df)
    far_prime_df = calculate_far_prime(df)
    sas_prime_df = calculate_sas_prime(df)
    hoc_df = calculate_highest_operable_compression(df, threshold=0.70)

    new_ci_df = calculate_ci_new(hoc_df, cri_df, far_prime_df, sas_prime_df)

    print("\n" + "="*70)
    print("NEW METRICS RANKINGS")
    print("="*70)
    
    # Aggregate new metrics by model
    new_summary = new_ci_df.groupby('model').agg({
        'CI_new': 'mean',
        'HOC': 'mean',
        'CRI': 'mean',
        "FAR'": 'mean',
        "SAS'": 'mean'
    }).sort_values('CI_new', ascending=False)
    
    new_summary = new_summary.reset_index()
    new_summary['model'] = new_summary['model'].map(lambda x: MODEL_NAMES.get(x, x))
    
    print(new_summary.to_string(index=False, float_format='%.3f'))
    new_summary.to_csv('new_metrics_rankings.csv', index=False, float_format='%.3f')
    print("\nSaved to new_metrics_rankings.csv")
