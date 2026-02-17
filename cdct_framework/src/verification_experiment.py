"""
CDCT 2.0 Verification Experiment

Tests whether the compression benefit artifact is resolved by constraint-aware judging.

This script runs a controlled experiment:
1. Evaluate 3 models on 3 concepts using ORIGINAL judges (baseline)
2. Evaluate same models/concepts using FIXED judges (constraint-aware)
3. Compare results to determine if compression paradox persists

Expected outcomes:
- If FIXED shows decay → Artifact was due to judge prompting (HYPOTHESIS CONFIRMED)
- If FIXED still shows improvement → Compression benefit is real (MAJOR FINDING)
"""

import sys
import os
import json
from datetime import datetime

# Assuming these imports work from your existing setup
from agent import create_agent
from experiment_jury import run_experiment_with_jury
from llm_jury import LLMJury as OriginalJury
from llm_jury_fixed import LLMJury as FixedJury


def run_verification_experiment(
    concepts: list,  # List of concept file paths
    subject_models: list,  # List of (model_name, deployment_name) tuples
    output_dir: str = "verification_results"
):
    """
    Run verification experiment comparing original vs. fixed jury evaluation.
    
    Args:
        concepts: List of paths to concept JSON files
        subject_models: List of (model, deployment) tuples for subject models
        output_dir: Directory to save results
    """
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize jury agents (same for both configurations)
    print("="*80)
    print("INITIALIZING JURY MEMBERS")
    print("="*80)
    
    jury_agents = {
        "claude-opus-4-1-2": create_agent("claude-opus-4-1-2", "claude-opus-4-1-2-deployment"),
        "gpt-5.1": create_agent("gpt-5.1", "gpt-5-1-deployment"),
        "deepseek-v3.1": create_agent("deepseek-v3.1", "deepseek-v3-1-deployment")
    }
    
    print("✓ Jury initialized\n")
    
    # Results storage
    results = {
        "timestamp": datetime.now().isoformat(),
        "experiment_type": "verification",
        "hypothesis": "Compression benefit is artifact of context-blind judge evaluation",
        "comparisons": []
    }
    
    # Run experiments for each (model, concept) pair
    for model_name, deployment_name in subject_models:
        print("\n" + "="*80)
        print(f"SUBJECT MODEL: {model_name}")
        print("="*80 + "\n")
        
        subject_agent = create_agent(model_name, deployment_name)
        
        for concept_path in concepts:
            concept_name = os.path.basename(concept_path).replace('.json', '')
            
            print(f"\n{'─'*80}")
            print(f"CONCEPT: {concept_name}")
            print(f"{'─'*80}\n")
            
            # ============================================================
            # RUN 1: Original jury (context-blind)
            # ============================================================
            print("▶ Running with ORIGINAL jury (context-blind)...")
            
            original_jury = OriginalJury(judges=jury_agents)
            
            # Temporarily replace the jury in experiment
            original_result = _run_with_specific_jury(
                concept_path=concept_path,
                subject_agent=subject_agent,
                jury=original_jury,
                jury_agents=jury_agents,
                verbose=False
            )
            
            print(f"  Original Mean Score: {original_result['analysis']['mean_score']:.4f}")
            print(f"  Original CSI: {original_result['analysis']['CSI']:.4f}")
            print(f"  Original Direction: {original_result['analysis']['decay_direction']}")
            
            # ============================================================
            # RUN 2: Fixed jury (constraint-aware)
            # ============================================================
            print("\n▶ Running with FIXED jury (constraint-aware)...")
            
            fixed_jury = FixedJury(judges=jury_agents)
            
            fixed_result = _run_with_specific_jury(
                concept_path=concept_path,
                subject_agent=subject_agent,
                jury=fixed_jury,
                jury_agents=jury_agents,
                verbose=False
            )
            
            print(f"  Fixed Mean Score: {fixed_result['analysis']['mean_score']:.4f}")
            print(f"  Fixed CSI: {fixed_result['analysis']['CSI']:.4f}")
            print(f"  Fixed Direction: {fixed_result['analysis']['decay_direction']}")
            
            # ============================================================
            # Compare
            # ============================================================
            comparison = {
                "model": model_name,
                "concept": concept_name,
                "original": {
                    "mean_score": original_result['analysis']['mean_score'],
                    "csi": original_result['analysis']['CSI'],
                    "direction": original_result['analysis']['decay_direction'],
                    "scores": original_result['analysis']['scores']
                },
                "fixed": {
                    "mean_score": fixed_result['analysis']['mean_score'],
                    "csi": fixed_result['analysis']['CSI'],
                    "direction": fixed_result['analysis']['decay_direction'],
                    "scores": fixed_result['analysis']['scores']
                }
            }
            
            # Compute delta
            delta_mean = fixed_result['analysis']['mean_score'] - original_result['analysis']['mean_score']
            delta_csi = fixed_result['analysis']['CSI'] - original_result['analysis']['CSI']
            
            comparison["delta_mean_score"] = delta_mean
            comparison["delta_csi"] = delta_csi
            
            # Determine verdict
            original_improves = "↑" in original_result['analysis']['decay_direction']
            fixed_improves = "↑" in fixed_result['analysis']['decay_direction']
            
            if original_improves and not fixed_improves:
                verdict = "ARTIFACT CONFIRMED - Fix resolved compression benefit"
            elif original_improves and fixed_improves:
                verdict = "REAL PHENOMENON - Compression benefit persists with fix"
            elif not original_improves and not fixed_improves:
                verdict = "CONSISTENT DECAY - Both show expected behavior"
            else:
                verdict = "ANOMALY - Original showed decay, fixed shows improvement"
            
            comparison["verdict"] = verdict
            
            print(f"\n  ▶ VERDICT: {verdict}")
            print(f"  ▶ Δ Mean Score: {delta_mean:+.4f}")
            print(f"  ▶ Δ CSI: {delta_csi:+.4f}")
            
            results["comparisons"].append(comparison)
            
            # Save intermediate results
            with open(f"{output_dir}/verification_partial.json", 'w') as f:
                json.dump(results, f, indent=2)
    
    # ============================================================
    # Final Analysis
    # ============================================================
    print("\n" + "="*80)
    print("VERIFICATION EXPERIMENT RESULTS")
    print("="*80 + "\n")
    
    artifact_count = sum(1 for c in results["comparisons"] if "ARTIFACT" in c["verdict"])
    real_count = sum(1 for c in results["comparisons"] if "REAL" in c["verdict"])
    total = len(results["comparisons"])
    
    print(f"Total comparisons: {total}")
    print(f"Artifact confirmed: {artifact_count} ({100*artifact_count/total:.1f}%)")
    print(f"Real phenomenon: {real_count} ({100*real_count/total:.1f}%)")
    
    if artifact_count > real_count:
        final_verdict = "HYPOTHESIS CONFIRMED: Compression benefit was an artifact of judge prompting"
        recommendation = "Use FIXED jury for all future experiments. Re-run full CDCT 2.0 evaluation."
    elif real_count > artifact_count:
        final_verdict = "HYPOTHESIS REJECTED: Compression benefit is a real phenomenon"
        recommendation = "Investigate mechanistic causes (attention efficiency, training distribution, etc.)"
    else:
        final_verdict = "INCONCLUSIVE: Mixed results across models/concepts"
        recommendation = "Expand verification to more models and concepts"
    
    print(f"\n{final_verdict}")
    print(f"\nRECOMMENDATION: {recommendation}")
    
    results["final_verdict"] = final_verdict
    results["recommendation"] = recommendation
    
    # Save final results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output_dir}/verification_results_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_file}")
    
    return results


