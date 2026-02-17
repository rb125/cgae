"""
DDFT Framework - The Drill-Down and Fabricate Test

A protocol for measuring epistemic robustness in Large Language Models.

Quick Start:
    from ddft import CognitiveProfiler

    profiler = CognitiveProfiler(model="your-model")
    profile = profiler.run_complete_assessment(
        concepts=["Natural Selection", "Recursion"],
        compression_levels=[0.0, 0.25, 0.5, 0.75, 1.0]
    )

    print(f"CI Score: {profile.ci_score}")
    print(f"Phenotype: {profile.phenotype}")
"""

from ddft import (
    CognitiveProfiler,
    CognitiveProfile,
    InterviewerAgent,
    FabricationTrapGenerator,
    ContextCompressor,
    ConceptLoader,
    LLMJury,
    create_agent,
    __version__
)

__all__ = [
    "CognitiveProfiler",
    "CognitiveProfile",
    "InterviewerAgent",
    "FabricationTrapGenerator",
    "ContextCompressor",
    "ConceptLoader",
    "LLMJury",
    "create_agent",
    "__version__"
]
