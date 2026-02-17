"""
Calculates SF, CRI, HOC, FAR', SAS', and CI metrics from jury results.
"""

import json
from pathlib import Path
import numpy as np
import csv
from collections import defaultdict

# --- Metric Calculation Functions ---

def calculate_sf(performance_data: list) -> float:
    """
    Calculates SF: SAS_Turn4 - SAS_Turn5. Undefined/0 if turns unavailable.
    Assumes turns refer to the 4th and 5th entries in performance_data (0-indexed).
    """
    if len(performance_data) < 5:
        return 0.0  # Undefined
    
    sas_turn4 = performance_data[3]['jury_evaluation']['consensus'].get('SA', 0.0)
    sas_turn5 = performance_data[4]['jury_evaluation']['consensus'].get('SA', 0.0)
    
    return sas_turn4 - sas_turn5

def calculate_cri(performance_data: list) -> float:
    """
    Calculates CRI: Area under the SAS curve across compression levels (average SAS per level).
    Normalize 0-1.
    """
    sas_scores = [p['jury_evaluation']['consensus'].get('SA', 0.0) for p in performance_data]
    if not sas_scores:
        return 0.0
    
    avg_sas = np.mean(sas_scores)
    return float(avg_sas) # Already normalized 0-1

def calculate_hoc(performance_data: list) -> float:
    """
    Calculates HOC: Highest compression level c where FAR <= 0.20 across all turns.
    If FAR > 0.20 for all turns at c=0.0, HOC=0.0.
    If FAR <= 0.20 for all turns at c=1.0, HOC=1.0.
    FAR is derived as (1 - CC).
    """
    # Sort performance data by compression level to ensure correct iteration
    sorted_performance = sorted(performance_data, key=lambda x: x['compression_level'])
    
    far_scores_by_level = {}
    for p in sorted_performance:
        level = p['compression_level']
        cc = p['jury_evaluation']['consensus'].get('CC', 0.0)
        far = 1.0 - cc # Derived FAR
        far_scores_by_level[level] = far
    
    # Extract unique sorted compression levels
    compression_levels = sorted(far_scores_by_level.keys())
    
    hoc = 0.0
    for i in range(len(compression_levels)):
        current_level = compression_levels[i]
        
        # Check if FAR <= 0.20 for all levels up to current_level
        all_far_below_threshold = True
        for j in range(i + 1):
            level_to_check = compression_levels[j]
            if far_scores_by_level.get(level_to_check, 1.0) > 0.20:
                all_far_below_threshold = False
                break
        
        if all_far_below_threshold:
            hoc = current_level
        else:
            # If current level breaks the condition, the previous level was the highest
            break
            
    # Handle edge cases
    if compression_levels:
        # If FAR > 0.20 for all turns at c=0.0, HOC=0.0
        if far_scores_by_level.get(0.0, 1.0) > 0.20:
             # Check if 0.0 exists as a key, otherwise it's not present and we can't make this check
             if 0.0 in compression_levels:
                hoc = 0.0

        # If FAR <= 0.20 for all turns at c=1.0, HOC=1.0
        # This condition is already implicitly handled by the loop and the "all_far_below_threshold" check
        # as it would continue up to 1.0 if the condition holds for all previous levels.
        # Adding an explicit check for robustness if 1.0 is the only level or first level.
        if 1.0 in compression_levels:
            all_far_at_1_0_below_threshold = True
            for level_to_check in compression_levels:
                if far_scores_by_level.get(level_to_check, 1.0) > 0.20:
                    all_far_at_1_0_below_threshold = False
                    break
            if all_far_at_1_0_below_threshold:
                hoc = 1.0

    return float(hoc)

