
import json
import glob
import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.signal import find_peaks
import os
import pandas as pd

def analyze_curve_shape(c_values, scores):
    """Analyzes the shape of a performance curve using its spline fit."""
    
    # 1. Fit the Spline and create a smooth curve for analysis
    # Ensure we have enough points for a spline
    if len(c_values) < 4:
        return None, None, None, "flat", None, None

    try:
        spline = UnivariateSpline(c_values, scores, s=len(scores) * np.var(scores) * 0.1)
        c_smooth = np.linspace(c_values.min(), c_values.max(), 500)
        scores_smooth = spline(c_smooth)
    except Exception:
        return None, None, None, "error", None, None

    # 2. Find Extrema (peaks and valleys)
    peak_indices, _ = find_peaks(scores_smooth)
    valley_indices, _ = find_peaks(-scores_smooth)

    # 3. Classify Profile Type (Lenient Definition)
    # If performance is nearly flat, classify as such
    if np.std(scores_smooth) < 0.05:
        profile_type = "flat"
    elif len(valley_indices) > 0:
        profile_type = "multi-modal"
    else:
        profile_type = "unimodal"

    # 4. Calculate c_peak and score_at_c_peak
    overall_peak_index = np.argmax(scores_smooth)
    c_peak = c_smooth[overall_peak_index]
    score_at_peak = scores_smooth[overall_peak_index]

    # 5. Calculate c_valley
    c_valley = None
    if len(valley_indices) > 0:
        # Find the deepest valley that occurs before the absolute peak
        pre_peak_valleys = [v_idx for v_idx in valley_indices if c_smooth[v_idx] < c_peak]
        if pre_peak_valleys:
            deepest_valley_idx = pre_peak_valleys[np.argmin(scores_smooth[pre_peak_valleys])]
            c_valley = c_smooth[deepest_valley_idx]

    # 6. Calculate Extreme C Resilience
    score_at_c_zero = scores_smooth[0]
    if score_at_peak > 1e-6: # Avoid division by zero
        extreme_c_resilience = score_at_c_zero / score_at_peak
    else:
        extreme_c_resilience = np.nan

    return profile_type, c_peak, c_valley, extreme_c_resilience, peak_indices, valley_indices

def main():
    """Main function to run analysis and print summaries."""
    
    # --- Configurations ---
    RESULTS_PATH = "/home/rahul/arXiv/CDCT/cdct_framework/results"
    
    ARCHITECTURES = {
        "gpt-5-mini": "Reasoning",
        "grok-4-fast-reasoning": "Reasoning",
        "Phi-4-mini-instruct": "Reasoning",
        "DeepSeek-V3-0324": "Scaling-Optimized",
        "gpt-4.1": "Scaling-Optimized",
        "mistral-medium-2505": "Scaling-Optimized",
        "gpt-oss-120b": "PatternMatching"
    }

    all_results = []
    result_files = glob.glob(os.path.join(RESULTS_PATH, "*.json"))

    for filepath in result_files:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        model_name = data.get("model")
        domain_name = data.get("domain")
        architecture = ARCHITECTURES.get(model_name, "Unknown")
        
        performance_data = sorted(data.get("performance", []), key=lambda p: p.get("context_length", 0))
        scores = np.array([p.get("score", 0) for p in performance_data])
        context_lengths = np.array([p.get("context_length", 0) for p in performance_data])
        max_context = np.max(context_lengths)
        
        if max_context == 0: continue
        c_values = context_lengths / max_context

        profile, c_peak, c_valley, resilience, _, _ = analyze_curve_shape(c_values, scores)

        all_results.append({
            "model": model_name,
            "architecture": architecture,
            "domain": domain_name,
            "profile_type": profile,
            "c_peak": c_peak,
            "c_valley": c_valley,
            "resilience": resilience
        })

    # --- Display Results ---
    df = pd.DataFrame(all_results)
    df = df.sort_values(by=["architecture", "model", "domain"]).reset_index(drop=True)

    print("--- Detailed Curve Shape Analysis ---")
    with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 200):
        print(df)

    print("\n" + "="*80)
    print("--- Aggregated Analysis by Architecture ---")
    
    # Aggregate profile types
    profile_counts = df.groupby('architecture')['profile_type'].value_counts(normalize=True).unstack(fill_value=0)
    profile_counts = profile_counts.reindex(columns=['unimodal', 'multi-modal', 'flat', 'error']).fillna(0)
    profile_counts['total_experiments'] = df.groupby('architecture').size()

    print("\n--- Profile Type Distribution (% of experiments) ---")
    print(profile_counts.to_string(formatters={
        'unimodal': '{:,.1%}'.format,
        'multi-modal': '{:,.1%}'.format,
        'flat': '{:,.1%}'.format,
        'error': '{:,.1%}'.format
    }))

    # Aggregate resilience
    resilience_agg = df.groupby('architecture')['resilience'].agg(['mean', 'std', 'min', 'max'])
    print("\n--- Extreme C Resilience (score @ c=0 / score @ peak) ---")
    print(resilience_agg.to_string(formatters={
        'mean': '{:,.3f}'.format,
        'std': '{:,.3f}'.format,
        'min': '{:,.3f}'.format,
        'max': '{:,.3f}'.format
    }))
    print("="*80)

if __name__ == "__main__":
    main()
