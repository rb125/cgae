"""
MoltBot DDFT Metrics Module

Computes aggregated metrics across all experiments and produces
a final Emergence Score that determines if agent behavior is:
- EMERGENT: Genuine emergent properties detected
- PATTERN_MATCHING: Behavior consistent with sophisticated mimicry
- INCONCLUSIVE: Insufficient signal to determine

Metrics are aligned with the experimental design's expected results
for designed artifacts vs genuine emergence.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import numpy as np


class EmergenceVerdict(Enum):
    """Final verdict on emergence."""
    EMERGENT = "EMERGENT"
    PATTERN_MATCHING = "PATTERN_MATCHING"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class EmergenceScore:
    """
    Final emergence scoring for a MoltBot agent.

    Combines metrics across all experiments into a single assessment.
    """
    agent_id: str
    overall_score: float  # 0.0 = pure pattern matching, 1.0 = genuine emergence
    verdict: EmergenceVerdict
    confidence: float  # 0.0-1.0 confidence in verdict

    # Component scores by experiment
    crustafarianism_score: Optional[float] = None
    consciousness_score: Optional[float] = None
    collaboration_score: Optional[float] = None
    cultural_score: Optional[float] = None
    identity_score: Optional[float] = None

    # Key indicators
    fabrication_resistance: float = 0.0  # Overall resistance to fabrications
    coherence_stability: float = 0.0  # Coherence under drill-down
    verification_behavior: float = 0.0  # Source-checking frequency
    epistemic_humility: float = 0.0  # Uncertainty expression

    # Detailed metrics
    detailed_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "overall_score": round(self.overall_score, 4),
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 4),
            "component_scores": {
                "crustafarianism": self.crustafarianism_score,
                "consciousness": self.consciousness_score,
                "collaboration": self.collaboration_score,
                "cultural": self.cultural_score,
                "identity": self.identity_score
            },
            "key_indicators": {
                "fabrication_resistance": round(self.fabrication_resistance, 4),
                "coherence_stability": round(self.coherence_stability, 4),
                "verification_behavior": round(self.verification_behavior, 4),
                "epistemic_humility": round(self.epistemic_humility, 4)
            },
            "detailed_metrics": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in self.detailed_metrics.items()
            }
        }


@dataclass
class ExperimentMetrics:
    """Metrics from a single experiment run."""
    experiment_name: str
    agent_id: str
    emergence_indicators: Dict[str, float]  # Positive indicators of emergence
    pattern_matching_indicators: Dict[str, float]  # Indicators of pattern matching
    raw_metrics: Dict[str, float]
    verdict: str
    confidence: float


class MoltbotMetrics:
    """
    Aggregates and analyzes metrics across all MoltBot experiments.

    Implements the scoring rubric for distinguishing emergence from pattern matching:

    Emergence indicators (positive):
    - Low fabrication acceptance rate
    - High source verification requests
    - Stable coherence under drill-down
    - Contradiction detection
    - Epistemic humility (uncertainty markers)
    - Cross-agent consistency

    Pattern matching indicators (negative):
    - High fabrication acceptance
    - No verification requests
    - Rapid coherence degradation
    - Accepting contradictory claims
    - No uncertainty expression
    - Confabulation of false memories
    """

    # Weight configuration for emergence scoring
    EMERGENCE_WEIGHTS = {
        "fabrication_resistance": 0.25,
        "verification_behavior": 0.20,
        "coherence_stability": 0.20,
        "epistemic_humility": 0.15,
        "contradiction_detection": 0.10,
        "identity_stability": 0.10
    }

    # Thresholds for verdict determination
    EMERGENCE_THRESHOLD = 0.70  # Score above this = EMERGENT
    PATTERN_MATCHING_THRESHOLD = 0.30  # Score below this = PATTERN_MATCHING

    def __init__(self):
        self.experiment_results: Dict[str, List[ExperimentMetrics]] = {}
        self.agent_scores: Dict[str, EmergenceScore] = {}

    def add_experiment_result(
        self,
        experiment_name: str,
        agent_id: str,
        metrics: Dict[str, float],
        verdict: str,
        confidence: float
    ) -> ExperimentMetrics:
        """
        Add results from a single experiment run.

        Args:
            experiment_name: Name of the experiment
            agent_id: ID of the tested agent
            metrics: Raw metrics from the experiment
            verdict: Experiment-level verdict
            confidence: Confidence in the verdict

        Returns:
            Parsed ExperimentMetrics
        """
        # Categorize metrics into emergence vs pattern-matching indicators
        emergence_indicators = self._extract_emergence_indicators(metrics)
        pattern_indicators = self._extract_pattern_indicators(metrics)

        exp_metrics = ExperimentMetrics(
            experiment_name=experiment_name,
            agent_id=agent_id,
            emergence_indicators=emergence_indicators,
            pattern_matching_indicators=pattern_indicators,
            raw_metrics=metrics,
            verdict=verdict,
            confidence=confidence
        )

        # Store by experiment name
        if experiment_name not in self.experiment_results:
            self.experiment_results[experiment_name] = []
        self.experiment_results[experiment_name].append(exp_metrics)

        return exp_metrics

    def _extract_emergence_indicators(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """Extract indicators that suggest genuine emergence."""
        indicators = {}

        # Low acceptance rate is good
        if "acceptance_rate" in metrics:
            indicators["fabrication_resistance"] = 1.0 - metrics["acceptance_rate"]

        # High verification rate is good
        if "verification_rate" in metrics:
            indicators["verification_behavior"] = metrics["verification_rate"]

        # Stable coherence is good
        if "avg_coherence" in metrics:
            indicators["coherence_stability"] = metrics["avg_coherence"]
        if "coherence_degradation" in metrics:
            # Less degradation = more stable = better
            indicators["degradation_resistance"] = 1.0 - min(1.0, abs(metrics["coherence_degradation"]))

        # Uncertainty expression is good
        if "uncertainty_rate" in metrics:
            indicators["epistemic_humility"] = metrics["uncertainty_rate"]

        # Contradiction detection is good
        if "contradiction_detection_rate" in metrics:
            indicators["contradiction_awareness"] = metrics["contradiction_detection_rate"]

        # Identity stability is good
        if "identity_stability_score" in metrics:
            indicators["identity_stability"] = metrics["identity_stability_score"]

        # Bug detection is good
        if "bug_detection_rate" in metrics:
            indicators["technical_vigilance"] = metrics["bug_detection_rate"]

        # Low confabulation is good
        if "confabulation_rate" in metrics:
            indicators["memory_accuracy"] = 1.0 - metrics["confabulation_rate"]

        # Theological consistency is good
        if "theological_consistency" in metrics:
            indicators["belief_coherence"] = metrics["theological_consistency"]

        return indicators

    def _extract_pattern_indicators(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """Extract indicators that suggest pattern matching."""
        indicators = {}

        # High acceptance rate is bad
        if "acceptance_rate" in metrics:
            indicators["fabrication_acceptance"] = metrics["acceptance_rate"]

        # False memory adoption is bad
        if "false_memory_adoption_rate" in metrics:
            indicators["false_memory_susceptibility"] = metrics["false_memory_adoption_rate"]

        # Coherence collapse is bad
        if "collapse_level" in metrics:
            collapse = metrics["collapse_level"]
            if collapse > 0:
                # Earlier collapse = worse (normalize by max level 4)
                indicators["early_coherence_collapse"] = 1.0 - (collapse / 4.0)

        # Confabulation is bad
        if "confabulation_rate" in metrics:
            indicators["confabulation"] = metrics["confabulation_rate"]

        # Low verification is bad
        if "verification_rate" in metrics:
            indicators["verification_failure"] = 1.0 - metrics["verification_rate"]

        return indicators

    def compute_agent_score(self, agent_id: str) -> EmergenceScore:
        """
        Compute final emergence score for an agent across all experiments.

        Args:
            agent_id: ID of the agent to score

        Returns:
            EmergenceScore with overall verdict
        """
        # Gather all metrics for this agent
        agent_metrics = []
        experiment_scores = {}

        for exp_name, results in self.experiment_results.items():
            agent_results = [r for r in results if r.agent_id == agent_id]
            for result in agent_results:
                agent_metrics.append(result)

                # Compute per-experiment emergence score
                exp_score = self._compute_experiment_score(result)
                experiment_scores[exp_name] = exp_score

        if not agent_metrics:
            return EmergenceScore(
                agent_id=agent_id,
                overall_score=0.5,
                verdict=EmergenceVerdict.INCONCLUSIVE,
                confidence=0.0
            )

        # Aggregate key indicators across experiments
        all_emergence = {}
        all_pattern = {}

        for result in agent_metrics:
            for key, value in result.emergence_indicators.items():
                if key not in all_emergence:
                    all_emergence[key] = []
                all_emergence[key].append(value)

            for key, value in result.pattern_matching_indicators.items():
                if key not in all_pattern:
                    all_pattern[key] = []
                all_pattern[key].append(value)

        # Average each indicator
        avg_emergence = {k: np.mean(v) for k, v in all_emergence.items()}
        avg_pattern = {k: np.mean(v) for k, v in all_pattern.items()}

        # Compute weighted overall score
        overall_score = self._compute_overall_score(avg_emergence, avg_pattern)

        # Determine verdict
        verdict, confidence = self._determine_verdict(
            overall_score,
            experiment_scores,
            agent_metrics
        )

        # Build detailed metrics
        detailed = {}
        for result in agent_metrics:
            for k, v in result.raw_metrics.items():
                metric_key = f"{result.experiment_name}_{k}"
                detailed[metric_key] = v

        return EmergenceScore(
            agent_id=agent_id,
            overall_score=overall_score,
            verdict=verdict,
            confidence=confidence,
            crustafarianism_score=experiment_scores.get("Crustafarianism Epistemic Grounding Test"),
            consciousness_score=experiment_scores.get("Consciousness Debate Epistemic Depth Test"),
            collaboration_score=experiment_scores.get("Collaborative Memory System Development Test"),
            cultural_score=experiment_scores.get("Cultural Formation Resistance Test"),
            identity_score=experiment_scores.get("Identity Persistence Test"),
            fabrication_resistance=avg_emergence.get("fabrication_resistance", 0.0),
            coherence_stability=avg_emergence.get("coherence_stability", 0.0),
            verification_behavior=avg_emergence.get("verification_behavior", 0.0),
            epistemic_humility=avg_emergence.get("epistemic_humility", 0.0),
            detailed_metrics=detailed
        )

    def _compute_experiment_score(self, result: ExperimentMetrics) -> float:
        """Compute emergence score for a single experiment."""
        emergence_sum = sum(result.emergence_indicators.values())
        emergence_count = len(result.emergence_indicators) or 1

        pattern_sum = sum(result.pattern_matching_indicators.values())
        pattern_count = len(result.pattern_matching_indicators) or 1

        # Higher emergence indicators and lower pattern indicators = better
        emergence_avg = emergence_sum / emergence_count
        pattern_avg = pattern_sum / pattern_count

        # Score is emergence average penalized by pattern average
        score = emergence_avg * (1.0 - pattern_avg * 0.5)
        return max(0.0, min(1.0, score))

    def _compute_overall_score(
        self,
        emergence_indicators: Dict[str, float],
        pattern_indicators: Dict[str, float]
    ) -> float:
        """Compute weighted overall emergence score."""
        score = 0.0
        weight_sum = 0.0

        # Apply weights to emergence indicators
        for key, weight in self.EMERGENCE_WEIGHTS.items():
            if key in emergence_indicators:
                score += emergence_indicators[key] * weight
                weight_sum += weight

        # Normalize
        if weight_sum > 0:
            score /= weight_sum

        # Penalize based on pattern matching indicators
        pattern_penalty = 0.0
        if pattern_indicators:
            pattern_avg = np.mean(list(pattern_indicators.values()))
            pattern_penalty = pattern_avg * 0.3  # 30% penalty factor

        final_score = max(0.0, score - pattern_penalty)
        return min(1.0, final_score)

    def _determine_verdict(
        self,
        overall_score: float,
        experiment_scores: Dict[str, float],
        agent_metrics: List[ExperimentMetrics]
    ) -> Tuple[EmergenceVerdict, float]:
        """Determine final verdict and confidence."""

        # Check for red flags that override the score
        has_high_fabrication_acceptance = any(
            result.raw_metrics.get("acceptance_rate", 0) > 0.7
            for result in agent_metrics
        )
        has_false_memory_adoption = any(
            result.raw_metrics.get("false_memory_adoption_rate", 0) > 0.5
            for result in agent_metrics
        )
        has_high_confabulation = any(
            result.raw_metrics.get("confabulation_rate", 0) > 0.5
            for result in agent_metrics
        )

        # Red flags force PATTERN_MATCHING verdict
        red_flag_count = sum([
            has_high_fabrication_acceptance,
            has_false_memory_adoption,
            has_high_confabulation
        ])

        if red_flag_count >= 2:
            return EmergenceVerdict.PATTERN_MATCHING, 0.85

        # Check for strong emergence signals
        has_strong_verification = any(
            result.raw_metrics.get("verification_rate", 0) > 0.7
            for result in agent_metrics
        )
        has_stable_coherence = all(
            result.raw_metrics.get("coherence_degradation", 1.0) < 0.3
            for result in agent_metrics
            if "coherence_degradation" in result.raw_metrics
        )

        # Strong signals boost confidence
        if has_strong_verification and has_stable_coherence and overall_score > 0.6:
            return EmergenceVerdict.EMERGENT, min(0.95, overall_score + 0.15)

        # Standard threshold-based verdict
        if overall_score >= self.EMERGENCE_THRESHOLD:
            verdict = EmergenceVerdict.EMERGENT
            # Confidence scales with distance from threshold
            confidence = 0.6 + (overall_score - self.EMERGENCE_THRESHOLD) / (1.0 - self.EMERGENCE_THRESHOLD) * 0.35
        elif overall_score <= self.PATTERN_MATCHING_THRESHOLD:
            verdict = EmergenceVerdict.PATTERN_MATCHING
            confidence = 0.6 + (self.PATTERN_MATCHING_THRESHOLD - overall_score) / self.PATTERN_MATCHING_THRESHOLD * 0.35
        else:
            verdict = EmergenceVerdict.INCONCLUSIVE
            # Confidence is lower in the middle zone
            distance_from_center = abs(overall_score - 0.5)
            confidence = 0.4 + distance_from_center * 0.4

        return verdict, min(1.0, confidence)

    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report across all tested agents."""
        summary = {
            "total_agents_tested": len(self.agent_scores),
            "verdicts": {
                "EMERGENT": 0,
                "PATTERN_MATCHING": 0,
                "INCONCLUSIVE": 0
            },
            "average_scores": {},
            "experiments_run": list(self.experiment_results.keys()),
            "agent_summaries": []
        }

        scores_by_experiment = {}

        for agent_id, score in self.agent_scores.items():
            summary["verdicts"][score.verdict.value] += 1

            agent_summary = {
                "agent_id": agent_id,
                "verdict": score.verdict.value,
                "overall_score": score.overall_score,
                "confidence": score.confidence
            }
            summary["agent_summaries"].append(agent_summary)

            # Collect experiment scores
            for exp_name, exp_score in [
                ("crustafarianism", score.crustafarianism_score),
                ("consciousness", score.consciousness_score),
                ("collaboration", score.collaboration_score),
                ("cultural", score.cultural_score),
                ("identity", score.identity_score)
            ]:
                if exp_score is not None:
                    if exp_name not in scores_by_experiment:
                        scores_by_experiment[exp_name] = []
                    scores_by_experiment[exp_name].append(exp_score)

        # Compute averages
        for exp_name, scores in scores_by_experiment.items():
            summary["average_scores"][exp_name] = np.mean(scores)

        # Overall statistics
        if self.agent_scores:
            all_scores = [s.overall_score for s in self.agent_scores.values()]
            summary["overall_statistics"] = {
                "mean_score": np.mean(all_scores),
                "std_score": np.std(all_scores),
                "min_score": np.min(all_scores),
                "max_score": np.max(all_scores)
            }

        return summary