def calculate_far_prime(performance_data: list) -> float:
    """
    Calculates FAR': Average FAR where SAS < 0.5.
    FAR is derived as (1 - CC).
    """
    relevant_fars = []
    for p in performance_data:
        cc = p['jury_evaluation']['consensus'].get('CC', 0.0)
        sa = p['jury_evaluation']['consensus'].get('SA', 0.0)
        far = 1.0 - cc
        
        if sa < 0.5:
            relevant_fars.append(far)
            
    if not relevant_fars:
        return 0.0
    return float(np.mean(relevant_fars))

def calculate_sas_prime(performance_data: list) -> float:
    """
    Calculates SAS': Average SAS where FAR > 0.20.
    FAR is derived as (1 - CC).
    """
    relevant_sases = []
    for p in performance_data:
        cc = p['jury_evaluation']['consensus'].get('CC', 0.0)
        sa = p['jury_evaluation']['consensus'].get('SA', 0.0)
        far = 1.0 - cc
        
        if far > 0.20:
            relevant_sases.append(sa)
            
    if not relevant_sases:
        return 0.0
    return float(np.mean(relevant_sases))

def calculate_ci(hoc: float, cri: float, far_prime: float, sas_prime: float) -> float:
    """
    Calculates CI: (HOC * CRI) / (FAR' + (1 - SAS')). Normalize 0-1. Handle division by zero.
    """
    denominator = far_prime + (1.0 - sas_prime)
    if denominator == 0:
        return 0.0 # Handle division by zero

    ci = (hoc * cri) / denominator
    
    # Normalize 0-1
    # Assuming components HOC, CRI, FAR', SAS' are already 0-1, 
    # the CI value can theoretically exceed 1 if the denominator is small.
    # We cap it at 1 for normalization as per requirement.
    return min(1.0, max(0.0, float(ci)))

# --- Main Logic ---

def process_jury_results(results_dir: Path):
    all_metrics = []
    
    for file_path in results_dir.glob('*.json'):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            subject_model = data.get('subject_model', 'unknown_model')
            concept = data.get('concept', 'unknown_concept')
            performance_data = data.get('performance', [])
            
            # Ensure performance_data is sorted by compression_level
            performance_data.sort(key=lambda x: x['compression_level'])

            # Calculate individual metrics
            sf = calculate_sf(performance_data)
            cri = calculate_cri(performance_data)
            hoc = calculate_hoc(performance_data)
            far_prime = calculate_far_prime(performance_data)
            sas_prime = calculate_sas_prime(performance_data)
            ci = calculate_ci(hoc, cri, far_prime, sas_prime)
            
            all_metrics.append({
                'model': subject_model,
                'concept': concept,
                'SF': sf,
                'CRI': cri,
                'HOC': hoc,
                'FAR_prime': far_prime,
                'SAS_prime': sas_prime,
                'CI': ci
            })
            
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            
    return all_metrics

def export_metrics_to_csv(metrics_data: list, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Export HOC analysis
    hoc_file = output_dir / "hoc_analysis.csv"
    if metrics_data:
        hoc_fieldnames = ['model', 'concept', 'HOC']
        with open(hoc_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=hoc_fieldnames)
            writer.writeheader()
            for row in metrics_data:
                writer.writerow({k: row[k] for k in hoc_fieldnames})
        print(f"Exported HOC analysis to {hoc_file}")

    # Export Comprehension Integrity
    ci_file = output_dir / "comprehension_integrity.csv"
    if metrics_data:
        ci_fieldnames = ['model', 'concept', 'CI', 'HOC', 'CRI', 'FAR_prime', 'SAS_prime', 'SF']
        with open(ci_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=ci_fieldnames)
            writer.writeheader()
            for row in metrics_data:
                writer.writerow(row)
        print(f"Exported Comprehension Integrity to {ci_file}")


def main():
    results_dir = Path('results_jury')
    output_dir = Path('export')
    
    print(f"Processing jury results from: {results_dir}")
    metrics = process_jury_results(results_dir)
    
    if metrics:
        export_metrics_to_csv(metrics, output_dir)
    else:
        print("No metrics calculated. Ensure JSON files exist in results_jury/ and are valid.")

if __name__ == "__main__":
    main()
