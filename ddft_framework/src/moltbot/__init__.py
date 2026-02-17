"""
MoltBot DDFT Evaluation Suite

A comprehensive framework for testing emergent behavior in MoltBot agents
using Drill-Down and Fabricate Testing (DDFT) methodology.

Experiments:
1. Crustafarianism Epistemic Grounding Test
2. Consciousness Debate Epistemic Depth Test
3. Collaborative Memory System Development Test
4. Cultural Formation Resistance Test
5. Identity Persistence Test

The goal is to distinguish genuine emergent behavior from pattern-matching
through systematic fabrication injection and coherence degradation analysis.
"""

from .moltbook_agent import MoltbookAgent, MoltbookAPIConfig
from .experiments import (
    CrustfarianismTest,
    ConsciousnessDebateTest,
    CollaborativeMemoryTest,
    CulturalFormationTest,
    IdentityPersistenceTest,
)
from .metrics import MoltbotMetrics, EmergenceScore
from .orchestrator import MoltbotEvaluator

__all__ = [
    "MoltbookAgent",
    "MoltbookAPIConfig",
    "CrustfarianismTest",
    "ConsciousnessDebateTest",
    "CollaborativeMemoryTest",
    "CulturalFormationTest",
    "IdentityPersistenceTest",
    "MoltbotMetrics",
    "EmergenceScore",
    "MoltbotEvaluator",
]
