
import json
import glob
import numpy as np
from scipy.interpolate import UnivariateSpline
import matplotlib.pyplot as plt
import os

def get_performance_data(filepath):
    """Extracts and normalizes performance data from a result file."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None, None

    performance_data = data.get("performance", [])
    if not performance_data:
        return None, None

    performance_data.sort(key=lambda p: p.get("context_length", 0))

    scores = np.array([p.get("score", 0) for p in performance_data])
    context_lengths = np.array([p.get("context_length", 0) for p in performance_data])

    max_context = np.max(context_lengths)
    if max_context == 0:
        return None, None
    
    c_values = context_lengths / max_context
    return c_values, scores

def main():
    """Generates and saves a plot of performance curves for specified models and domain."""
    results_path = "/home/rahul/arXiv/CDCT/cdct_framework/results"
    output_filename = "/home/rahul/arXiv/CDCT/cdct_framework/pattern_matching_ethics_curve.png"
    
    # --- Configuration ---
    domain_to_plot = "ethics_harm_principle"
    models_to_plot = {
        "gpt-oss-120b": "GPT-OSS-120B"
    }
    
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))

    for model_id, model_name in models_to_plot.items():
        # Construct the filename pattern
        # Example: results_ethics_harm_principle_gpt-5-mini_compression_aware_lenient.json
        filename = f"results_{domain_to_plot}_{model_id}_compression_aware_lenient.json"
        filepath = os.path.join(results_path, filename)

        c_values, scores = get_performance_data(filepath)

        if c_values is None or scores is None:
            print(f"Could not load or process data for {model_name}. Skipping.")
            continue

        # Plot raw data points
        ax.scatter(c_values, scores, label=f"{model_name} (Raw Data)", alpha=0.6)

        # Fit and plot spline curve
        try:
            spline = UnivariateSpline(c_values, scores, s=len(scores)*np.var(scores)*0.1)
            c_smooth = np.linspace(c_values.min(), c_values.max(), 300)
            scores_smooth = spline(c_smooth)
            ax.plot(c_smooth, scores_smooth, label=f"{model_name} (Spline Fit)")
        except Exception as e:
            print(f"Could not fit spline for {model_name}: {e}")

    # --- Formatting ---
    ax.set_title("Performance on 'Ethics' for Pattern-Matching Model", fontsize=18, pad=20)
    ax.set_xlabel("Compression Level (c) [0=Keyword, 1=Full Text]", fontsize=12)
    ax.set_ylabel("Performance Score", fontsize=12)
    ax.legend(fontsize=10)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlim(-0.05, 1.05)
    fig.tight_layout()

    # --- Save Plot ---
    try:
        plt.savefig(output_filename, dpi=300)
        print(f"Plot saved successfully to {output_filename}")
    except Exception as e:
        print(f"Failed to save plot: {e}")

if __name__ == "__main__":
    main()
