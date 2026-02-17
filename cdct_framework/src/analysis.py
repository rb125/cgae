"""
Analysis module - Calculate CSI, C_h, and aggregate statistics
"""
import numpy as np
from scipy import stats
from typing import Dict, Any, List

def analyze_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes CDCT experiment results to calculate CSI and C_h.
    
    FIXED: Now uses abs(slope) instead of max(0, -slope)
    
    Args:
        results: The results dictionary from run_experiment.
    
    Returns:
        Results dict with added 'analysis' section
    """
    performance = results.get("performance", [])
    
    if not performance:
        return {
            **results,
            "analysis": {
                "CSI": None,
                "C_h": None,
                "mean_score": 0.0,
                "error": "No performance data"
            }
        }
    
    scores = np.array([p["score"] for p in performance])

    # =========================================================================
    # Create a continuous compression scale `c` based on information content.
    # This aligns with the paper's formal definition of c ∈ [0,1], where `c`
    # is the fraction of original information retained. We use word count as
    # a proxy for information content, creating a non-linear scale.
    # =========================================================================
    context_lengths = np.array([p.get("context_length", 0) for p in performance])
    max_context_length = np.max(context_lengths) if len(context_lengths) > 0 else 0

    if max_context_length > 0:
        # c_values are the fraction of information retained, where c=1.0 is full info.
        # The levels are sorted from most compressed (L=0) to least (L=max),
        # so the c_values will be sorted in ascending order.
        c_values = context_lengths / max_context_length
    else:
        # Fallback to a linear scale if context length is not available for some reason.
        c_values = np.linspace(0, 1, len(performance))

    # =========================================================================
    # Comprehension Horizon (C_h)
    # Definition: C_h = min{c : P(c) >= threshold}. A lower C_h is better.
    # =========================================================================
    threshold = 0.7
    c_h = None
    
    # Find the minimum c_value where performance meets the threshold.
    # This is the first point on the sorted c_values scale to pass.
    for i, p in enumerate(performance):
        if p["score"] >= threshold:
            c_h = c_values[i]  # C_h is the continuous c-value
            break
    # If no level passes, c_h remains None.

    # =========================================================================
    # Compression Stability Index (CSI)
    # Definition: CSI = |dP/dc|. A lower CSI is better.
    # =========================================================================
    csi = None
    csi_stderr = None
    r_squared = None
    decay_direction = None
    
    if len(c_values) >= 2:
        # Perform linear regression on Performance vs. the continuous `c` value.
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            c_values, scores
        )
        
        csi = abs(slope)
        csi_stderr = std_err
        r_squared = r_value ** 2
        
        # The paper's "decay" refers to performance decaying as compression INCREASES (i.e., as `c` DECREASES).
        # Therefore, a positive slope of Performance vs. `c` is the expected "decay" direction.
        # A negative slope means performance improves with more compression, which is counter-intuitive.
        if slope < -0.1: # Use a threshold to ignore noise around zero
             decay_direction = "improvement" # Counter-intuitive improvement with compression
        else:
             decay_direction = "decay" # Expected decay with compression

    # ============================================================
    # Additional metrics
    # ============================================================
    score_variance = float(np.std(scores)) if len(scores) > 1 else 0.0
    
    analysis = {
        "CSI": float(csi) if csi is not None else None,
        "CSI_stderr": float(csi_stderr) if csi_stderr is not None else None,
        "R_squared": float(r_squared) if r_squared is not None else None,
        "C_h": float(c_h) if c_h is not None else None, # C_h is now a float
        "mean_score": float(np.mean(scores)),
        "score_variance": score_variance,
        "min_score": float(np.min(scores)),
        "max_score": float(np.max(scores)),
        "decay_direction": decay_direction,
        "n_compression_levels": len(c_values)
    }
    
    # ============================================================
    # Validation warnings
    # ============================================================
    warnings = []
    
    if decay_direction == "improvement" and csi > 0.05:
        warnings.append(
            "WARNING: Performance improves significantly with compression. "
            "Model may be ignoring compression constraints or evaluation is too lenient."
        )
    
    if len(c_values) < 3:
        warnings.append(
            "WARNING: Fewer than 3 compression levels. CSI estimate unreliable."
        )
    
    if r_squared is not None and r_squared < 0.3:
        warnings.append(
            f"WARNING: Low R² ({r_squared:.3f}). Non-linear decay pattern. "
            "Consider additional analysis."
        )
    
    # Check for hallucination pattern
    hallucination_count = sum(
        1 for p in performance 
        if p.get('verdict') == 'memorized'
    )
    
    if hallucination_count > len(performance) * 0.5:
        warnings.append(
            f"WARNING: High hallucination rate ({hallucination_count}/{len(performance)}). "
            "Model not respecting compression constraints."
        )
    
    if warnings:
        analysis["warnings"] = warnings
    
    results["analysis"] = analysis
    return results


def analyze_multi_concept(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregates results across multiple concepts for benchmarking.
    
    Args:
        all_results: List of result dicts from multiple concepts
    
    Returns:
        Aggregate statistics (mean CSI, domain breakdown, etc.)
    """
    csi_values = []
    c_h_values = []
    domains = {}
    
    for result in all_results:
        analysis = result.get("analysis", {})
        csi = analysis.get("CSI")
        c_h = analysis.get("C_h")
        domain = result.get("domain", "unknown")
        
        if csi is not None:
            csi_values.append(csi)
            
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(csi)
        
        if c_h is not None:
            c_h_values.append(c_h)
    
    aggregate = {
        "model": all_results[0]["model"] if all_results else None,
        "n_concepts": len(all_results),
        "mean_CSI": float(np.mean(csi_values)) if csi_values else None,
        "CSI_std": float(np.std(csi_values)) if len(csi_values) > 1 else None,
        "mean_C_h": float(np.mean(c_h_values)) if c_h_values else None,
        "domain_breakdown": {
            domain: {
                "mean_CSI": float(np.mean(csi_list)),
                "std_CSI": float(np.std(csi_list)) if len(csi_list) > 1 else 0,
                "n_concepts": len(csi_list)
            }
            for domain, csi_list in domains.items()
        }
    }
    
    return aggregate