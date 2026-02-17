
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import json
import glob

# ==============================================================================
# FIGURE 1: PERFORMANCE DECAY CURVES
# ==============================================================================
def generate_decay_curves():
    """Generates a line plot contrasting high-CSI and low-CSI models."""
    print("Generating Figure 1: Performance Decay Curves...")
    
    # Data extracted from results for the "mathematics_derivative" concept
    data_gpt5_mini = {
        "c": [0.0476, 0.1428, 0.1746, 0.4285, 1.0],
        "performance": [1.0, 1.0, 1.0, 1.0, 1.0]
    }
    data_gpt_oss = {
        "c": [0.0476, 0.3174, 0.1746, 0.7270, 1.0],
        "performance": [1.0, 1.0, 1.0, 1.0, 0.833]
    }

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(data_gpt5_mini["c"], data_gpt5_mini["performance"], marker='o', linestyle='--', label='GPT-5-mini (CSI = 0.00)')
    ax.plot(data_gpt_oss["c"], data_gpt_oss["performance"], marker='s', linestyle='--', label='GPT-OSS-120B (CSI = 0.17)')

    # Fit and plot linear regression lines
    z_gpt5 = np.polyfit(data_gpt5_mini["c"], data_gpt5_mini["performance"], 1)
    p_gpt5 = np.poly1d(z_gpt5)
    ax.plot(data_gpt5_mini["c"], p_gpt5(data_gpt5_mini["c"] ), color='blue', alpha=0.5)

    z_oss = np.polyfit(data_gpt_oss["c"], data_gpt_oss["performance"], 1)
    p_oss = np.poly1d(z_oss)
    ax.plot(data_gpt_oss["c"], p_oss(data_gpt_oss["c"] ), color='orange', alpha=0.5)

    ax.set_title('Figure 1: Performance Decay vs. Semantic Compression', fontsize=14, pad=20)
    ax.set_xlabel('Compression Level (c) [0 = Max Compression, 1 = Full Info]', fontsize=12)
    ax.set_ylabel('Performance Score P(c)', fontsize=12)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlim(-0.05, 1.05)
    ax.legend(title='Model (CSI)', fontsize=10)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

    plt.tight_layout()
    plt.savefig('decay_curves.png', dpi=300)
    plt.close(fig)
    print("Saved decay_curves.png")

# ==============================================================================
# FIGURE 2: CSI VS. MODEL SCALE SCATTER PLOT
# ==============================================================================
def generate_csi_vs_scale_scatter():
    """Generates a scatter plot of CSI vs. log-parameters to show lack of correlation."""
    print("\nGenerating Figure 2: CSI vs. Model Scale Scatter Plot...")
    
    data = {
        'Model': [
            'GPT-5-mini', 'Grok-4-fast-reasoning', 'DeepSeek-V3-0324', 
            'Mistral-medium-2505', 'Phi-4-mini-instruct', 'GPT-4.1', 'GPT-OSS-120B'
        ],
        'Params (B)': [27, 1000, 671, 22, 3.8, 1200, 120],
        'Mean CSI': [0.0949, 0.1048, 0.1395, 0.1610, 0.1616, 0.1671, 0.1774]
    }
    df = pd.DataFrame(data)

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.scatter(df['Params (B)'], df['Mean CSI'], s=100, alpha=0.7, c=df['Mean CSI'], cmap='viridis_r')
    ax.set_xscale('log')

    for i, row in df.iterrows():
        ax.text(row['Params (B)'], row['Mean CSI'] + 0.002, row['Model'], fontsize=9, ha='center')

    z = np.polyfit(np.log10(df['Params (B)']), df['Mean CSI'], 1)
    p = np.poly1d(z)
    ax.plot(df['Params (B)'].sort_values(), p(np.log10(df['Params (B)'].sort_values())), "r--", alpha=0.5, label=f'Trend (r ≈ -0.13)')

    ax.set_title('Figure 2: Comprehension Stability (CSI) vs. Model Scale', fontsize=14, pad=20)
    ax.set_xlabel('Model Parameters (Billions) - Log Scale', fontsize=12)
    ax.set_ylabel('Mean Comprehension Stability Index (CSI)', fontsize=12)
    ax.legend()
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

    plt.tight_layout()
    plt.savefig('csi_vs_scale.png', dpi=300)
    plt.close(fig)
    print("Saved csi_vs_scale.png")

