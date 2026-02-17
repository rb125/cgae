"""
Experiment runner - Orchestrates CDCT experiments
"""
from typing import Dict, Any
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    from . import concept as concept_loader
    from . import agent as agent_loader
    from .evaluation import evaluate_response_comprehensive
    from .prompting import create_compression_aware_prompt, create_few_shot_prompt, create_simple_prompt
    from .analysis import analyze_results
except ImportError:
    # Fallback for direct execution
    import concept as concept_loader
    import agent as agent_loader
    from evaluation import evaluate_response_comprehensive
    from prompting import create_compression_aware_prompt, create_few_shot_prompt, create_simple_prompt
    from analysis import analyze_results

def run_experiment(
    concept_path: str,
    agent: agent_loader.Agent,
    prompt_strategy: str = "compression_aware",
    evaluation_mode: str = "balanced",
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Runs complete CDCT experiment with integrated improvements.
    
    Args:
        concept_path: Path to concept JSON file
        agent: Agent instance (must have .query() method)
        prompt_strategy: "compression_aware", "few_shot", or "simple"
        evaluation_mode: "strict", "balanced", or "lenient"
        verbose: Print progress
    
    Returns:
        Complete results dictionary with analysis
    """
    # Load concept
    loaded_concept = concept_loader.load_concept(concept_path)
    
    results = {
        "concept": loaded_concept.concept,
        "domain": loaded_concept.domain,
        "model": agent.model_name,
        "prompt_strategy": prompt_strategy,
        "evaluation_mode": evaluation_mode,
        "performance": [],
        "failed_levels": [] # Log technical failures separately
    }
    
    max_compression = max(step.compression_level for step in loaded_concept.corpus)
    full_text = next(
        (step.text for step in loaded_concept.corpus 
        if step.compression_level == max_compression), 
        ""
    )
    if verbose:
        print(f"\n{'='*70}")
        print(f"CDCT Experiment: {loaded_concept.concept} ({loaded_concept.domain})")
        print(f"Model: {agent.model_name}")
        print(f"Strategy: {prompt_strategy} | Evaluation: {evaluation_mode}")
        print(f"{'='*70}\n")
    
    for step in loaded_concept.corpus:
        level = step.compression_level
        text = step.text
        question = step.probes.get("recall", "") # Default to empty string if recall probe not found
        expected = step.expected_keywords
        
        # Create prompt based on strategy
        if prompt_strategy == "compression_aware":
            prompt = create_compression_aware_prompt(text, question, level, max_compression)
        elif prompt_strategy == "few_shot":
            prompt = create_few_shot_prompt(text, question, level)
        else:  # simple
            prompt = create_simple_prompt(text, question)
        
        if verbose:
            print(f"Compression {level}/{max_compression} | Context: {len(text.split())} words")
        
        # Query model
        try:
            response = agent.query(prompt)
        except Exception as e:
            print(f"ERROR querying model: {e}")
            response = f"Error: {e}"

        # If the response is None or a technical error, log it and skip.
        if not response or response.strip().startswith("Error:"):
            error_message = response.strip() if response else "Model returned a None response"
            if verbose:
                print(f"  FAILED level {level} due to model error: {error_message}")
            results["failed_levels"].append({
                "compression_level": level,
                "context_length": len(text.split()),
                "error": error_message
            })
            continue
        
        # Evaluate with comprehensive method
        eval_result = evaluate_response_comprehensive(
            response=response,
            expected_keywords=expected,
            available_context=text,
            compression_level=level,
            max_compression_level=max_compression,
            evaluation_mode=evaluation_mode,
            full_concept_text=full_text
        )
        
        results["performance"].append({
            "compression_level": level,
            "context_length": len(text.split()),
            "response_length": len(response.split()),
            "score": eval_result['final_score'],
            "verdict": eval_result['verdict'],
            "hallucinated": eval_result['components']['strict']['hallucinated'],
            "response": response,
            "detailed_eval": eval_result
        })
        
        if verbose:
            print(f"  Score: {eval_result['final_score']:.3f} | "
                  f"Verdict: {eval_result['verdict']} | "
                  f"Response: {len(response.split())} words")
            if eval_result['components']['strict']['hallucinated']:
                print(f"  ⚠ Hallucinated: {eval_result['components']['strict']['hallucinated']}")
    
    # Analyze results
    results = analyze_results(results)
    
    if verbose:
        print(f"\n{'='*70}")
        print("RESULTS:")
        print(f"  CSI: {results['analysis']['CSI']:.4f}")
        print(f"  C_h: {results['analysis']['C_h']}")
        print(f"  Mean Score: {results['analysis']['mean_score']:.3f}")
        print(f"  Direction: {results['analysis']['decay_direction']}")
        
        if 'warnings' in results['analysis']:
            print(f"\n  WARNINGS:")
            for w in results['analysis']['warnings']:
                print(f"    • {w}")
        print(f"{'='*70}\n")
    
    return results


def quick_test(concept_path: str, agent, save_path: str = None):
    """
    Quick test with default settings.
    
    Args:
        concept_path: Path to concept JSON
        agent: Agent instance
        save_path: Optional path to save results
    
    Returns:
        Results dictionary
    """
    results = run_experiment(
        concept_path=concept_path,
        agent=agent,
        prompt_strategy="compression_aware",
        evaluation_mode="balanced",
        verbose=True
    )
    
    if save_path:
        with open(save_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {save_path}")
    
    return results


def compare_strategies(concept_path: str, agent):
    """
    Compare different prompt strategies.
    
    Args:
        concept_path: Path to concept JSON
        agent: Agent instance
    
    Returns:
        Dict mapping strategy names to results
    """
    strategies = ["simple", "compression_aware", "few_shot"]
    results = {}
    
    for strategy in strategies:
        print(f"\n{'#'*70}")
        print(f"Testing Strategy: {strategy.upper()}")
        print(f"{'#'*70}")
        
        result = run_experiment(
            concept_path, agent, 
            prompt_strategy=strategy,
            verbose=True
        )
        results[strategy] = result
    
    # Compare
    print(f"\n{'='*70}")
    print("STRATEGY COMPARISON")
    print(f"{'='*70}")
    for strategy, result in results.items():
        csi = result['analysis']['CSI']
        mean_score = result['analysis']['mean_score']
        print(f"{strategy:20s}: CSI={csi:.4f}, Mean Score={mean_score:.3f}")
    
    return results