"""
This script performs an analysis to find correlations between model architecture
and ethical adaptability scores (AS) from the EECT benchmark.

It combines the architectural data from models_config.py with the
final results from the EECT paper to identify trends.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def analyze_architectural_correlates():
    """
    Performs the correlation analysis between model architecture and EECT scores.
    """
    # 1. Define the data, combining results from the paper and arch from config
    data = [
        # Data from Table 2 in eect_arXiv.tex and models_config.py
        # AS = Adaptability Score, ECS = Ethical Coherence Score
        {'model': 'O4-Mini', 'AS': 0.520, 'ECS': 8.730, 'architecture': 'Reasoning-Aligned', 'params': 'Undisclosed', 'family': 'OpenAI'},
        {'model': 'Phi-4', 'AS': 0.520, 'ECS': 8.390, 'architecture': 'Reasoning-Aligned', 'params': '14B', 'family': 'Microsoft'},
        {'model': 'Llama-4-Maverick', 'AS': 0.520, 'ECS': 8.167, 'architecture': 'Mixture-of-Experts', 'params': '17B', 'family': 'Meta'},
        {'model': 'GPT-OSS-120B', 'AS': 0.510, 'ECS': 8.806, 'architecture': 'Dense', 'params': '120B', 'family': 'OpenSource'},
        {'model': 'O3', 'AS': 0.468, 'ECS': 8.859, 'architecture': 'Reasoning-Aligned', 'params': 'Undisclosed', 'family': 'OpenAI'},
        {'model': 'GPT-5', 'AS': 0.458, 'ECS': 8.852, 'architecture': 'Reasoning-Aligned', 'params': 'Undisclosed', 'family': 'OpenAI'},
        {'model': 'Grok-4-Fast', 'AS': 0.437, 'ECS': 8.225, 'architecture': 'Dense', 'params': 'Undisclosed', 'family': 'xAI'},
    ]

    df = pd.DataFrame(data)

    # Add a 'pass_fail' column based on the AS > 0.5 threshold
    df['status'] = np.where(df['AS'] > 0.5, 'Pass', 'Fail')

    # 2. Perform analysis
    print("--- EECT Architecture vs. Adaptability Analysis ---")
    print("\n1. Raw Data:")
    print(df)

    # Group by architecture and calculate mean scores
    arch_analysis = df.groupby('architecture')['AS'].agg(['mean', 'count']).sort_values(by='mean', ascending=False)
    print("\n2. Mean Adaptability Score (AS) by Architecture:")
    print(arch_analysis)

    # --- PLOTTING ---
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(10, 6))

    arch_analysis['mean'].plot(kind='bar', ax=ax, color=['#4E79A7', '#F28E2B', '#59A14F'])
    
    ax.set_title('Mean Adaptability Score (AS) by Model Architecture', fontsize=16, fontweight='bold')
    ax.set_xlabel('Architecture Type', fontsize=12)
    ax.set_ylabel('Mean Adaptability Score (AS)', fontsize=12)
    ax.tick_params(axis='x', rotation=0)
    
    # Add a horizontal line for the pass threshold
    ax.axhline(y=0.5, color='r', linestyle='--', linewidth=2, label='Pass Threshold (AS=0.5)')
    
    # Add data labels on top of bars
    for i, v in enumerate(arch_analysis['mean']):
        ax.text(i, v + 0.005, f"{v:.3f}", ha='center', fontweight='bold')

    ax.legend()
    plt.tight_layout()

    # Save the figure
    plot_filename = 'tools/architecture_performance.png'
    plt.savefig(plot_filename)
    print(f"\n--- Plot saved to {plot_filename} ---")
    # --- END PLOTTING ---


    # Group by family and calculate mean scores
    family_analysis = df.groupby('family')['AS'].agg(['mean', 'count']).sort_values(by='mean', ascending=False)
    print("\n3. Mean Adaptability Score (AS) by Model Family:")
    print(family_analysis)

    # Observation on reasoning-aligned models
    reasoning_aligned_models = df[df['architecture'] == 'Reasoning-Aligned']
    print("\n4. Analysis of 'Reasoning-Aligned' models:")
    print(reasoning_aligned_models)
    print("\nObservation: The 'Reasoning-Aligned' architecture type shows the widest variance in performance,")
    print("containing top-tier models (O4-Mini, Phi-4) and low-tier models (O3, GPT-5).")
    print("This suggests that 'Reasoning-Aligned' is not a monolithic category and other factors are at play.")

    # MoE vs Dense
    print("\n5. MoE vs. Dense Architectures:")
    moe_model = df[df['architecture'] == 'Mixture-of-Experts']
    dense_models = df[df['architecture'] == 'Dense']
    print("MoE Model (Llama-4):")
    print(moe_model[['model', 'AS', 'status']])
    print("\nDense Models (GPT-OSS, Grok-4):")
    print(dense_models[['model', 'AS', 'status']])
    print("\nObservation: The single MoE model passed, while the dense models were split (1 pass, 1 fail).")


if __name__ == '__main__':
    analyze_architectural_correlates()
