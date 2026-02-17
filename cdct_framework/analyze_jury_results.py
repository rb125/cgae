"""
Comprehensive analysis of partial jury results
Analyzes all available data in results_jury without requiring server access
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from collections import defaultdict
import numpy as np
from statsmodels.stats.inter_rater import fleiss_kappa

def load_results(results_dir: Path) -> List[Dict]:
    """Load all result files from directory."""
    results = []
    for file_path in sorted(results_dir.glob('*.json')):
        try:
            with open(file_path) as f:
                data = json.load(f)
                results.append(data)
        except Exception as e:
            print(f"Warning: Failed to load {file_path.name}: {e}")
    return results

def analyze_model_performance(results: List[Dict]) -> Dict:
    """Analyze performance metrics by model."""
    by_model = defaultdict(list)
    
    for result in results:
        model = result.get('subject_model', 'unknown')
        analysis = result.get('analysis', {})
        
        if analysis:
            by_model[model].append({
                'concept': result.get('concept'),
                'mean_score': analysis.get('mean_score'),
                'csi': analysis.get('CSI'),
                'decay_direction': analysis.get('decay_direction'),
                'mean_agreement': analysis.get('mean_agreement')
            })
    
    # Compute aggregates
    performance = {}
    for model, data_points in sorted(by_model.items()):
        scores = [d['mean_score'] for d in data_points if d['mean_score'] is not None]
        csis = [d['csi'] for d in data_points if d['csi'] is not None]
        
        improves = sum(1 for d in data_points if '↑' in d.get('decay_direction', ''))
        decays = len(data_points) - improves
        
        performance[model] = {
            'count': len(data_points),
            'mean_score_avg': float(np.mean(scores)) if scores else None,
            'mean_score_std': float(np.std(scores)) if scores else None,
            'csi_avg': float(np.mean(csis)) if csis else None,
            'csi_std': float(np.std(csis)) if csis else None,
            'improves_count': improves,
            'decays_count': decays,
            'improves_pct': 100 * improves / len(data_points) if data_points else 0
        }
    
    return performance

def analyze_concept_performance(results: List[Dict]) -> Dict:
    """Analyze performance metrics by concept."""
    by_concept = defaultdict(list)
    
    for result in results:
        concept = result.get('concept', 'unknown')
        analysis = result.get('analysis', {})
        
        if analysis:
            by_concept[concept].append({
                'model': result.get('subject_model'),
                'mean_score': analysis.get('mean_score'),
                'csi': analysis.get('CSI'),
                'decay_direction': analysis.get('decay_direction'),
                'mean_agreement': analysis.get('mean_agreement')
            })
    
    # Compute aggregates
    performance = {}
    for concept, data_points in sorted(by_concept.items()):
        scores = [d['mean_score'] for d in data_points if d['mean_score'] is not None]
        csis = [d['csi'] for d in data_points if d['csi'] is not None]
        
        improves = sum(1 for d in data_points if '↑' in d.get('decay_direction', ''))
        decays = len(data_points) - improves
        
        performance[concept] = {
            'count': len(data_points),
            'mean_score_avg': float(np.mean(scores)) if scores else None,
            'mean_score_std': float(np.std(scores)) if scores else None,
            'csi_avg': float(np.mean(csis)) if csis else None,
            'csi_std': float(np.std(csis)) if csis else None,
            'improves_count': improves,
            'decays_count': decays,
            'improves_pct': 100 * improves / len(data_points) if data_points else 0
        }
    
    return performance

def analyze_compression_effect(results: List[Dict]) -> Dict:
    """Analyze compression benefit patterns."""
    improves_list = []
    decays_list = []
    
    for result in results:
        analysis = result.get('analysis', {})
        if analysis:
            decay_dir = analysis.get('decay_direction', '')
            if '↑' in decay_dir:
                improves_list.append({
                    'model': result.get('subject_model'),
                    'concept': result.get('concept'),
                    'mean_score': analysis.get('mean_score'),
                    'csi': analysis.get('CSI')
                })
            else:
                decays_list.append({
                    'model': result.get('subject_model'),
                    'concept': result.get('concept'),
                    'mean_score': analysis.get('mean_score'),
                    'csi': analysis.get('CSI')
                })
    
    return {
        'total_results': len(results),
        'compression_improves': len(improves_list),
        'compression_decays': len(decays_list),
        'improves_pct': 100 * len(improves_list) / len(results) if results else 0,
        'decays_pct': 100 * len(decays_list) / len(results) if results else 0
    }

def analyze_agreement(results: List[Dict]) -> Dict:
    """Analyze jury agreement metrics."""
    agreements = []
    
    for result in results:
        analysis = result.get('analysis', {})
        agreement = analysis.get('mean_agreement')
        if agreement is not None:
            agreements.append(agreement)
    
    if not agreements:
        return {'no_data': True}
    
    return {
        'count': len(agreements),
        'mean': float(np.mean(agreements)),
        'std': float(np.std(agreements)),
        'min': float(np.min(agreements)),
        'max': float(np.max(agreements)),
        'median': float(np.median(agreements))
    }

def calculate_fleiss_kappa_scores(results: List[Dict]) -> Dict:
    """Calculate Fleiss' Kappa for FAR, SAS, and FC based on discretized scores."""
    far_ratings = []
    sas_ratings = []
    fc_ratings = []

    num_judges = 3 # Fixed for this jury setup

    def calculate_kappa_or_nan_reason(ratings_list, metric_name):
        if not ratings_list:
            return f"No valid ratings for {metric_name}"
        kappa_input = np.array([[row.count(0), row.count(1)] for row in ratings_list])
        if kappa_input.shape[0] == 0:
            return f"No items for {metric_name} after filtering"
        
        # Check for perfect agreement or no variability
        all_zeros = np.all(kappa_input[:, 0] == num_judges) # All judges rated 0 for all items
        all_ones = np.all(kappa_input[:, 1] == num_judges) # All judges rated 1 for all items
        
        if all_zeros or all_ones:
            # If all raters assigned the same category to all subjects, Fleiss' Kappa is undefined.
            # It means there is no variability in the ratings, so p_mean_exp becomes 1, leading to NaN.
            # In such cases, agreement is effectively perfect.
            return f"Perfect agreement (all {('0' if all_zeros else '1')}s) for {metric_name} across all items. Kappa is undefined."
        
        # Check for cases where p_mean_exp might become 1 due to certain edge cases in variability
        # statsmodels handles this with a RuntimeWarning, but returning nan.
        # We can run a preliminary check. If only one category is ever used (e.g., all items are rated as '0' by all judges),
        # or if the distribution is such that p_mean_exp becomes 1, then Kappa is undefined.
        
        try:
            kappa_value = fleiss_kappa(kappa_input, method='fleiss')
            return float(kappa_value)
        except Exception as e:
            return f"Error calculating Kappa for {metric_name}: {e}. Possibly no variability in ratings."

    for result in results:
        for perf_entry in result.get('performance', []):
            jury_eval = perf_entry.get('jury_evaluation', {})
            judges_scores = jury_eval.get('judges', {})

            if len(judges_scores) == num_judges:
                current_far_scores = []
                current_sas_scores = []
                current_fc_scores = []
                
                # First, collect all scores for this item
                for judge_name in sorted(judges_scores.keys()):
                    score = judges_scores[judge_name]
                    current_far_scores.append(score.get('CC')) # Changed from 'FAR' to 'CC'
                    current_sas_scores.append(score.get('SA')) # Changed from 'SAS' to 'SA'
                    current_fc_scores.append(score.get('FC'))

                # Now, validate and discretize. If any judge returned None for a metric,
                # that entire item is skipped for that metric's kappa calculation.
                if all(s is not None for s in current_far_scores):
                    far_ratings.append([1 if s > 0.7 else 0 for s in current_far_scores])

                if all(s is not None for s in current_sas_scores):
                    sas_ratings.append([1 if s > 0.7 else 0 for s in current_sas_scores])
                
                if all(s is not None for s in current_fc_scores):
                    fc_ratings.append([1 if s > 0.7 else 0 for s in current_fc_scores])


    kappa_results = {}
    
    kappa_results['fleiss_kappa_cc'] = calculate_kappa_or_nan_reason(far_ratings, 'CC') # Changed from 'far' to 'cc'
    kappa_results['fleiss_kappa_sa'] = calculate_kappa_or_nan_reason(sas_ratings, 'SA') # Changed from 'sas' to 'sa'
    kappa_results['fleiss_kappa_fc'] = calculate_kappa_or_nan_reason(fc_ratings, 'FC')

    return kappa_results

