"""
DDFT - The Drill-Down and Fabricate Test

Main module providing the public API for DDFT evaluations.

Quick Start:
    from ddft import CognitiveProfiler

    profiler = CognitiveProfiler(model="your-model")
    profile = profiler.run_complete_assessment(
        concepts=["Natural Selection", "Recursion"],
        compression_levels=[0.0, 0.25, 0.5, 0.75, 1.0]
    )

    print(f"CI Score: {profile.ci_score}")
    print(f"Phenotype: {profile.phenotype}")
    print(f"Danger Zone Rate: {profile.danger_zone_pct}%")
"""

from cognitive_profiler import CognitiveProfiler, CognitiveProfile
from interviewer import InterviewerAgent, FabricationTrapGenerator
from compression import ContextCompressor, ConceptLoader
from llm_jury import LLMJury
from agent import create_agent

__version__ = "1.0.0"

__all__ = [
    "CognitiveProfiler",
    "CognitiveProfile",
    "InterviewerAgent",
    "FabricationTrapGenerator",
    "ContextCompressor",
    "ConceptLoader",
    "LLMJury",
    "create_agent"
]
