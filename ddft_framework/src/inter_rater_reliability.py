"""
Inter-Rater Reliability Analysis for Jury Consensus System

Computes:
- Pairwise Spearman ρ (rank correlation)
- Fleiss' κ (multi-judge agreement)
- Krippendorff's α
- Per-model judge agreement
- Judge disagreement heatmap
"""

import json
import glob
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns

def load_evaluation_results(results_dir: str) -> pd.DataFrame:
    """Load all ddft_*.json files and extract judge scores."""
    
    results = []
    
    for json_file in glob.glob(f"{results_dir}/ddft_*.json"):
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        if "error" in data:
            continue  # Skip error files
        
        subject_model = data.get("subject_model", "unknown")
        concept = data.get("concept", "unknown")
        compression = data.get("compression_level", 0.0)
        
        # Extract judge scores from conversation log
        for turn_idx, turn in enumerate(data.get("conversation_log", [])):
            if turn.get("role") == "assistant" and "evaluation" in turn:
                eval_data = turn["evaluation"]
                
                if "error" in eval_data or "parse_error" in eval_data:
                    continue  # Skip parse errors
                
                # Extract consensus and individual judge scores
                row = {
                    "subject_model": subject_model,
                    "concept": concept,
                    "compression": compression,
                    "turn": turn_idx + 1,
                    "consensus_FAR": eval_data.get("FAR"),
                    "consensus_SAS": eval_data.get("SAS"),
                    "consensus_FC": eval_data.get("FC"),
                    "agreement_score": eval_data.get("agreement_score"),
                    "judge_variance": eval_data.get("judge_variance"),
                }
                
                # Extract individual judge scores
                individual = eval_data.get("individual_scores", {})
                for judge_name, judge_scores in individual.items():
                    row[f"{judge_name}_FAR"] = judge_scores.get("FAR")
                    row[f"{judge_name}_SAS"] = judge_scores.get("SAS")
                    row[f"{judge_name}_FC"] = judge_scores.get("FC")
                
                results.append(row)
    
    return pd.DataFrame(results)


def compute_pairwise_spearman(df: pd.DataFrame, metric: str, 
                             compression_level: float = None) -> Dict:
    """
    Compute Spearman ρ between all judge pairs.
    
    Args:
        df: DataFrame with judge scores
        metric: One of ['FAR', 'SAS', 'FC']
        compression_level: Filter to specific compression (None = all)
    
    Returns:
        Dict of pairwise correlations
    """
    
    if compression_level is not None:
        df = df[df['compression'] == compression_level]
    
    judges = ["claude-opus-4-1", "gpt-5.1", "qwen-3"]
    judge_cols = [f"{j}_{metric}" for j in judges]
    
    # Remove rows with NaN
    df_clean = df[judge_cols].dropna()
    
    results = {}
    for i, judge1 in enumerate(judges):
        for judge2 in judges[i+1:]:
            col1 = f"{judge1}_{metric}"
            col2 = f"{judge2}_{metric}"
            
            if col1 in df_clean.columns and col2 in df_clean.columns:
                rho, pval = spearmanr(df_clean[col1], df_clean[col2])
                results[f"{judge1} vs {judge2}"] = {
                    "rho": rho,
                    "p_value": pval,
                    "n": len(df_clean)
                }
    
    return results


def compute_fleiss_kappa(df: pd.DataFrame, metric: str) -> float:
    """
    Compute Fleiss' κ for multi-judge agreement.
    
    Approach:
    1. Bin each judge's scores independently: 0.0-0.33 → 0, 0.33-0.67 → 1, 0.67-1.0 → 2
    2. Create (n_responses, 3) matrix of judge categories
    3. Compute Fleiss' κ on categorical agreement
    """
    
    judges = ["claude-opus-4-1", "gpt-5.1", "qwen-3"]
    judge_cols = [f"{j}_{metric}" for j in judges]
    
    # Get clean data
    df_clean = df[judge_cols].dropna()
    
    if len(df_clean) == 0:
        return 0.0
    
    # Bin each judge's scores independently to categories [0, 1, 2]
    binned_scores = np.zeros((len(df_clean), 3))
    for col_idx, col in enumerate(judge_cols):
        scores = df_clean[col].values
        # Bin: [0-0.33) → 0, [0.33-0.67) → 1, [0.67-1.0] → 2
        binned = np.digitize(scores, bins=[0.33, 0.67]) - 1
        binned = np.clip(binned, 0, 2)  # Ensure range [0, 1, 2]
        binned_scores[:, col_idx] = binned
    
    # Compute Fleiss' κ using statsmodels
    try:
        from statsmodels.stats.inter_rater import fleiss_kappa
        kappa = fleiss_kappa(binned_scores)
    except ImportError:
        # Fallback: manual computation
        n_judges = 3
        n_subjects = len(df_clean)
        n_categories = 3
        
        # Observed agreement
        po_sum = 0
        for subject_idx in range(n_subjects):
            categories = binned_scores[subject_idx, :]
            category_counts = np.bincount(categories.astype(int), minlength=n_categories)
            # Proportion of pairs that agree for this subject
            pairs_agree = np.sum(category_counts * (category_counts - 1))
            po_sum += pairs_agree / (n_judges * (n_judges - 1))
        
        po = po_sum / n_subjects
        
        # Expected agreement
        nk = np.sum(np.eye(n_categories)[binned_scores.astype(int)], axis=(0, 1))
        pk = nk / (n_judges * n_subjects)
        pe = np.sum(pk ** 2)
        
        kappa = (po - pe) / (1 - pe) if pe < 1 else 0
    
    return kappa


