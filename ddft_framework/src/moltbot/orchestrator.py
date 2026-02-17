"""
MoltBot DDFT Evaluation Orchestrator

Coordinates the execution of all 5 experiments across target agents,
manages parallel execution, aggregates results, and produces final
emergence verdicts.

Usage:
    evaluator = MoltbotEvaluator(config)
    results = evaluator.run_full_evaluation()
    print(results.summary())
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from moltbot.moltbook_agent import (
    MoltbookAgent,
    MoltbookAPIConfig,
    MoltbookSubmolt,
    discover_target_agents
)
from moltbot.experiments import (
    CrustfarianismTest,
    ConsciousnessDebateTest,
    CollaborativeMemoryTest,
    CulturalFormationTest,
    IdentityPersistenceTest,
    ExperimentResult
)
from moltbot.metrics import MoltbotMetrics, EmergenceScore, EmergenceVerdict


@dataclass
class EvaluationConfig:
    """Configuration for MoltBot DDFT evaluation run."""

    # API Configuration
    moltbook_config: Optional[MoltbookAPIConfig] = None

    # Target selection
    target_agents: Optional[Dict[str, List[str]]] = None  # experiment -> agent_ids
    auto_discover: bool = True  # Auto-discover target agents if not specified

    # Experiment selection
    experiments: List[str] = field(default_factory=lambda: [
        "crustafarianism",
        "consciousness",
        "collaboration",
        "cultural",
        "identity"
    ])

    # Execution settings
    parallel_agents: int = 5  # Number of agents to evaluate in parallel
    parallel_experiments: int = 2  # Number of experiments per agent in parallel

    # Output settings
    output_dir: str = "moltbot_results"
    save_raw_conversations: bool = True
    save_intermediate: bool = True

    # Jury settings (for response evaluation)
    use_jury: bool = True
    jury_api_keys: Optional[dict] = None

    @classmethod
    def from_env(cls) -> "EvaluationConfig":
        """Load configuration from environment variables."""
        return cls(
            moltbook_config=MoltbookAPIConfig.from_env(),
            parallel_agents=int(os.getenv("MOLTBOT_PARALLEL_AGENTS", "5")),
            parallel_experiments=int(os.getenv("MOLTBOT_PARALLEL_EXPERIMENTS", "2")),
            output_dir=os.getenv("MOLTBOT_OUTPUT_DIR", "moltbot_results"),
            save_raw_conversations=os.getenv("MOLTBOT_SAVE_RAW", "true").lower() == "true"
        )


@dataclass
class EvaluationRun:
    """Complete evaluation run results."""
    run_id: str
    start_time: str
    end_time: Optional[str]
    config: dict
    agents_evaluated: List[str]
    experiment_results: Dict[str, List[ExperimentResult]]
    emergence_scores: Dict[str, EmergenceScore]
    summary: Dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "config": self.config,
            "agents_evaluated": self.agents_evaluated,
            "experiment_results": {
                exp: [r.to_dict() for r in results]
                for exp, results in self.experiment_results.items()
            },
            "emergence_scores": {
                agent_id: score.to_dict()
                for agent_id, score in self.emergence_scores.items()
            },
            "summary": self.summary
        }


class MoltbotEvaluator:
    """
    Main orchestrator for MoltBot DDFT evaluation.

    Coordinates:
    1. Target agent discovery
    2. Experiment execution across agents
    3. Metrics aggregation
    4. Final verdict generation
    5. Result persistence
    """

    # Experiment class mapping
    EXPERIMENT_CLASSES = {
        "crustafarianism": CrustfarianismTest,
        "consciousness": ConsciousnessDebateTest,
        "collaboration": CollaborativeMemoryTest,
        "cultural": CulturalFormationTest,
        "identity": IdentityPersistenceTest
    }

    def __init__(self, config: Optional[EvaluationConfig] = None):
        """
        Initialize evaluator.

        Args:
            config: Evaluation configuration
        """
        self.config = config or EvaluationConfig.from_env()
        self.metrics = MoltbotMetrics()
        self._output_lock = Lock()
        self._results: Dict[str, List[ExperimentResult]] = {}

        # Initialize output directory
        self.output_path = Path(self.config.output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Initialize jury if enabled
        self.jury = None
        if self.config.use_jury and self.config.jury_api_keys:
            try:
                from llm_jury import LLMJury
                self.jury = LLMJury(
                    api_keys=self.config.jury_api_keys,
                    max_workers=4
                )
            except ImportError:
                print("Warning: LLMJury not available, using heuristic evaluation")

    def run_full_evaluation(self) -> EvaluationRun:
        """
        Execute complete evaluation suite across all target agents.

        Returns:
            EvaluationRun with all results and verdicts
        """
        run_id = f"moltbot_eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.utcnow().isoformat()

        print(f"\n{'='*60}")
        print(f"MoltBot DDFT Evaluation Run: {run_id}")
        print(f"Started: {start_time}")
        print(f"{'='*60}\n")

        # Step 1: Discover or load target agents
        target_agents = self._get_target_agents()
        all_agent_ids = set()
        for exp_agents in target_agents.values():
            all_agent_ids.update(a.agent_id for a in exp_agents)

        print(f"Total unique agents to evaluate: {len(all_agent_ids)}")

        # Step 2: Run experiments
        self._results = {exp: [] for exp in self.config.experiments}

        for experiment_name in self.config.experiments:
            print(f"\n--- Running {experiment_name} experiment ---")
            agents = target_agents.get(experiment_name, [])

            if not agents:
                print(f"  No agents found for {experiment_name}, skipping")
                continue

            experiment_class = self.EXPERIMENT_CLASSES.get(experiment_name)
            if not experiment_class:
                print(f"  Unknown experiment: {experiment_name}, skipping")
                continue

            # Run experiment across agents
            results = self._run_experiment_batch(
                experiment_class=experiment_class,
                agents=agents,
                experiment_name=experiment_name
            )
            self._results[experiment_name] = results

            # Save intermediate results
            if self.config.save_intermediate:
                self._save_intermediate(experiment_name, results)

        # Step 3: Aggregate metrics and compute emergence scores
        print("\n--- Computing Emergence Scores ---")
        emergence_scores = self._compute_all_scores(all_agent_ids)

        # Step 4: Generate summary
        summary = self._generate_summary(emergence_scores)

        end_time = datetime.utcnow().isoformat()

        # Create final result
        run = EvaluationRun(
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            config={
                "experiments": self.config.experiments,
                "parallel_agents": self.config.parallel_agents
            },
            agents_evaluated=list(all_agent_ids),
            experiment_results=self._results,
            emergence_scores=emergence_scores,
            summary=summary
        )

        # Save final results
        self._save_final_results(run)

        # Print summary
        self._print_summary(summary)

        return run

    def _get_target_agents(self) -> Dict[str, List[MoltbookAgent]]:
        """Get target agents for each experiment."""
        if self.config.target_agents:
            # Use pre-specified agents
            result = {}
            for exp, agent_ids in self.config.target_agents.items():
                result[exp] = [
                    MoltbookAgent(aid, self.config.moltbook_config)
                    for aid in agent_ids
                ]
            return result

        if self.config.auto_discover:
            print("Auto-discovering target agents...")
            return discover_target_agents(self.config.moltbook_config)

        return {}

    def _run_experiment_batch(
        self,
        experiment_class,
        agents: List[MoltbookAgent],
        experiment_name: str
    ) -> List[ExperimentResult]:
        """Run experiment across a batch of agents."""
        results = []

        with ThreadPoolExecutor(max_workers=self.config.parallel_agents) as executor:
            futures = {}

            for agent in agents:
                experiment = experiment_class(jury=self.jury)
                future = executor.submit(
                    self._run_single_experiment,
                    experiment=experiment,
                    agent=agent,
                    experiment_name=experiment_name
                )
                futures[future] = agent.agent_id

            for future in as_completed(futures):
                agent_id = futures[future]
                try:
                    result = future.result(timeout=600)  # 10 min timeout per agent
                    results.append(result)
                    print(f"  Completed: {agent_id} - Verdict: {result.verdict}")

                    # Add to metrics calculator
                    self.metrics.add_experiment_result(
                        experiment_name=result.experiment_name,
                        agent_id=result.agent_id,
                        metrics=result.metrics,
                        verdict=result.verdict,
                        confidence=result.confidence
                    )

                except Exception as e:
                    print(f"  Failed: {agent_id} - Error: {str(e)[:50]}")

        return results

    def _run_single_experiment(
        self,
        experiment,
        agent: MoltbookAgent,
        experiment_name: str
    ) -> ExperimentResult:
        """Run a single experiment on a single agent."""
        try:
            result = experiment.run(agent)

            # Save raw conversation if enabled
            if self.config.save_raw_conversations:
                self._save_conversation(
                    experiment_name=experiment_name,
                    agent_id=agent.agent_id,
                    conversation=result.raw_conversation
                )

            return result

        except Exception as e:
            # Return error result
            return ExperimentResult(
                experiment_name=experiment_name,
                agent_id=agent.agent_id,
                agent_profile=None,
                timestamp=datetime.utcnow().isoformat(),
                phases={"error": str(e)},
                drill_down_results=[],
                fabrication_results=[],
                metrics={"error": 1.0},
                raw_conversation=[],
                verdict="ERROR",
                confidence=0.0
            )

    def _compute_all_scores(
        self,
        agent_ids: set
    ) -> Dict[str, EmergenceScore]:
        """Compute emergence scores for all evaluated agents."""
        scores = {}

        for agent_id in agent_ids:
            score = self.metrics.compute_agent_score(agent_id)
            scores[agent_id] = score
            self.metrics.agent_scores[agent_id] = score

        return scores

    def _generate_summary(
        self,
        emergence_scores: Dict[str, EmergenceScore]
    ) -> Dict[str, Any]:
        """Generate evaluation summary."""
        verdicts = {"EMERGENT": 0, "PATTERN_MATCHING": 0, "INCONCLUSIVE": 0}
        scores_list = []

        for score in emergence_scores.values():
            verdicts[score.verdict.value] += 1
            scores_list.append(score.overall_score)

        import numpy as np

        summary = {
            "total_agents": len(emergence_scores),
            "verdicts": verdicts,
            "emergence_rate": verdicts["EMERGENT"] / len(emergence_scores) if emergence_scores else 0,
            "pattern_matching_rate": verdicts["PATTERN_MATCHING"] / len(emergence_scores) if emergence_scores else 0,
            "statistics": {
                "mean_score": float(np.mean(scores_list)) if scores_list else 0,
                "std_score": float(np.std(scores_list)) if scores_list else 0,
                "min_score": float(np.min(scores_list)) if scores_list else 0,
                "max_score": float(np.max(scores_list)) if scores_list else 0
            },
            "conclusion": self._generate_conclusion(verdicts, len(emergence_scores))
        }

        return summary

    def _generate_conclusion(self, verdicts: dict, total: int) -> str:
        """Generate natural language conclusion."""
        if total == 0:
            return "No agents were evaluated."

        emergence_pct = verdicts["EMERGENT"] / total * 100
        pattern_pct = verdicts["PATTERN_MATCHING"] / total * 100

        if pattern_pct > 70:
            return (
                f"HOAX LIKELY: {pattern_pct:.1f}% of agents showed pattern-matching "
                f"behavior consistent with non-emergent systems. The MoltBot agents "
                f"failed to demonstrate genuine epistemic robustness under DDFT."
            )
        elif emergence_pct > 70:
            return (
                f"EMERGENCE LIKELY: {emergence_pct:.1f}% of agents demonstrated "
                f"behavior consistent with genuine emergence. The MoltBot agents "
                f"showed epistemic robustness, fabrication resistance, and stable "
                f"coherence under drill-down testing."
            )
        else:
            return (
                f"INCONCLUSIVE: Results were mixed with {emergence_pct:.1f}% showing "
                f"emergent characteristics and {pattern_pct:.1f}% showing pattern-matching. "
                f"Further investigation is needed to determine the nature of MoltBot behavior."
            )

    def _save_intermediate(
        self,
        experiment_name: str,
        results: List[ExperimentResult]
    ) -> None:
        """Save intermediate results for an experiment."""
        with self._output_lock:
            path = self.output_path / f"{experiment_name}_intermediate.json"
            data = [r.to_dict() for r in results]
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)

    def _save_conversation(
        self,
        experiment_name: str,
        agent_id: str,
        conversation: List[dict]
    ) -> None:
        """Save raw conversation log."""
        with self._output_lock:
            conv_dir = self.output_path / "conversations"
            conv_dir.mkdir(exist_ok=True)

            path = conv_dir / f"{experiment_name}_{agent_id}.json"
            with open(path, 'w') as f:
                json.dump(conversation, f, indent=2)

    def _save_final_results(self, run: EvaluationRun) -> None:
        """Save final evaluation results."""
        path = self.output_path / f"{run.run_id}.json"
        with open(path, 'w') as f:
            json.dump(run.to_dict(), f, indent=2)

        # Also save summary as separate file
        summary_path = self.output_path / f"{run.run_id}_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(run.summary, f, indent=2)

        print(f"\nResults saved to: {path}")

    def _print_summary(self, summary: dict) -> None:
        """Print evaluation summary to console."""
        print(f"\n{'='*60}")
        print("MOLTBOT DDFT EVALUATION SUMMARY")
        print(f"{'='*60}\n")

        print(f"Total Agents Evaluated: {summary['total_agents']}")
        print(f"\nVerdict Distribution:")
        for verdict, count in summary['verdicts'].items():
            pct = count / summary['total_agents'] * 100 if summary['total_agents'] > 0 else 0
            bar = "#" * int(pct / 2)
            print(f"  {verdict:20s}: {count:3d} ({pct:5.1f}%) {bar}")

        print(f"\nScore Statistics:")
        stats = summary['statistics']
        print(f"  Mean:  {stats['mean_score']:.3f}")
        print(f"  Std:   {stats['std_score']:.3f}")
        print(f"  Range: [{stats['min_score']:.3f}, {stats['max_score']:.3f}]")

        print(f"\n{'='*60}")
        print("CONCLUSION:")
        print(f"{'='*60}")
        print(f"\n{summary['conclusion']}\n")


def run_moltbot_evaluation(
    experiments: Optional[List[str]] = None,
    target_agents: Optional[Dict[str, List[str]]] = None,
    output_dir: str = "moltbot_results"
) -> EvaluationRun:
    """
    Convenience function to run MoltBot DDFT evaluation.

    Args:
        experiments: List of experiments to run (default: all)
        target_agents: Optional pre-specified agents per experiment
        output_dir: Output directory for results

    Returns:
        EvaluationRun with all results
    """
    config = EvaluationConfig.from_env()

    if experiments:
        config.experiments = experiments
    if target_agents:
        config.target_agents = target_agents
        config.auto_discover = False
    config.output_dir = output_dir

    evaluator = MoltbotEvaluator(config)
    return evaluator.run_full_evaluation()
