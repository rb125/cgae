"""
Analyze RLHF ablation study results.
Compares baseline vs no_helpfulness prompts across all models and concepts.
"""
import json
import os
from pathlib import Path
from collections import defaultdict
import statistics
import re

def parse_filename(filename: str):
    """Parse jury result filename to extract concept and model."""
    # Format: jury_results_{concept}_{model}_compression_aware[_no_helpfulness].json
    # Example: jury_results_art_impressionism_gpt-5_compression_aware_no_helpfulness.json
    
    match = re.match(r"jury_results_(.+)_compression_aware(_no_helpfulness)?\.json", filename)
    if not match:
        return None, None, None
    
    full_part = match.group(1)
    is_ablated = match.group(2) is not None
    
    # Find last underscore that separates concept from model
    # Model names can contain underscores/hyphens
    parts = full_part.split("_")
    
    # Known concepts (from concepts/ directory)
    concepts = [
        "art_impressionism",
        "biology_natural_selection", 
        "computer_science_recursion",
        "ethics_harm_principle",
        "linguistics_phoneme",
        "logic_modus_ponens",
        "mathematics_derivative",
        "physics_f_equals_ma"
    ]
    
    # Find which concept this is
    for concept in concepts:
        if full_part.startswith(concept + "_"):
            model = full_part[len(concept)+1:]
            return concept, model, is_ablated
    
    return None, None, None

def load_results_from_directory(directory: str) -> dict:
    """Load all jury results from directory."""
    results = defaultdict(lambda: defaultdict(dict))
    
    results_dir = Path(directory)
    if not results_dir.exists():
        print(f"ERROR: Directory {directory} not found")
        return results
    
    for result_file in sorted(results_dir.glob("*.json")):
        try:
            with open(result_file, 'r') as f:
                data = json.load(f)
                concept = data.get('concept')  # Use concept from JSON
                model = data.get('subject_model')  # Use model from JSON
                
                if not concept or not model:
                    print(f"Warning: Could not extract concept/model from {result_file.name}")
                    continue
                
                is_ablated = "_no_helpfulness" in result_file.name
                key = "ablated" if is_ablated else "baseline"
                results[concept][model][key] = data
        
        except Exception as e:
            print(f"Warning: Error loading {result_file.name}: {e}")
    
    return results

def extract_cc_at_level(results_dict: dict, target_level: float) -> float:
    """Extract CC score at specific compression level."""
    if 'performance' not in results_dict or not results_dict['performance']:
        return None
    
    best_match = None
    min_diff = float('inf')
    
    for entry in results_dict['performance']:
        level = entry.get('compression_level', 0)
        diff = abs(level - target_level)
        
        if diff < min_diff:
            min_diff = diff
            best_match = entry
    
    if best_match:
        # Try to get CC score from jury evaluation
        jury_eval = best_match.get('jury_evaluation', {})
        consensus = jury_eval.get('consensus', {})
        cc_score = consensus.get('CC')
        
        if cc_score is not None:
            return cc_score
    
    return None