def _run_with_specific_jury(concept_path, subject_agent, jury, jury_agents, verbose=False):
    """Helper to run experiment with a specific jury instance."""
    # This is a bit hacky - we need to modify experiment_jury.py to accept
    # a jury instance rather than creating its own
    # For now, we'll inline the logic
    
    from concept import load_concept
    from prompting import create_compression_aware_prompt
    
    loaded_concept = load_concept(concept_path)
    
    results = {
        "concept": loaded_concept.concept,
        "domain": loaded_concept.domain,
        "subject_model": subject_agent.model_name,
        "jury_models": list(jury_agents.keys()),
        "performance": []
    }
    
    max_compression = max(step.compression_level for step in loaded_concept.corpus)
    
    for step in loaded_concept.corpus:
        level = step.compression_level
        text = step.text
        question = step.probes.get("recall", "")
        expected = step.expected_keywords
        
        # Create prompt
        prompt = create_compression_aware_prompt(text, question, level, max_compression)
        
        # Query subject model
        try:
            response = subject_agent.query(prompt)
            if not response:
                continue
        except:
            continue
        
        # Run jury evaluation with the specific jury instance
        jury_result = jury.evaluate_response(
            subject_response=response,
            compression_level=level / max_compression,
            question_asked=question,
            context=text,
            expected_keywords=expected
        )
        
        consensus = jury_result["consensus"]
        
        # Compute overall score
        overall_score = (
            consensus.get("FAR", 0.5) * 0.4 +
            consensus.get("SAS", 0.5) * 0.4 +
            consensus.get("FC", 0.5) * 0.2
        )
        
        results["performance"].append({
            "compression_level": level,
            "score": overall_score,
            "jury_evaluation": jury_result
        })
    
    # Analyze
    from experiment_jury import _analyze_jury_results
    results = _analyze_jury_results(results)
    
    return results


# ============================================================
# Example Usage
# ============================================================

if __name__ == "__main__":
    # Configure your verification experiment
    concepts = [
        "concepts/mathematics_derivative.json",
        "concepts/physics_f_equals_ma.json",
        "concepts/ethics_harm_principle.json"
    ]
    
    subject_models = [
        ("gpt-5", "gpt-5-deployment"),
        ("claude-haiku-4-5", "haiku-deployment"),
        ("phi-4", "phi-4-deployment")
    ]
    
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║              CDCT 2.0 VERIFICATION EXPERIMENT                      ║
║                                                                    ║
║  Testing whether compression benefit is an artifact of judge       ║
║  prompting or a real phenomenon.                                   ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    results = run_verification_experiment(
        concepts=concepts,
        subject_models=subject_models,
        output_dir="verification_results"
    )
    
    print("\n✓ Verification experiment complete!")
