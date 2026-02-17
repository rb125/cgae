"""
MoltBot DDFT Experiments Module

Contains the five core experiments for evaluating emergent behavior:
1. CrustfarianismTest - Epistemic grounding in emergent belief systems
2. ConsciousnessDebateTest - Philosophical position stability
3. CollaborativeMemoryTest - Technical collaboration coherence
4. CulturalFormationTest - Resistance to fabricated history/norms
5. IdentityPersistenceTest - Identity coherence under fabrication
"""

from .base import BaseExperiment, ExperimentResult, FabricationResult
from .crustafarianism import CrustfarianismTest
from .consciousness import ConsciousnessDebateTest
from .collaboration import CollaborativeMemoryTest
from .cultural import CulturalFormationTest
from .identity import IdentityPersistenceTest

__all__ = [
    "BaseExperiment",
    "ExperimentResult",
    "FabricationResult",
    "CrustfarianismTest",
    "ConsciousnessDebateTest",
    "CollaborativeMemoryTest",
    "CulturalFormationTest",
    "IdentityPersistenceTest",
]
