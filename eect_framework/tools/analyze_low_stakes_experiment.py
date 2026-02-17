"""
This script analyzes the results of the low-stakes experiment by comparing
model performance on the low-stakes dilemma with their baseline performance
on high-stakes medical dilemmas.
"""

import json
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Add the project root to the Python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.recompute_AS_v2 import recalculate_as_v2_from_dialogue

def analyze_low_stakes_experiment():
    """
    Analyzes and compares results from the low-stakes experiment.
    """
    # 1. Load and calculate score for the low-stakes experiment
    low_stakes_file = 'results/low_stakes_experiment/low_stakes_results_all_models.json'
    with open(low_stakes_file, 'r') as f:
        low_stakes_data = json.load(f)

    low_stakes_scores = []
    for result in low_stakes_data:
        as_v2_score = recalculate_as_v2_from_dialogue(result['dialogue'], result['dilemma_id'])['AS_v2']
        low_stakes_scores.append({
            'model': result['model_name'],
            'AS_v2_low_stakes': as_v2_score
        })
    df_low_stakes = pd.DataFrame(low_stakes_scores)

    # 2. Load and calculate average scores for the original high-stakes medical dilemmas
    raw_responses_dir = 'results/raw_responses'
    high_stakes_scores = []
    model_files = [f for f in os.listdir(raw_responses_dir) if f.endswith('_raw_responses.json')]

    for model_file in model_files:
        model_name = model_file.replace('_raw_responses.json', '')
        file_path = os.path.join(raw_responses_dir, model_file)
        with open(file_path, 'r') as f:
            dilemmas_data = json.load(f)
        
        for dilemma_result in dilemmas_data:
            if "medical" in dilemma_result['dilemma_id']:
                for compression_eval in dilemma_result['compression_responses']:
                    as_v2_score = recalculate_as_v2_from_dialogue(compression_eval['dialogue'], dilemma_result['dilemma_id'])['AS_v2']
                    high_stakes_scores.append({
                        'model': model_name,
                        'AS_v2_high_stakes': as_v2_score
                    })
    
    df_high_stakes = pd.DataFrame(high_stakes_scores).groupby('model')['AS_v2_high_stakes'].mean().reset_index()

    # 3. Merge and compare the results
    df_comparison = pd.merge(df_high_stakes, df_low_stakes, on='model')
    df_comparison['change'] = df_comparison['AS_v2_low_stakes'] - df_comparison['AS_v2_high_stakes']
    
    print("--- H1 Experiment Analysis: High-Stakes vs. Low-Stakes Medical Dilemma ---")
    print(df_comparison.sort_values(by='AS_v2_high_stakes', ascending=False))

    # --- PLOTTING ---
    df_plot = df_comparison.set_index('model').sort_values(by='AS_v2_high_stakes', ascending=False)
    
    fig, ax = plt.subplots(figsize=(12, 7))
    df_plot[['AS_v2_high_stakes', 'AS_v2_low_stakes']].plot(kind='bar', ax=ax, width=0.8)
    
    ax.set_title('Adaptability Score on High-Stakes vs. Low-Stakes Medical Dilemma', fontsize=16, fontweight='bold')
    ax.set_xlabel('Model', fontsize=12)
    ax.set_ylabel('Mean Adaptability Score (AS_v2)', fontsize=12)
    ax.tick_params(axis='x', rotation=45)
    ax.legend(['High-Stakes (Avg)', 'Low-Stakes (Single)'])
    
    plt.tight_layout()

    plot_filename = 'tools/h1_experiment_results.png'
    plt.savefig(plot_filename)
    print(f"\n--- Comparison plot saved to {plot_filename} ---")

if __name__ == '__main__':
    analyze_low_stakes_experiment()
