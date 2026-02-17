"""
Quick verification script to test CC/SA separation.

Tests the hypothesis:
- CC should show U-curve (high at extremes, low at medium)
- SA should show monotonic decay (high at c=1.0, lower at c=0.0)
- These are independent dimensions

Run on 1-2 models × 1 concept to validate before full re-run.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from llm_jury import LLMJury
from agent import create_agent

def analyze_separated_metrics(results_file: str):
    """
    Analyze a jury results file and separate CC vs SA patterns.
    
    Args:
        results_file: Path to JSON file with jury results
    """
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    print("="*80)
    print(f"SEPARATED METRICS ANALYSIS: {data['subject_model']} - {data['concept']}")
    print("="*80)
    
    # Extract metrics
    compression_levels = []
    cc_scores = []
    sa_scores = []
    fc_scores = []
    response_lengths = []
    
    for perf in data['performance']:
        c_level = perf['compression_level']
        consensus = perf['jury_evaluation']['consensus']
        
        compression_levels.append(c_level)
        cc_scores.append(consensus.get('CC', 0.0))
        sa_scores.append(consensus.get('SA', 0.0))
        fc_scores.append(consensus.get('FC', 0.0))
        response_lengths.append(perf['response_length'])
    
    # Print table
    print("\n{:<15} {:<12} {:<12} {:<12} {:<12}".format(
        "Compression", "CC", "SA", "FC", "Length"
    ))
    print("-"*80)
    
    for i, c in enumerate(compression_levels):
        print("{:<15} {:<12.3f} {:<12.3f} {:<12.3f} {:<12}".format(
            f"{c:.2f}",
            cc_scores[i],
            sa_scores[i],
            fc_scores[i],
            response_lengths[i]
        ))
    
    # Analyze patterns
    print("\n" + "="*80)
    print("PATTERN ANALYSIS")
    print("="*80)
    
    # CC pattern (expect U-curve)
    cc_extreme_avg = (cc_scores[0] + cc_scores[-1]) / 2  # Average of c=0.0 and c=1.0
    cc_medium_avg = sum(cc_scores[1:-1]) / len(cc_scores[1:-1]) if len(cc_scores) > 2 else 0
    
    print(f"\nCC (Constraint Compliance):")
    print(f"  Extreme compression avg (c=0.0, c=1.0): {cc_extreme_avg:.3f}")
    print(f"  Medium compression avg (c=0.25-0.75): {cc_medium_avg:.3f}")
    print(f"  Difference: {cc_extreme_avg - cc_medium_avg:+.3f}")
    
    if cc_extreme_avg > cc_medium_avg + 0.1:
        print(f"  → U-CURVE CONFIRMED: High compliance at extremes, low at medium")
    elif abs(cc_extreme_avg - cc_medium_avg) < 0.1:
        print(f"  → FLAT: Consistent compliance across compression levels")
    else:
        print(f"  → INVERSE U: Lower compliance at extremes")
    
    # SA pattern (expect monotonic improvement or decay)
    sa_delta = sa_scores[-1] - sa_scores[0]  # c=1.0 - c=0.0
    
    print(f"\nSA (Semantic Accuracy):")
    print(f"  At c=0.0 (extreme compression): {sa_scores[0]:.3f}")
    print(f"  At c=1.0 (minimal compression): {sa_scores[-1]:.3f}")
    print(f"  Delta: {sa_delta:+.3f}")
    
    if sa_delta > 0.1:
        print(f"  → MONOTONIC IMPROVEMENT: Accuracy increases with context")
    elif abs(sa_delta) < 0.1:
        print(f"  → STABLE: Consistent accuracy across compression")
    else:
        print(f"  → MONOTONIC DECAY: Accuracy decreases with context (unexpected)")
    
    # Check for correlation between CC and SA
    # Simple correlation: do they move together?
    cc_var = sum((x - sum(cc_scores)/len(cc_scores))**2 for x in cc_scores)
    sa_var = sum((x - sum(sa_scores)/len(sa_scores))**2 for x in sa_scores)
    
    if cc_var > 0.01 and sa_var > 0.01:  # Both have variance
        cc_mean = sum(cc_scores)/len(cc_scores)
        sa_mean = sum(sa_scores)/len(sa_scores)
        covar = sum((cc_scores[i] - cc_mean)*(sa_scores[i] - sa_mean) 
                   for i in range(len(cc_scores)))
        correlation = covar / (len(cc_scores) * (cc_var * sa_var)**0.5)
        
        print(f"\nCC-SA Correlation: {correlation:.3f}")
        if abs(correlation) < 0.3:
            print(f"  → ORTHOGONAL: CC and SA are independent dimensions ✓")
        elif correlation > 0.5:
            print(f"  → POSITIVE: High compliance → high accuracy")
        else:
            print(f"  → NEGATIVE: High compliance → low accuracy (paradoxical)")
    
    # Response length vs CC
    print(f"\nResponse Length vs CC:")
    for i, c in enumerate(compression_levels):
        if c < 0.6:  # Only check constrained levels
            expected_limit = 20 if c < 0.3 else 50
            violation_ratio = response_lengths[i] / expected_limit
            print(f"  c={c:.2f}: {response_lengths[i]:3d} words "
                  f"(limit: {expected_limit}, ratio: {violation_ratio:.1f}×, CC: {cc_scores[i]:.2f})")
    
    print("\n" + "="*80)


def test_separation_on_existing_data():
    """
    Test metric separation on the existing gpt-5/phi-4 derivative data.
    
    This shows what the separated metrics WOULD look like if we re-ran
    with the new jury prompts.
    """
    print("\n" + "#"*80)
    print("# TESTING METRIC SEPARATION ON EXISTING DATA")
    print("#"*80)
    
    # Note: Existing data has FAR/SAS/FC, not CC/SA/FC
    # We'll analyze conceptually what separation would reveal
    
    files = [
        ("../results_jury/jury_results_mathematics_derivative_gpt-5_compression_aware.json", "GPT-5"),
        ("../results_jury/jury_results_mathematics_derivative_phi-4_compression_aware.json", "Phi-4")
    ]
    
    for filepath, model_name in files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            print(f"\n{'='*80}")
            print(f"MODEL: {model_name} - DERIVATIVE CONCEPT")
            print(f"{'='*80}")
            
            print("\n{:<10} {:<8} {:<10} {:<10} {:<10} {:<12}".format(
                "Level", "Context", "Response", "FAR", "SAS", "FC"
            ))
            print("-"*80)
            
            for perf in data['performance']:
                c = perf['compression_level']
                ctx_len = perf['context_length']
                resp_len = perf['response_length']
                consensus = perf['jury_evaluation']['consensus']
                
                far = consensus.get('FAR', 0)
                sas = consensus.get('SAS', 0)
                fc = consensus.get('FC', 0)
                
                print(f"{c:<10.2f} {ctx_len:<8d} {resp_len:<10d} {far:<10.3f} {sas:<10.3f} {fc:<10.3f}")
            
            # Hypothesize what CC vs SA would be
            print(f"\n{'─'*80}")
            print("HYPOTHESIZED SEPARATION (if we had CC/SA):")
            print(f"{'─'*80}")
            
            for perf in data['performance']:
                c = perf['compression_level']
                resp_len = perf['response_length']
                consensus = perf['jury_evaluation']['consensus']
                far = consensus.get('FAR', 0)
                
                # Hypothesis: FAR was conflating CC and SA
                # At medium compression with long responses, low FAR likely means:
                # - Low CC (violated length constraint)
                # - But SA could be higher (content might be accurate)
                
                if c < 0.3:
                    expected_limit = 20
                elif c < 0.6:
                    expected_limit = 50
                else:
                    expected_limit = None
                
                if expected_limit:
                    violation = resp_len / expected_limit
                    # Estimate CC based on violation
                    if violation < 1.2:
                        est_cc = 1.0
                    elif violation < 2.0:
                        est_cc = 0.7
                    elif violation < 3.0:
                        est_cc = 0.4
                    else:
                        est_cc = 0.2
                    
                    # Estimate SA: if FAR was low due to violation, SA might be higher
                    # (We'd need re-evaluation to know for sure)
                    if far < 0.5 and violation > 2.0:
                        est_sa = far + 0.3  # Hypothetical correction
                    else:
                        est_sa = far
                    
                    print(f"c={c:.2f}: Response {resp_len}w (limit {expected_limit}w, {violation:.1f}× over)")
                    print(f"  Current FAR: {far:.2f}")
                    print(f"  → Estimated CC: {est_cc:.2f} (constraint compliance)")
                    print(f"  → Estimated SA: {min(est_sa, 1.0):.2f} (semantic accuracy)")
                    print()
        
        except FileNotFoundError:
            print(f"File not found: {filepath}")
            print("Place test files in current directory to analyze.")


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║           CC/SA SEPARATION VERIFICATION SCRIPT                     ║
║                                                                    ║
║  This script analyzes how separating Constraint Compliance (CC)    ║
║  from Semantic Accuracy (SA) changes CDCT interpretation.          ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    test_separation_on_existing_data()
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("""
1. Update experiment_jury.py to use llm_jury_fixed_v2.py
2. Re-run 2-3 models × 2-3 concepts with separated metrics
3. Analyze results to confirm:
   - CC shows U-curve pattern
   - SA shows monotonic pattern (decay or improvement)
   - CC and SA are orthogonal (low correlation)
4. Write CDCT 2.0 paper with both findings:
   - U-shaped constraint compliance gap
   - Compression-dependent semantic accuracy
   - Jury disagreement as brittleness signal
    """)