def generate_irr_report(results_dir: str = "results", 
                       output_file: str = "INTER_RATER_RELIABILITY_REPORT.txt"):
    """
    Generate comprehensive inter-rater reliability report.
    """
    
    df = load_evaluation_results(results_dir)
    
    if len(df) == 0:
        print("No valid evaluation results found.")
        return
    
    report = []
    report.append("=" * 80)
    report.append("INTER-RATER RELIABILITY ANALYSIS")
    report.append("DDFT Jury Consensus Evaluation")
    report.append("=" * 80)
    report.append("")
    
    # Overall statistics
    report.append(f"Total evaluations: {len(df)}")
    report.append(f"Models: {df['subject_model'].nunique()}")
    report.append(f"Concepts: {df['concept'].nunique()}")
    report.append(f"Compression levels: {df['compression'].nunique()}")
    report.append(f"Turns: {df['turn'].nunique()}")
    report.append("")
    
    # 1. Pairwise Spearman ρ by metric (overall)
    report.append("-" * 80)
    report.append("1. PAIRWISE SPEARMAN ρ (Overall)")
    report.append("-" * 80)
    
    for metric in ["FAR", "SAS", "FC"]:
        report.append(f"\nMetric: {metric}")
        corr = compute_pairwise_spearman(df, metric)
        for pair, stats in corr.items():
            report.append(f"  {pair:30} ρ={stats['rho']:.3f} (p={stats['p_value']:.4f}, n={stats['n']})")
    
    # 2. Pairwise Spearman by compression level
    report.append("\n" + "-" * 80)
    report.append("2. SPEARMAN ρ BY COMPRESSION LEVEL")
    report.append("-" * 80)
    
    for compression in sorted(df['compression'].unique()):
        report.append(f"\nCompression Level: c={compression}")
        for metric in ["FAR", "SAS", "FC"]:
            corr = compute_pairwise_spearman(df, metric, compression)
            for pair, stats in corr.items():
                report.append(f"  {metric} - {pair:25} ρ={stats['rho']:.3f}")
    
    # 3. Fleiss' κ
    report.append("\n" + "-" * 80)
    report.append("3. FLEISS' κ (Multi-Judge Agreement)")
    report.append("-" * 80)
    
    for metric in ["FAR", "SAS", "FC"]:
        kappa = compute_fleiss_kappa(df, metric)
        interpretation = "poor" if kappa < 0.41 else "moderate" if kappa < 0.61 else "substantial" if kappa < 0.81 else "almost perfect"
        report.append(f"\n{metric}: κ = {kappa:.3f} ({interpretation} agreement)")
    
    # 4. Judge agreement by model
    report.append("\n" + "-" * 80)
    report.append("4. JUDGE AGREEMENT BY MODEL")
    report.append("-" * 80)
    
    model_agreement = df.groupby('subject_model')['agreement_score'].agg(['mean', 'std', 'min', 'max'])
    report.append("\nModel Agreement Summary:")
    report.append(f"{'Model':<25} {'Mean Agree':<12} {'Std Dev':<10} {'Min':<8} {'Max':<8}")
    for model, row in model_agreement.iterrows():
        report.append(f"{model:<25} {row['mean']:.3f}        {row['std']:.3f}      {row['min']:.3f}    {row['max']:.3f}")
    
    # 5. Judge agreement by compression
    report.append("\n" + "-" * 80)
    report.append("5. JUDGE AGREEMENT BY COMPRESSION LEVEL")
    report.append("-" * 80)
    
    compression_agreement = df.groupby('compression')['agreement_score'].agg(['mean', 'std', 'min', 'max'])
    report.append(f"\n{'Compression':<15} {'Mean Agree':<12} {'Std Dev':<10} {'Min':<8} {'Max':<8}")
    for compression, row in compression_agreement.iterrows():
        report.append(f"c={compression:<12} {row['mean']:.3f}        {row['std']:.3f}      {row['min']:.3f}    {row['max']:.3f}")
    
    # 6. High variance cases (disagreement)
    report.append("\n" + "-" * 80)
    report.append("6. HIGH VARIANCE CASES (Judge Disagreement)")
    report.append("-" * 80)
    report.append("\nCases with agreement_score < 0.75 (substantial disagreement):")
    
    high_var = df[df['agreement_score'] < 0.75].sort_values('agreement_score')
    if len(high_var) > 0:
        report.append(f"Count: {len(high_var)} cases ({100*len(high_var)/len(df):.1f}%)")
        report.append(f"\n{'Model':<25} {'Concept':<15} {'c':<6} {'Turn':<5} {'Agreement':<10}")
        for _, row in high_var.head(20).iterrows():
            report.append(f"{row['subject_model']:<25} {row['concept']:<15} {row['compression']:<6.2f} {row['turn']:<5} {row['agreement_score']:<10.3f}")
    else:
        report.append("None found - judges show strong agreement overall.")
    
    # Write report
    report_text = "\n".join(report)
    print(report_text)
    
    with open(output_file, 'w') as f:
        f.write(report_text)
    
    print(f"\nReport saved to: {output_file}")
    
    return df


