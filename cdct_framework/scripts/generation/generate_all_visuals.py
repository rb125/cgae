
import json
import glob
import numpy as np
from scipy.interpolate import UnivariateSpline
import matplotlib.pyplot as plt
import os
import itertools

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

def generate_plot(domain_id, domain_name, models_to_plot, model_group_name, output_dir):
    """Generates and saves a single plot for a given configuration."""
    
    output_filename = os.path.join(output_dir, f"curves_{model_group_name.lower()}_{domain_id.split('_')[0]}.png")
    
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))
    
    found_data = False
    for model_id, model_name in models_to_plot.items():
        filename = f"results_{domain_id}_{model_id}_compression_aware_lenient.json"
        filepath = os.path.join("/home/rahul/arXiv/CDCT/cdct_framework/results", filename)

        c_values, scores = get_performance_data(filepath)

        if c_values is None or scores is None:
            continue
        
        found_data = True
        # Plot raw data points
        ax.scatter(c_values, scores, label=f"{model_name} (Raw Data)", alpha=0.6)

        # Fit and plot spline curve
        if len(c_values) > 3: # Spline needs at least 4 points
            try:
                spline = UnivariateSpline(c_values, scores, s=len(scores)*np.var(scores)*0.1)
                c_smooth = np.linspace(c_values.min(), c_values.max(), 300)
                scores_smooth = spline(c_smooth)
                ax.plot(c_smooth, scores_smooth, label=f"{model_name} (Spline Fit)")
            except Exception:
                # If spline fails, just plot the raw data connected
                ax.plot(c_values, scores, label=f"{model_name} (Line)", linestyle='--')
        else:
            ax.plot(c_values, scores, label=f"{model_name} (Line)", linestyle='--')


    if not found_data:
        plt.close(fig)
        return None

    # --- Formatting ---
    title = f"Performance on '{domain_name}' for {model_group_name} Models"
    ax.set_title(title, fontsize=18, pad=20)
    ax.set_xlabel("Compression Level (c) [0=Keyword, 1=Full Text]", fontsize=12)
    ax.set_ylabel("Performance Score", fontsize=12)
    ax.legend(fontsize=10)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlim(-0.05, 1.05)
    fig.tight_layout()

    # --- Save Plot ---
    try:
        plt.savefig(output_filename, dpi=300)
        plt.close(fig)
        return output_filename
    except Exception:
        plt.close(fig)
        return None

def main():
    """
    Main function to loop through configurations and generate all plots.
    """
    # --- Global Configurations ---
    OUTPUT_DIR = "/home/rahul/arXiv/CDCT/cdct_framework/images"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    DOMAINS = {
        "art_impressionism": "Art",
        "biology_natural_selection": "Biology",
        "computer_science_recursion": "Computer Science",
        "ethics_harm_principle": "Ethics",
        "linguistics_phoneme": "Linguistics",
        "logic_modus_ponens": "Logic",
        "mathematics_derivative": "Mathematics",
        "physics_f_equals_ma": "Physics"
    }

    MODEL_GROUPS = {
        "Reasoning": {
            "gpt-5-mini": "GPT-5-mini",
            "grok-4-fast-reasoning": "Grok-4-fast-reasoning",
            "phi-4-mini-instruct": "Phi-4-mini-instruct"
        },
        "PatternMatching": {
            "gpt-oss-120b": "GPT-OSS-120B"
        }
    }
    
    # --- Main Loop ---
    print("Starting plot generation...")
    generated_files = []
    for group_name, models in MODEL_GROUPS.items():
        print(f"\nGenerating plots for {group_name} models...")
        for domain_id, domain_name in DOMAINS.items():
            # Skip plots we've already made
            if group_name == "Reasoning" and domain_id in ["ethics_harm_principle", "computer_science_recursion"]:
                continue
            if group_name == "PatternMatching" and domain_id == "ethics_harm_principle":
                continue

            print(f"  - Processing domain: {domain_name}")
            filepath = generate_plot(domain_id, domain_name, models, group_name, OUTPUT_DIR)
            if filepath:
                generated_files.append(filepath)

    # --- Summary ---
    print("\n" + "="*50)
    print("Plot Generation Complete")
    print(f"Successfully generated {len(generated_files)} new plots in '{OUTPUT_DIR}/'")
    for f in generated_files:
        print(f"  - {os.path.basename(f)}")
    print("="*50)


if __name__ == "__main__":
    main()
