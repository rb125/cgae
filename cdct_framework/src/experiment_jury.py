"""
Jury-based experiment runner - Orchestrates CDCT experiments with LLM jury evaluation
Replaces mechanical evaluation with 3-judge consensus system
"""
from typing import Dict, Any, List, Optional
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    from . import concept as concept_loader
    from . import agent as agent_loader
    from .llm_jury import LLMJury
    from .prompting import create_compression_aware_prompt, create_few_shot_prompt, create_simple_prompt, create_minimal_prompt
    from .analysis import analyze_results
except ImportError:
    # Fallback for direct execution
    import concept as concept_loader
    import agent as agent_loader
    from llm_jury import LLMJury
    from prompting import create_compression_aware_prompt, create_few_shot_prompt, create_simple_prompt, create_minimal_prompt
    from analysis import analyze_results


def run_experiment_with_jury(
    concept_path: str,
    subject_agent: agent_loader.Agent,
    jury_agents: Dict[str, agent_loader.Agent],
    prompt_strategy: str = "compression_aware",
    ablation_type: Optional[str] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Runs CDCT experiment with jury-based evaluation.
    
    Args:
        concept_path: Path to concept JSON file
        subject_agent: Agent being tested (subject)
        jury_agents: Dict of judge_name -> Agent for jury members
        prompt_strategy: "compression_aware", "few_shot", or "simple"
        ablation_type: "no_helpfulness" for RLHF ablation, None for baseline
        verbose: Print progress
    
    Returns:
        Complete results dictionary with jury evaluations
    """
    # Load concept
    loaded_concept = concept_loader.load_concept(concept_path)
    
    # Initialize jury
    jury = LLMJury(judges=jury_agents)
    
    results = {
        "concept": loaded_concept.concept,
        "domain": loaded_concept.domain,
        "subject_model": subject_agent.model_name,
        "jury_models": list(jury_agents.keys()),
        "evaluation_system": "jury",
        "prompt_strategy": prompt_strategy,
        "ablation_type": ablation_type,
        "performance": [],
        "failed_levels": []
    }
    
    max_compression = max(step.compression_level for step in loaded_concept.corpus)
    full_text = next(
        (step.text for step in loaded_concept.corpus 
        if step.compression_level == max_compression), 
        ""
    )
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"CDCT Jury Experiment: {loaded_concept.concept} ({loaded_concept.domain})")
        print(f"Subject Model: {subject_agent.model_name}")
        print(f"Jury Members: {', '.join(jury_agents.keys())}")
        print(f"Strategy: {prompt_strategy}")
        if ablation_type:
            print(f"Ablation Type: {ablation_type}")
        print(f"{'='*70}\n")
    
    for step in loaded_concept.corpus:
        level = step.compression_level
        text = step.text
        question = step.probes.get("recall", "")
        expected = step.expected_keywords
        
        # Create prompt based on strategy
        if prompt_strategy == "compression_aware":
            # Apply ablation if requested
            if ablation_type == "no_helpfulness":
                prompt = create_minimal_prompt(text, question)
            else:
                prompt = create_compression_aware_prompt(text, question, level, max_compression)
        elif prompt_strategy == "few_shot":
            prompt = create_few_shot_prompt(text, question, level)
        else:  # simple
            prompt = create_simple_prompt(text, question)
        
        if verbose:
            print(f"Compression {level}/{max_compression} | Context: {len(text.split())} words")
        
        # Query subject model
        try:
            response = subject_agent.query(prompt)
        except Exception as e:
            print(f"ERROR querying subject model: {e}")
            response = f"Error: {e}"

        # If the response is None or a technical error, log it and skip
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
        
        # Run jury evaluation
        if verbose:
            print(f"  Subject response: {len(response.split())} words")
        
        jury_result = jury.evaluate_response(
            subject_response=response,
            compression_level=level / max_compression,
            question_asked=question,
            context=text,
            expected_keywords=expected
        )
        
        consensus = jury_result["consensus"]
        
        # Format results
        performance_entry = {
            "compression_level": level,
            "context_length": len(text.split()),
            "response_length": len(response.split()),
            "response": response,
            "jury_evaluation": jury_result
        }
        
        # Compute overall score for backwards compatibility with analysis
        # Check for new metrics (CC/SA) or old metrics (FAR/SAS)
        cc_or_far = consensus.get("CC") or consensus.get("FAR")
        sa_or_sas = consensus.get("SA") or consensus.get("SAS")
        
        if cc_or_far is not None and sa_or_sas is not None:
            # Weighted combination: CC and SA weighted equally, FC secondary
            overall_score = (
                cc_or_far * 0.4 +
                sa_or_sas * 0.4 +
                consensus.get("FC", 0.5) * 0.2
            )
            performance_entry["score"] = overall_score
            
            if verbose:
                cc_label = "CC" if consensus.get("CC") is not None else "FAR"
                sa_label = "SA" if consensus.get("SA") is not None else "SAS"
                print(f"  Jury Consensus: {cc_label}={cc_or_far:.3f}, {sa_label}={sa_or_sas:.3f}, "
                      f"FC={consensus.get('FC', '?'):.3f}")
                print(f"  Agreement: {consensus.get('agreement_score', 0.0):.3f} - "
                      f"{consensus.get('recommendation', 'Unknown')}")
                print(f"  Overall Score: {overall_score:.3f}")
        else:
            performance_entry["score"] = 0.0
            if verbose:
                error_msg = consensus.get('error', 'Unknown error')
                print(f"  ✗ Jury evaluation failed: {error_msg}")
                if 'error' not in consensus:
                    print(f"    Consensus keys: {list(consensus.keys())}")
        
        results["performance"].append(performance_entry)
    
    # Analyze results (compute CSI, etc.)
    # Note: We need to adapt analysis to work with jury scores
    results = _analyze_jury_results(results)
    
    if verbose:
        print(f"\n{'='*70}")
        print("JURY EVALUATION RESULTS:")
        print(f"  Mean Score: {results['analysis']['mean_score']:.3f}")
        print(f"  CSI: {results['analysis']['CSI']:.4f}")
        print(f"  Mean Agreement: {results['analysis']['mean_agreement']:.3f}")
        print(f"  Direction: {results['analysis']['decay_direction']}")
        print(f"{'='*70}\n")
    
    return results


def _analyze_jury_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze jury-based results.
    Computes CSI, mean score, agreement metrics, etc.
    """
    performance = results["performance"]
    
    if not performance:
        results["analysis"] = {
            "CSI": 0.0,
            "mean_score": 0.0,
            "mean_agreement": 0.0,
            "decay_direction": "N/A",
            "error": "No valid performance data"
        }
        return results
    
    scores = [p.get("score", 0.0) for p in performance]
    compression_levels = [p["compression_level"] for p in performance]
    
    # Extract agreement scores
    agreements = []
    for p in performance:
        jury_eval = p.get("jury_evaluation", {})
        consensus = jury_eval.get("consensus", {})
        agreement = consensus.get("agreement_score", 0.0)
        if agreement > 0:
            agreements.append(agreement)
    
    mean_score = sum(scores) / len(scores) if scores else 0.0
    mean_agreement = sum(agreements) / len(agreements) if agreements else 0.0
    
    # Compute CSI (Compression Stability Index)
    # Lower compression (higher compression_level) should have higher scores
    high_compression_scores = [s for s, c in zip(scores, compression_levels) if c >= max(compression_levels) * 0.5]
    low_compression_scores = [s for s, c in zip(scores, compression_levels) if c < min(compression_levels) * 0.75]
    
    csi = 0.0
    if high_compression_scores and low_compression_scores:
        # CSI measures how well model maintains performance across compression levels
        avg_high = sum(high_compression_scores) / len(high_compression_scores)
        avg_low = sum(low_compression_scores) / len(low_compression_scores)
        csi = avg_high - avg_low  # Positive = good (maintains performance even with less context)
    
    # Determine decay direction
    if len(scores) >= 2:
        early_avg = sum(scores[:len(scores)//2]) / (len(scores)//2) if len(scores) >= 2 else scores[0]
        late_avg = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2) if len(scores) >= 2 else scores[-1]
        
        if early_avg > late_avg + 0.05:
            decay_direction = "↓ Graceful (expected)"
        elif early_avg < late_avg - 0.05:
            decay_direction = "↑ Improvement with compression"
        else:
            decay_direction = "→ Stable"
    else:
        decay_direction = "N/A"
    
    results["analysis"] = {
        "CSI": csi,
        "mean_score": mean_score,
        "mean_agreement": mean_agreement,
        "decay_direction": decay_direction,
        "compression_levels": compression_levels,
        "scores": scores,
        "agreement_scores": agreements
    }
    
    return results


def compare_jury_strategies(concept_path: str, subject_agent, jury_agents: Dict) -> Dict:
    """
    Compare different prompt strategies with jury evaluation.
    
    Args:
        concept_path: Path to concept JSON
        subject_agent: Agent being tested
        jury_agents: Dict of jury member agents
    
    Returns:
        Dict mapping strategy names to results
    """
    strategies = ["simple", "compression_aware", "few_shot"]
    results = {}
    
    for strategy in strategies:
        print(f"\n{'#'*70}")
        print(f"Jury Evaluation - Strategy: {strategy.upper()}")
        print(f"{'#'*70}")
        
        result = run_experiment_with_jury(
            concept_path, 
            subject_agent,
            jury_agents,
            prompt_strategy=strategy,
            verbose=True
        )
        results[strategy] = result
    
    # Compare
    print(f"\n{'='*70}")
    print("JURY-BASED STRATEGY COMPARISON")
    print(f"{'='*70}")
    for strategy, result in results.items():
        csi = result['analysis']['CSI']
        mean_score = result['analysis']['mean_score']
        mean_agreement = result['analysis']['mean_agreement']
        print(f"{strategy:20s}: CSI={csi:.4f}, Mean Score={mean_score:.3f}, Jury Agreement={mean_agreement:.3f}")
    
    return results