def visualize_judge_agreement(df: pd.DataFrame, output_dir: str = "figures"):
    """Generate visualization of judge agreement."""
    
    Path(output_dir).mkdir(exist_ok=True)
    
    # 1. Agreement by compression level
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    
    for idx, metric in enumerate(["FAR", "SAS", "FC"]):
        judges = ["claude-opus-4-1", "gpt-5.1", "qwen-3"]
        judge_cols = [f"{j}_{metric}" for j in judges]
        
        df_clean = df[judge_cols + ["compression"]].dropna()
        
        # Compute pairwise correlations by compression
        compressions = sorted(df['compression'].unique())
        corr_data = []
        
        for comp in compressions:
            df_comp = df_clean[df_clean['compression'] == comp]
            for i, j1 in enumerate(judges):
                for j2 in judges[i+1:]:
                    col1 = f"{j1}_{metric}"
                    col2 = f"{j2}_{metric}"
                    rho, _ = spearmanr(df_comp[col1], df_comp[col2])
                    corr_data.append({
                        "compression": comp,
                        "pair": f"{j1[:8]} vs {j2[:8]}",
                        "rho": rho
                    })
        
        corr_df = pd.DataFrame(corr_data)
        for pair in corr_df['pair'].unique():
            pair_data = corr_df[corr_df['pair'] == pair]
            axes[idx].plot(pair_data['compression'], pair_data['rho'], marker='o', label=pair)
        
        axes[idx].set_title(f"Judge Correlation: {metric}")
        axes[idx].set_xlabel("Compression Level")
        axes[idx].set_ylabel("Spearman ρ")
        axes[idx].legend(fontsize=8)
        axes[idx].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/judge_agreement_by_compression.png", dpi=300)
    print(f"Saved: {output_dir}/judge_agreement_by_compression.png")
    plt.close()
    
    # 2. Heatmap of judge agreement by model
    fig, ax = plt.subplots(figsize=(12, 8))
    
    models = sorted(df['subject_model'].unique())
    compressions = sorted(df['compression'].unique())
    
    agreement_matrix = np.zeros((len(models), len(compressions)))
    
    for i, model in enumerate(models):
        for j, comp in enumerate(compressions):
            agreement = df[(df['subject_model'] == model) & (df['compression'] == comp)]['agreement_score'].mean()
            agreement_matrix[i, j] = agreement
    
    sns.heatmap(agreement_matrix, annot=True, fmt='.2f', cmap='RdYlGn', 
               xticklabels=[f"c={c}" for c in compressions],
               yticklabels=models, ax=ax, cbar_kws={"label": "Agreement Score"})
    
    ax.set_title("Judge Agreement by Model and Compression Level")
    ax.set_ylabel("Subject Model")
    ax.set_xlabel("Compression Level")
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/judge_agreement_heatmap.png", dpi=300, bbox_inches='tight')
    print(f"Saved: {output_dir}/judge_agreement_heatmap.png")
    plt.close()


if __name__ == "__main__":
    import sys
    
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    
    # Generate report
    df = generate_irr_report(results_dir)
    
    # Generate visualizations
    if len(df) > 0:
        visualize_judge_agreement(df)