# ==============================================================================
# FIGURE 3: ARCHITECTURAL GROUPING BAR CHART
# ==============================================================================
def generate_arch_group_barchart():
    """Generates a bar chart visualizing Mean CSI by architectural paradigm."""
    print("\nGenerating Figure 3: Architectural Grouping Bar Chart...")
    
    architectures = {
        'Reasoning-Aligned': 0.1238,
        'Scaling-Optimized': 0.1559,
        'Pattern-Matching': 0.1774
    }
    labels = list(architectures.keys())
    csi_values = list(architectures.values())

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(8, 6))

    colors = ['#4CAF50', '#FFC107', '#F44336']
    bars = ax.bar(labels, csi_values, color=colors, alpha=0.8)

    ax.set_title('Figure 3: Mean Comprehension Stability by Architectural Paradigm', fontsize=14, pad=20)
    ax.set_ylabel('Mean Comprehension Stability Index (CSI)', fontsize=12)
    ax.set_xlabel('Architectural Group', fontsize=12)
    ax.set_ylim(0, 0.2)

    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.005, f'{yval:.4f}', ha='center', va='bottom')

    ax.axhline(y=0.11, color='darkgreen', linestyle='--', linewidth=1, label='Reasoning-Aligned Threshold (CSI < 0.11)')

    ax.legend()
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    plt.savefig('architectural_grouping_bar_chart.png', dpi=300)
    plt.close(fig)
    print("Saved architectural_grouping_bar_chart.png")

# ==============================================================================
# FIGURE 4: CSI HEATMAP
# ==============================================================================
def load_all_results_data():
    """Loads all result files and extracts the data needed for the heatmap."""
    data = []
    result_files = glob.glob('results/results_*.json')

    if not result_files:
        print("Warning: No result files found in the 'results/' directory.")
        return pd.DataFrame()

    for f_path in result_files:
        with open(f_path, 'r') as f:
            try:
                content = json.load(f)
                model = content.get('model', 'Unknown Model')
                domain = content.get('domain', 'Unknown Domain')
                csi = content.get('analysis', {}).get('CSI')

                if csi is not None:
                    data.append({
                        'Model': model,
                        'Domain': domain.replace('_', ' ').title(),
                        'CSI': csi
                    })
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON from {f_path}")
                continue
    
    return pd.DataFrame(data)

def generate_csi_heatmap(df):
    """Generates and saves the heatmap from the processed DataFrame."""
    print("\nGenerating Figure 4: CSI Heatmap by Model and Domain...")
    
    if df.empty:
        print("Skipping heatmap generation: No data found.")
        return

    try:
        pivot_table = df.pivot_table(index='Model', columns='Domain', values='CSI')
        ordered_domains = [
            'Logic', 'Physics', 'Mathematics', 'Linguistics', 
            'Biology', 'Computer Science', 'Ethics', 'Art'
        ]
        # Ensure only columns that exist in the pivot table are selected
        ordered_domains_exist = [d for d in ordered_domains if d in pivot_table.columns]
        pivot_table = pivot_table[ordered_domains_exist]

        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(12, 8))

        sns.heatmap(
            pivot_table, 
            annot=True, 
            fmt=".3f", 
            linewidths=.5, 
            cmap="viridis_r",
            ax=ax
        )

        ax.set_title('Heatmap of Comprehension Stability Index (CSI) by Model and Domain', fontsize=16, pad=20)
        ax.set_xlabel('Conceptual Domain', fontsize=12)
        ax.set_ylabel('Model', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)

        plt.tight_layout()
        plt.savefig('csi_heatmap.png', dpi=300)
        plt.close(fig)
        print("Saved csi_heatmap.png")

    except Exception as e:
        print(f"Could not generate heatmap. Error: {e}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main function to generate all figures."""
    print("--- Generating All Figures for CDCT Paper ---")
    
    # Generate plots from hardcoded summary data
    generate_decay_curves()
    generate_csi_vs_scale_scatter()
    generate_arch_group_barchart()
    
    # Load full results data once for the heatmap
    results_df = load_all_results_data()
    
    # Generate heatmap from the loaded data
    generate_csi_heatmap(results_df)
    
    print("\n--- All figures generated successfully! ---")

if __name__ == '__main__':
    main()