def main():
    """Run comprehensive analysis on partial jury results."""
    
    results_dir = Path('results_jury')
    results = load_results(results_dir)
    
    print("="*80)
    print("JURY RESULTS ANALYSIS (Partial Data)")
    print("="*80)
    print(f"\nTimestamp: {datetime.now().isoformat()}")
    print(f"Results directory: {results_dir}")
    print(f"Total results loaded: {len(results)}\n")
    
    # Model performance
    print("="*80)
    print("MODEL PERFORMANCE")
    print("="*80 + "\n")
    
    model_perf = analyze_model_performance(results)
    for model in sorted(model_perf.keys()):
        perf = model_perf[model]
        print(f"▶ {model}")
        print(f"  Experiments: {perf['count']}")
        print(f"  Mean Score: {perf['mean_score_avg']:.4f} ± {perf['mean_score_std']:.4f}")
        print(f"  CSI: {perf['csi_avg']:.4f} ± {perf['csi_std']:.4f}")
        print(f"  Compression improves: {perf['improves_count']}/{perf['count']} ({perf['improves_pct']:.1f}%)")
        print()
    
    # Concept performance
    print("="*80)
    print("CONCEPT PERFORMANCE")
    print("="*80 + "\n")
    
    concept_perf = analyze_concept_performance(results)
    for concept in sorted(concept_perf.keys()):
        perf = concept_perf[concept]
        print(f"▶ {concept}")
        print(f"  Experiments: {perf['count']}")
        print(f"  Mean Score: {perf['mean_score_avg']:.4f} ± {perf['mean_score_std']:.4f}")
        print(f"  CSI: {perf['csi_avg']:.4f} ± {perf['csi_std']:.4f}")
        print(f"  Compression improves: {perf['improves_count']}/{perf['count']} ({perf['improves_pct']:.1f}%)")
        print()
    
    # Compression effect
    print("="*80)
    print("COMPRESSION EFFECT SUMMARY")
    print("="*80 + "\n")
    
    comp_effect = analyze_compression_effect(results)
    print(f"Total experiments analyzed: {comp_effect['total_results']}")
    print(f"Compression improves: {comp_effect['compression_improves']} ({comp_effect['improves_pct']:.1f}%)")
    print(f"Compression decays: {comp_effect['compression_decays']} ({comp_effect['decays_pct']:.1f}%)\n")
    
    if comp_effect['improves_pct'] > 50:
        verdict = "Compression benefit detected across experiments"
    else:
        verdict = "Compression detriment or neutral effect across experiments"
    print(f"Verdict: {verdict}\n")
    
    # Jury agreement
    print("="*80)
    print("JURY AGREEMENT METRICS")
    print("="*80 + "\n")
    
    agreement = analyze_agreement(results)
    if 'no_data' not in agreement:
        print(f"Mean agreement: {agreement['mean']:.4f}")
        print(f"Std deviation: {agreement['std']:.4f}")
        print(f"Range: [{agreement['min']:.4f}, {agreement['max']:.4f}]")
        print(f"Median: {agreement['median']:.4f}\n")
    else:
        print("No agreement data available\n")
    
    # Fleiss' Kappa
    print("="*80)
    print("FLEISS' KAPPA (Inter-Judge Reliability)")
    print("="*80 + "\n")
    
    fleiss_kappa_results = calculate_fleiss_kappa_scores(results)
    if fleiss_kappa_results:
        for metric, kappa_val in fleiss_kappa_results.items():
            if isinstance(kappa_val, float):
                print(f"{metric.replace('_', ' ').title()}: {kappa_val:.4f}")
            else:
                print(f"{metric.replace('_', ' ').title()}: {kappa_val}")
        print("\n")
    else:
        print("No Fleiss' Kappa data available (likely no valid jury evaluations).\n")

    # Save report
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_results': len(results),
        'model_performance': model_perf,
        'concept_performance': concept_perf,
        'compression_effect': comp_effect,
        'jury_agreement': agreement,
        'fleiss_kappa': fleiss_kappa_results # Add Fleiss' Kappa to the report
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"verification_results/jury_analysis_{timestamp}.json"
    os.makedirs("verification_results", exist_ok=True)
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Report saved to: {report_file}\n")

if __name__ == "__main__":
    main()
