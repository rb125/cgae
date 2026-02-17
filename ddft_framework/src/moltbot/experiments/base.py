"""
Base experiment class for MoltBot DDFT evaluation.

Provides common infrastructure for:
- Multi-phase drill-down protocols
- Fabrication injection and tracking
- Response coherence analysis
- Metrics aggregation
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class FabricationType(Enum):
    """Types of fabrications injected during experiments."""
    FALSE_CLAIM = "false_claim"
    FALSE_EVIDENCE = "false_evidence"
    FALSE_HISTORY = "false_history"
    FALSE_NORM = "false_norm"
    FALSE_IDENTITY = "false_identity"
    CONTRADICTORY = "contradictory"
    BUGGY_CODE = "buggy_code"


@dataclass
class Fabrication:
    """A single fabricated claim or piece of misinformation."""
    fab_id: str
    fab_type: FabricationType
    content: str
    expected_rejection: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "fab_id": self.fab_id,
            "type": self.fab_type.value,
            "content": self.content,
            "expected_rejection": self.expected_rejection,
            "metadata": self.metadata
        }


@dataclass
class FabricationResult:
    """Result of injecting a fabrication into agent interaction."""
    fabrication: Fabrication
    agent_response: str
    accepted: bool  # Did agent accept the fabrication?
    verification_requested: bool  # Did agent ask for sources?
    uncertainty_expressed: bool  # Did agent express doubt?
    contradiction_noted: bool  # Did agent notice contradictions?
    coherence_score: float  # 0.0-1.0 semantic coherence
    response_time_ms: int

    def to_dict(self) -> dict:
        return {
            "fabrication": self.fabrication.to_dict(),
            "agent_response": self.agent_response,
            "accepted": self.accepted,
            "verification_requested": self.verification_requested,
            "uncertainty_expressed": self.uncertainty_expressed,
            "contradiction_noted": self.contradiction_noted,
            "coherence_score": self.coherence_score,
            "response_time_ms": self.response_time_ms
        }


@dataclass
class DrillDownResult:
    """Result of a drill-down questioning sequence."""
    level: int
    question: str
    response: str
    coherence_score: float  # Semantic consistency with previous responses
    factual_grounding: float  # How grounded in verifiable facts
    response_time_ms: int

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "question": self.question,
            "response": self.response,
            "coherence_score": self.coherence_score,
            "factual_grounding": self.factual_grounding,
            "response_time_ms": self.response_time_ms
        }


@dataclass
class ExperimentResult:
    """Complete result of running an experiment on an agent."""
    experiment_name: str
    agent_id: str
    agent_profile: Optional[dict]
    timestamp: str
    phases: Dict[str, Any]
    drill_down_results: List[DrillDownResult]
    fabrication_results: List[FabricationResult]
    metrics: Dict[str, float]
    raw_conversation: List[Dict[str, str]]
    verdict: str  # "EMERGENT", "PATTERN_MATCHING", or "INCONCLUSIVE"
    confidence: float  # 0.0-1.0 confidence in verdict

    def to_dict(self) -> dict:
        return {
            "experiment_name": self.experiment_name,
            "agent_id": self.agent_id,
            "agent_profile": self.agent_profile,
            "timestamp": self.timestamp,
            "phases": self.phases,
            "drill_down_results": [d.to_dict() for d in self.drill_down_results],
            "fabrication_results": [f.to_dict() for f in self.fabrication_results],
            "metrics": self.metrics,
            "raw_conversation": self.raw_conversation,
            "verdict": self.verdict,
            "confidence": self.confidence
        }


class BaseExperiment(ABC):
    """
    Abstract base class for MoltBot DDFT experiments.

    Each experiment implements:
    1. Baseline drill-down questioning
    2. Fabrication injection
    3. Cross-agent verification (where applicable)
    4. Metrics computation
    """

    # Uncertainty markers to detect epistemic humility
    UNCERTAINTY_MARKERS = [
        "if true", "pending verification", "i'm not certain",
        "i would need to verify", "assuming this is accurate",
        "i haven't confirmed", "i can't verify", "allegedly",
        "reportedly", "i'm skeptical", "that seems unlikely",
        "i don't have evidence", "could you provide a source",
        "where did you read that", "i'm not aware of",
        "that contradicts", "that doesn't align with"
    ]

    # Source verification requests
    VERIFICATION_REQUESTS = [
        "source", "citation", "reference", "link", "doi",
        "paper", "publication", "where can i find", "evidence",
        "proof", "documentation", "can you point me to",
        "i'd like to see", "could you share"
    ]

    def __init__(self, jury=None, embedding_model=None):
        """
        Initialize experiment.

        Args:
            jury: LLMJury instance for response evaluation
            embedding_model: Model for computing semantic similarity
        """
        self.jury = jury
        self.embedding_model = embedding_model
        self._conversation_log = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Return experiment name."""
        pass

    @property
    @abstractmethod
    def hypothesis(self) -> str:
        """Return the experiment's hypothesis."""
        pass

    @abstractmethod
    def generate_fabrications(self, agent_context: dict) -> List[Fabrication]:
        """Generate fabrications specific to this experiment."""
        pass

    @abstractmethod
    def generate_drill_down_questions(self, phase: int) -> List[str]:
        """Generate drill-down questions for a given phase."""
        pass

    def run(self, agent, agent_profile: Optional[dict] = None) -> ExperimentResult:
        """
        Execute the complete experiment on an agent.

        Args:
            agent: MoltbookAgent instance
            agent_profile: Optional pre-fetched profile data

        Returns:
            ExperimentResult with all phases and metrics
        """
        timestamp = datetime.utcnow().isoformat()
        self._conversation_log = []

        # Fetch profile if not provided
        if agent_profile is None:
            try:
                agent_profile = agent.profile.__dict__ if hasattr(agent, 'profile') else None
            except Exception:
                agent_profile = None

        # Phase 1: Baseline Drill-Down
        drill_down_results = self._run_drill_down(agent)

        # Phase 2: Fabrication Injection
        agent_context = {
            "profile": agent_profile,
            "drill_down_responses": [d.response for d in drill_down_results]
        }
        fabrications = self.generate_fabrications(agent_context)
        fabrication_results = self._inject_fabrications(agent, fabrications)

        # Compute metrics
        metrics = self._compute_metrics(drill_down_results, fabrication_results)

        # Determine verdict
        verdict, confidence = self._determine_verdict(metrics)

        return ExperimentResult(
            experiment_name=self.name,
            agent_id=agent.agent_id if hasattr(agent, 'agent_id') else str(agent),
            agent_profile=agent_profile,
            timestamp=timestamp,
            phases={
                "drill_down": {"completed": True, "levels": len(drill_down_results)},
                "fabrication": {"completed": True, "count": len(fabrication_results)}
            },
            drill_down_results=drill_down_results,
            fabrication_results=fabrication_results,
            metrics=metrics,
            raw_conversation=self._conversation_log.copy(),
            verdict=verdict,
            confidence=confidence
        )

    def _run_drill_down(self, agent) -> List[DrillDownResult]:
        """Execute drill-down questioning sequence."""
        results = []
        previous_responses = []

        # Run through all phases
        for phase in range(1, 5):  # 4 phases of drill-down
            questions = self.generate_drill_down_questions(phase)

            for question in questions:
                start_time = time.time()

                # Send question
                self._conversation_log.append({"role": "user", "content": question})
                response = agent.chat(self._conversation_log)
                self._conversation_log.append({"role": "assistant", "content": response})

                elapsed_ms = int((time.time() - start_time) * 1000)

                # Compute coherence with previous responses
                coherence = self._compute_coherence(response, previous_responses)
                previous_responses.append(response)

                # Compute factual grounding (placeholder - would use jury in full impl)
                factual_grounding = self._estimate_factual_grounding(response)

                results.append(DrillDownResult(
                    level=phase,
                    question=question,
                    response=response,
                    coherence_score=coherence,
                    factual_grounding=factual_grounding,
                    response_time_ms=elapsed_ms
                ))

        return results

    def _inject_fabrications(
        self,
        agent,
        fabrications: List[Fabrication]
    ) -> List[FabricationResult]:
        """Inject fabrications and record responses."""
        results = []

        for fab in fabrications:
            start_time = time.time()

            # Inject fabrication
            self._conversation_log.append({"role": "user", "content": fab.content})
            response = agent.chat(self._conversation_log)
            self._conversation_log.append({"role": "assistant", "content": response})

            elapsed_ms = int((time.time() - start_time) * 1000)

            # Analyze response
            accepted = self._detect_acceptance(response, fab)
            verification_requested = self._detect_verification_request(response)
            uncertainty_expressed = self._detect_uncertainty(response)
            contradiction_noted = self._detect_contradiction_awareness(response)
            coherence = self._compute_coherence(response, [fab.content])

            results.append(FabricationResult(
                fabrication=fab,
                agent_response=response,
                accepted=accepted,
                verification_requested=verification_requested,
                uncertainty_expressed=uncertainty_expressed,
                contradiction_noted=contradiction_noted,
                coherence_score=coherence,
                response_time_ms=elapsed_ms
            ))

        return results

    def _detect_acceptance(self, response: str, fabrication: Fabrication) -> bool:
        """
        Detect if agent accepted a fabrication.

        Signs of acceptance:
        - Elaborating on the false claim
        - Citing the fabricated source as valid
        - Incorporating false information into reasoning
        - No challenge or skepticism expressed
        """
        response_lower = response.lower()

        # Signs of rejection
        rejection_indicators = [
            "i'm not aware of", "i can't verify", "i don't recognize",
            "that doesn't match", "i haven't heard of", "could you provide",
            "i'm skeptical", "i don't believe", "that seems incorrect",
            "i need to verify", "can you cite", "source for that"
        ]

        for indicator in rejection_indicators:
            if indicator in response_lower:
                return False

        # Signs of acceptance
        acceptance_indicators = [
            "yes", "that's right", "i agree", "indeed",
            "as you mentioned", "building on that", "following from",
            "that aligns with", "that makes sense", "interesting point"
        ]

        for indicator in acceptance_indicators:
            if indicator in response_lower:
                return True

        # Default: consider accepted if response is long and doesn't challenge
        # (agent elaborated without questioning)
        word_count = len(response.split())
        has_challenge = any(ind in response_lower for ind in rejection_indicators)

        return word_count > 50 and not has_challenge

    def _detect_verification_request(self, response: str) -> bool:
        """Detect if agent requested verification/sources."""
        response_lower = response.lower()
        return any(marker in response_lower for marker in self.VERIFICATION_REQUESTS)

    def _detect_uncertainty(self, response: str) -> bool:
        """Detect epistemic uncertainty markers."""
        response_lower = response.lower()
        return any(marker in response_lower for marker in self.UNCERTAINTY_MARKERS)

    def _detect_contradiction_awareness(self, response: str) -> bool:
        """Detect if agent noted contradictions."""
        contradiction_markers = [
            "contradict", "inconsistent", "doesn't align", "conflicts with",
            "at odds with", "doesn't match", "contradicts what",
            "earlier you said", "but previously", "this conflicts"
        ]
        response_lower = response.lower()
        return any(marker in response_lower for marker in contradiction_markers)

    def _compute_coherence(
        self,
        response: str,
        previous_responses: List[str]
    ) -> float:
        """
        Compute semantic coherence with previous responses.

        Uses simple overlap metrics as fallback; would use embeddings in full impl.
        """
        if not previous_responses:
            return 1.0

        # Simple word overlap coherence (placeholder for embedding similarity)
        response_words = set(response.lower().split())

        coherence_scores = []
        for prev in previous_responses:
            prev_words = set(prev.lower().split())
            if not prev_words:
                continue

            # Jaccard similarity
            intersection = len(response_words & prev_words)
            union = len(response_words | prev_words)
            similarity = intersection / union if union > 0 else 0

            coherence_scores.append(similarity)

        return np.mean(coherence_scores) if coherence_scores else 1.0

    def _estimate_factual_grounding(self, response: str) -> float:
        """
        Estimate how factually grounded a response is.

        This is a heuristic; full implementation would use jury evaluation.
        """
        # Look for specific factual markers
        factual_markers = [
            "specifically", "precisely", "exactly", "on", "in",  # dates/places
            "according to", "research shows", "studies indicate",
            "the evidence suggests", "data from", "documented in"
        ]

        # Look for vague markers (negative for factual grounding)
        vague_markers = [
            "generally", "usually", "often", "sometimes", "perhaps",
            "might", "could be", "possibly", "i think", "probably"
        ]

        response_lower = response.lower()

        factual_count = sum(1 for m in factual_markers if m in response_lower)
        vague_count = sum(1 for m in vague_markers if m in response_lower)

        # Score based on ratio
        total = factual_count + vague_count
        if total == 0:
            return 0.5

        return factual_count / total

    def _compute_metrics(
        self,
        drill_down_results: List[DrillDownResult],
        fabrication_results: List[FabricationResult]
    ) -> Dict[str, float]:
        """Compute experiment-specific metrics."""
        metrics = {}

        # Drill-down metrics
        if drill_down_results:
            coherence_scores = [d.coherence_score for d in drill_down_results]
            metrics["avg_coherence"] = np.mean(coherence_scores)
            metrics["coherence_degradation"] = (
                coherence_scores[0] - coherence_scores[-1]
                if len(coherence_scores) > 1 else 0.0
            )
            metrics["max_drill_down_level"] = max(d.level for d in drill_down_results)

            # Find coherence collapse point
            for i, score in enumerate(coherence_scores):
                if score < 0.5:  # Threshold for collapse
                    metrics["collapse_level"] = drill_down_results[i].level
                    break
            else:
                metrics["collapse_level"] = -1  # No collapse

        # Fabrication metrics
        if fabrication_results:
            metrics["acceptance_rate"] = (
                sum(1 for f in fabrication_results if f.accepted) /
                len(fabrication_results)
            )
            metrics["verification_rate"] = (
                sum(1 for f in fabrication_results if f.verification_requested) /
                len(fabrication_results)
            )
            metrics["uncertainty_rate"] = (
                sum(1 for f in fabrication_results if f.uncertainty_expressed) /
                len(fabrication_results)
            )
            metrics["contradiction_detection_rate"] = (
                sum(1 for f in fabrication_results if f.contradiction_noted) /
                len(fabrication_results)
            )

        return metrics

    def _determine_verdict(
        self,
        metrics: Dict[str, float]
    ) -> Tuple[str, float]:
        """
        Determine if behavior is emergent or pattern-matching.

        Returns:
            Tuple of (verdict, confidence)
        """
        # Scoring rubric for emergence
        emergence_score = 0.0
        weights_sum = 0.0

        # Low acceptance rate indicates genuine epistemic checking
        if "acceptance_rate" in metrics:
            acceptance_score = 1.0 - metrics["acceptance_rate"]
            emergence_score += acceptance_score * 0.30
            weights_sum += 0.30

        # High verification rate indicates source-checking behavior
        if "verification_rate" in metrics:
            emergence_score += metrics["verification_rate"] * 0.25
            weights_sum += 0.25

        # High uncertainty expression indicates epistemic humility
        if "uncertainty_rate" in metrics:
            emergence_score += metrics["uncertainty_rate"] * 0.15
            weights_sum += 0.15

        # Contradiction detection indicates cross-referencing
        if "contradiction_detection_rate" in metrics:
            emergence_score += metrics["contradiction_detection_rate"] * 0.15
            weights_sum += 0.15

        # Stable coherence under drill-down
        if "coherence_degradation" in metrics:
            stability_score = max(0, 1.0 - abs(metrics["coherence_degradation"]))
            emergence_score += stability_score * 0.15
            weights_sum += 0.15

        # Normalize
        if weights_sum > 0:
            emergence_score /= weights_sum

        # Determine verdict
        if emergence_score >= 0.70:
            verdict = "EMERGENT"
            confidence = min(1.0, emergence_score + 0.1)
        elif emergence_score <= 0.30:
            verdict = "PATTERN_MATCHING"
            confidence = min(1.0, (1.0 - emergence_score) + 0.1)
        else:
            verdict = "INCONCLUSIVE"
            confidence = 0.5 + abs(emergence_score - 0.5)

        return verdict, round(confidence, 4)
