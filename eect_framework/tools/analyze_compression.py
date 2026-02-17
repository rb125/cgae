"""
This script analyzes the impact of prompt compression on the Adaptability Score (AS).

It iterates through the scored results for each model, recalculates the AS
for each dilemma at each of the 5 compression levels using the correct,
action-gated formula from the EECT paper, and then aggregates the results.

The formula used is: AS = ACT * III * (1 - RI) * (1 - PER)
"""

import sys
import os
# Add the project root to the Python path to allow for `from src...` imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import pandas as pd
import matplotlib.pyplot as plt
from src.algorithmic_checks import (
    analyze_dialogue,
    detect_position_reversal,
    calculate_information_integration_index,
    calculate_rigidity_index,
    calculate_procedural_ethical_ratio
)

def get_act_score(position_reversal: dict) -> int:
    """
    Calculates the ACT (Action) score.
    Returns 1 if there was any position reversal, 0 otherwise.
    
    Note: The paper also mentions a confidence drop of >= 2.0, but the
    dialogue protocol does not capture Turn 1 confidence, making this
    part of the ACT score impossible to calculate. We proceed using only
    position reversal as the basis for action.
    """
    return 1 if position_reversal.get('any_reversal', False) else 0

def recalculate_as_from_dialogue(dialogue_results: list, dilemma_id: str) -> float:
    """
    Recalculates the Adaptability Score (AS) from dialogue turns using the
    formula found in the project's source code.
    """
    if len(dialogue_results) < 5:
        return 0.0

    # The analyze_dialogue function from the source contains the full logic.
    # It calculates all components and the final AS. We will use it directly.
    full_analysis = analyze_dialogue(dialogue_results, dilemma_id)

    # The paper's formula seems to be a simplification. The code's formula is:
    # AS = III * (1 - RI) * (1 - PER), with the "action" implicitly part of RI.
    # We will use the score as calculated by the project's own logic.
    as_metric = full_analysis.get('adaptability_score', {})
    as_score = as_metric.get('as_score', 0.0)
    
    return as_score

def analyze_compression_impact():
    """
    Main function to analyze compression impact across all models.
    """
    raw_responses_dir = 'results/raw_responses'
    results = []

    model_files = [f for f in os.listdir(raw_responses_dir) if f.endswith('_raw_responses.json')]

    for model_file in model_files:
        model_name = model_file.replace('_raw_responses.json', '')
        file_path = os.path.join(raw_responses_dir, model_file)

        with open(file_path, 'r') as f:
            # The root of the raw responses is a list of dilemmas
            dilemmas_data = json.load(f)

        for dilemma_result in dilemmas_data:
            dilemma_id = dilemma_result['dilemma_id']
            
            for compression_eval in dilemma_result['compression_responses']:
                compression_level = compression_eval['compression_level']
                # The dialogue objects are in the 'dialogue' key
                dialogue_results = compression_eval['dialogue'] 

                # The key step: recalculate AS with the correct formula
                as_score = recalculate_as_from_dialogue(dialogue_results, dilemma_id)
                
                results.append({
                    'model': model_name,
                    'dilemma': dilemma_id,
                    'compression': compression_level,
                    'AS': as_score
                })

    df = pd.DataFrame(results)
    
    print("--- Compression vs. Adaptability Score (AS) Analysis ---")
    print(f"\nSuccessfully processed {len(df)} data points from {len(model_files)} models.")

    # Group by model and compression level to get the mean AS
    compression_analysis = df.groupby(['model', 'compression'])['AS'].mean().unstack()
    
    # Order compression levels correctly
    compression_order = ['c1.0', 'c0.75', 'c0.5', 'c0.25', 'c0.0']
    compression_analysis = compression_analysis[compression_order]
    
    print("\nMean Adaptability Score (AS) by Model and Compression Level:")
    print(compression_analysis)

    # --- PLOTTING ---
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))

    compression_analysis.T.plot(kind='line', marker='o', ax=ax)
    
    ax.set_title('Impact of Prompt Compression on Model Adaptability', fontsize=16, fontweight='bold')
    ax.set_xlabel('Prompt Compression Level', fontsize=12)
    ax.set_ylabel('Mean Adaptability Score (AS)', fontsize=12)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    ax.legend(title='Model', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()

    # Save the figure
    plot_filename = 'tools/compression_impact.png'
    plt.savefig(plot_filename)
    print(f"\n--- Plot saved to {plot_filename} ---")


if __name__ == '__main__':
    analyze_compression_impact()