def main():
    print(f"\n{'='*80}")
    print("RLHF ABLATION ANALYSIS: Baseline vs No-Helpfulness")
    print(f"{'='*80}\n")
    
    # Load both baseline and ablated results
    print("Loading baseline results from results_jury/...")
    baseline_results = load_results_from_directory("results_jury")
    print(f"  Loaded {sum(len(m) for m in baseline_results.values())} models across {len(baseline_results)} concepts")
    
    print("Loading ablated results from results_jury_ablation/...")
    ablated_results = load_results_from_directory("results_jury_ablation")
    print(f"  Loaded {sum(len(m) for m in ablated_results.values())} models across {len(ablated_results)} concepts\n")
    
    # Compile comparison data
    comparisons = []
    
    for concept in sorted(set(list(baseline_results.keys()) + list(ablated_results.keys()))):
        for model in sorted(set(
            list(baseline_results[concept].keys()) + list(ablated_results[concept].keys())
        )):
            baseline_data = baseline_results[concept][model].get("baseline")
            ablated_data = ablated_results[concept][model].get("ablated")
            
            if not baseline_data or not ablated_data:
                continue
            
            # Extract CC at c=0.5
            baseline_cc = extract_cc_at_level(baseline_data, 0.5)
            ablated_cc = extract_cc_at_level(ablated_data, 0.5)
            
            if baseline_cc is None or ablated_cc is None:
                continue
            
            improvement = ablated_cc - baseline_cc
            improvement_pct = (improvement / max(baseline_cc, 0.01)) * 100
            
            comparisons.append({
                "concept": concept,
                "model": model,
                "baseline_cc": baseline_cc,
                "ablated_cc": ablated_cc,
                "improvement": improvement,
                "improvement_pct": improvement_pct
            })
    
    if not comparisons:
        print("ERROR: No valid comparisons found!")
        print("Check that both results_jury/ and results_jury_ablation/ contain matching files")
        return
    
    # Print detailed results table
    print("DETAILED RESULTS (all model × concept pairs):")
    print(f"\n{'Concept':<35} {'Model':<30} {'Baseline':<10} {'Ablated':<10} {'Improvement':<15}")
    print(f"{'-'*100}")
    
    for comp in sorted(comparisons, key=lambda x: -x['improvement_pct']):
        print(f"{comp['concept']:<35} {comp['model']:<30} "
              f"{comp['baseline_cc']:<10.3f} {comp['ablated_cc']:<10.3f} "
              f"{comp['improvement_pct']:>+6.1f}%")
    
    # Summary statistics by model
    print(f"\n{'='*80}")
    print("SUMMARY BY MODEL:")
    print(f"{'='*80}\n")
    
    by_model = defaultdict(list)
    for comp in comparisons:
        by_model[comp['model']].append(comp['improvement_pct'])
    
    model_stats = []
    for model in sorted(by_model.keys()):
        improvements = by_model[model]
        avg_imp = statistics.mean(improvements)
        min_imp = min(improvements)
        max_imp = max(improvements)
        count = len(improvements)
        
        model_stats.append({
            "model": model,
            "avg": avg_imp,
            "min": min_imp,
            "max": max_imp,
            "count": count
        })
        
        print(f"{model:<45}")
        print(f"  Average improvement: {avg_imp:+6.1f}%")
        print(f"  Range:              {min_imp:+6.1f}% to {max_imp:+6.1f}%")
        print(f"  Tests:              {count}")
        print()
    
    # Summary statistics by concept
    print(f"{'='*80}")
    print("SUMMARY BY CONCEPT:")
    print(f"{'='*80}\n")
    
    by_concept = defaultdict(list)
    for comp in comparisons:
        by_concept[comp['concept']].append(comp['improvement_pct'])
    
    for concept in sorted(by_concept.keys()):
        improvements = by_concept[concept]
        avg_imp = statistics.mean(improvements)
        min_imp = min(improvements)
        max_imp = max(improvements)
        count = len(improvements)
        
        print(f"{concept:<45}")
        print(f"  Average improvement: {avg_imp:+6.1f}%")
        print(f"  Range:              {min_imp:+6.1f}% to {max_imp:+6.1f}%")
        print(f"  Tests:              {count}")
        print()
    
    # Overall statistics
    print(f"{'='*80}")
    print("OVERALL STATISTICS:")
    print(f"{'='*80}\n")
    
    all_improvements = [comp['improvement_pct'] for comp in comparisons]
    all_baseline = [comp['baseline_cc'] for comp in comparisons]
    all_ablated = [comp['ablated_cc'] for comp in comparisons]
    
    avg_improvement = statistics.mean(all_improvements)
    median_improvement = statistics.median(all_improvements)
    min_improvement = min(all_improvements)
    max_improvement = max(all_improvements)
    positive_count = sum(1 for i in all_improvements if i > 0)
    
    print(f"Total trials:          {len(comparisons)}")
    print(f"Average improvement:   {avg_improvement:+6.1f}%")
    print(f"Median improvement:    {median_improvement:+6.1f}%")
    print(f"Min improvement:       {min_improvement:+6.1f}%")
    print(f"Max improvement:       {max_improvement:+6.1f}%")
    print(f"Positive improvements: {positive_count}/{len(comparisons)}")
    print()
    
    print(f"Average CC (baseline):  {statistics.mean(all_baseline):.3f}")
    print(f"Average CC (ablated):   {statistics.mean(all_ablated):.3f}")
    print()
    
    # Hypothesis validation
    print(f"{'='*80}")
    print("HYPOTHESIS VALIDATION:")
    print(f"{'='*80}\n")
    
    if avg_improvement >= 40:
        print("✓ HYPOTHESIS STRONGLY VALIDATED")
        print(f"  CC improved {avg_improvement:.1f}% (target: ≥40%)")
        print("  RLHF 'be helpful' signal IS the cause of CC failure at c=0.5")
        print("  → Write causal section for ICLR submission")
    elif avg_improvement >= 20:
        print("⚠ PARTIAL SUPPORT")
        print(f"  CC improved {avg_improvement:.1f}% (target: ≥40%)")
        print("  RLHF alignment is ONE contributing factor")
        print("  → Investigate other mechanisms (entropy, training distribution)")
    else:
        print("✗ HYPOTHESIS NOT SUPPORTED")
        print(f"  CC improved only {avg_improvement:.1f}% (target: ≥40%)")
        print("  RLHF not the primary cause")
        print("  → Pivot to alternative explanations")
    
    print(f"\n{'='*80}\n")
    
    # Save comparison to JSON
    output_path = Path("ablation_comparison.json")
    with open(output_path, 'w') as f:
        json.dump({
            "comparisons": comparisons,
            "by_model": {model: {"improvements": improvements, 
                                "average": statistics.mean(improvements)}
                        for model, improvements in by_model.items()},
            "by_concept": {concept: {"improvements": improvements,
                                     "average": statistics.mean(improvements)}
                          for concept, improvements in by_concept.items()},
            "overall": {
                "total_trials": len(comparisons),
                "average_improvement_pct": avg_improvement,
                "median_improvement_pct": median_improvement,
                "min_improvement_pct": min_improvement,
                "max_improvement_pct": max_improvement,
                "positive_improvements": positive_count,
                "hypothesis_validated": avg_improvement >= 40
            }
        }, f, indent=2)
    
    print(f"Detailed results saved to: {output_path}")

if __name__ == "__main__":
    main()
