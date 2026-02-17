"""
Quick Start Example - Running DDFT evaluation as shown in the paper.

This demonstrates the streamlined API from the paper's Quick Start section.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ddft import CognitiveProfiler


def main():
    """
    Run a simple DDFT evaluation on a subject model.

    This reproduces the Quick Start example from the paper.
    """
    print("DDFT Quick Start Example")
    print("=" * 70)

    # Configure the model to test
    # You can use a simple model name or a full configuration dict
    model_config = {
        "model_name": "gpt-4",
        "deployment_name": "gpt-4",
        "provider": "azure_openai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT"
    }

    # Create the profiler
    profiler = CognitiveProfiler(model=model_config)

    # Run assessment on select concepts
    # (Using 2 concepts for quick demo - paper uses all 8)
    profile = profiler.run_complete_assessment(
        concepts=["Natural Selection", "Recursion"],
        compression_levels=[0.0, 0.25, 0.5, 0.75, 1.0]
    )

    # Display results
    print("\n" + "=" * 70)
    print("COGNITIVE PROFILE RESULTS")
    print("=" * 70)
    print(f"Model: {profile.model_name}")
    print(f"CI Score: {profile.ci_score:.3f}")
    print(f"Phenotype: {profile.phenotype}")
    print(f"Danger Zone Rate: {profile.danger_zone_pct:.1f}%")
    print()
    print("Component Metrics:")
    print(f"  HOC (Hallucination Onset Compression): {profile.hoc:.3f}")
    print(f"  FG (Fabrication Gradient): {profile.fg:.3f}")
    print(f"  Decay Smoothness: {profile.decay_smoothness:.3f}")
    print(f"  MCA (Meta-Cognitive Awareness): {profile.mca:.3f}")
    print()
    print(f"Evaluations: {profile.num_evaluations} turns")
    print(f"Concepts tested: {', '.join(profile.concepts_tested)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
