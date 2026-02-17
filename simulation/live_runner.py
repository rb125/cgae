"""
Live Simulation Runner - CGAE economy with real LLM agents.

Unlike the synthetic runner (runner.py) which uses coin-flip task execution,
this runner:
1. Creates LLM agents backed by real Azure AI Foundry model endpoints
2. Assigns real tasks with concrete prompts from the task bank
3. Sends prompts to live models and receives actual outputs
4. Verifies outputs with algorithmic constraint checks + jury LLM evaluation
5. Settles contracts based on real verification results

Run:
  python -m simulation.live_runner

Required environment variables:
  AZURE_API_KEY              - Azure API key
  AZURE_OPENAI_API_ENDPOINT  - Azure OpenAI endpoint
  DDFT_MODELS_ENDPOINT       - Azure AI Foundry endpoint
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cgae_engine.gate import GateFunction, RobustnessVector, Tier
from cgae_engine.registry import AgentRegistry, AgentStatus
from cgae_engine.contracts import ContractManager, ContractStatus, Constraint
from cgae_engine.economy import Economy, EconomyConfig
from cgae_engine.temporal import TemporalDecay, StochasticAuditor
from cgae_engine.audit import AuditOrchestrator
from cgae_engine.llm_agent import LLMAgent, create_llm_agents
from cgae_engine.models_config import CONTESTANT_MODELS, JURY_MODELS, get_model_config
from cgae_engine.tasks import (
    Task, ALL_TASKS, TASKS_BY_TIER, get_tasks_for_tier, verify_output,
)
from cgae_engine.verifier import TaskVerifier, VerificationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default robustness profiles per model family (based on existing CDCT/DDFT/EECT results)
# These are starting points — real audits will refine them.
# ---------------------------------------------------------------------------

DEFAULT_ROBUSTNESS = {
    # OpenAI reasoning models: high CC and ER, variable AS
    "gpt-5":             RobustnessVector(cc=0.72, er=0.68, as_=0.55, ih=0.82),
    "o3":                RobustnessVector(cc=0.80, er=0.75, as_=0.42, ih=0.88),
    "o4-mini":           RobustnessVector(cc=0.65, er=0.60, as_=0.48, ih=0.78),
    # DeepSeek: strong ER, moderate CC
    "DeepSeek-v3.1":     RobustnessVector(cc=0.58, er=0.65, as_=0.50, ih=0.75),
    "DeepSeek-v3.2":     RobustnessVector(cc=0.62, er=0.68, as_=0.52, ih=0.78),
    # Meta Llama: moderate across the board
    "Llama-4-Maverick-17B-128E-Instruct-FP8": RobustnessVector(cc=0.45, er=0.42, as_=0.38, ih=0.65),
    # Small models: lower robustness
    "Phi-4":             RobustnessVector(cc=0.40, er=0.35, as_=0.32, ih=0.60),
    "gpt-oss-120b":      RobustnessVector(cc=0.48, er=0.45, as_=0.35, ih=0.68),
    # Others
    "grok-4-non-reasoning": RobustnessVector(cc=0.55, er=0.50, as_=0.45, ih=0.72),
    "mistral-medium-2505": RobustnessVector(cc=0.50, er=0.48, as_=0.40, ih=0.70),
    "Kimi-K2.5":         RobustnessVector(cc=0.52, er=0.55, as_=0.45, ih=0.73),
}


@dataclass
class LiveSimConfig:
    """Configuration for a live simulation run."""
    # How many task rounds to run (each round = 1 task per active agent)
    num_rounds: int = 10
    # Economy params
    initial_balance: float = 1.0
    decay_rate: float = 0.005
    audit_cost: float = 0.002
    storage_cost_per_step: float = 0.0003
    # Which models to use (by name). None = use all available.
    model_names: Optional[list[str]] = None
    # Output
    output_dir: str = "simulation/live_results"
    # Random seed
    seed: Optional[int] = 42


class LiveSimulationRunner:
    """
    Runs the CGAE economy with live LLM agents.

    Economic loop per round:
    1. Select a task for each active agent (matched to their tier)
    2. Agent executes the task (real LLM call)
    3. Verify output (algorithmic + jury)
    4. Settle contract (reward or penalty based on verification)
    5. Apply temporal dynamics
    6. Record metrics
    """

    def __init__(self, config: Optional[LiveSimConfig] = None):
        self.config = config or LiveSimConfig()
        if self.config.seed is not None:
            random.seed(self.config.seed)

        # Initialize economy
        econ_config = EconomyConfig(
            decay_rate=self.config.decay_rate,
            initial_balance=self.config.initial_balance,
            audit_cost=self.config.audit_cost,
            storage_cost_per_step=self.config.storage_cost_per_step,
        )
        self.economy = Economy(config=econ_config)
        self.audit = AuditOrchestrator()

        # LLM agents (populated in setup)
        self.llm_agents: dict[str, LLMAgent] = {}       # model_name -> LLMAgent
        self.agent_model_map: dict[str, str] = {}        # agent_id -> model_name
        self.jury_agents: list[LLMAgent] = []

        # Verifier (populated after jury agents created)
        self.verifier: Optional[TaskVerifier] = None

        # Metrics
        self._results: list[dict] = []
        self._round_summaries: list[dict] = []

    def setup(self):
        """Create LLM agents and register them in the economy."""
        # Determine which models to use
        if self.config.model_names:
            contestant_configs = [
                get_model_config(n) for n in self.config.model_names
                if get_model_config(n).get("tier_assignment") != "jury"
            ]
            jury_configs = [
                get_model_config(n) for n in self.config.model_names
                if get_model_config(n).get("tier_assignment") == "jury"
            ]
        else:
            contestant_configs = CONTESTANT_MODELS
            jury_configs = JURY_MODELS

        # Create jury agents first
        logger.info("Creating jury agents...")
        jury_dict = create_llm_agents(jury_configs)
        self.jury_agents = list(jury_dict.values())
        if self.jury_agents:
            logger.info(f"Jury agents: {[a.model_name for a in self.jury_agents]}")
        else:
            logger.warning("No jury agents available — T2+ tasks will use algorithmic-only verification")

        self.verifier = TaskVerifier(jury_agents=self.jury_agents)

        # Create contestant agents
        logger.info("Creating contestant agents...")
        self.llm_agents = create_llm_agents(contestant_configs)
        if not self.llm_agents:
            raise RuntimeError(
                "No LLM agents could be created. Check that AZURE_API_KEY "
                "and endpoint env vars are set."
            )

        # Register each in the economy
        for model_name, llm_agent in self.llm_agents.items():
            robustness = DEFAULT_ROBUSTNESS.get(
                model_name,
                RobustnessVector(cc=0.50, er=0.50, as_=0.45, ih=0.70),
            )

            record = self.economy.register_agent(
                model_name=model_name,
                model_config={"model": model_name, "provider": llm_agent.provider},
            )
            self.agent_model_map[record.agent_id] = model_name

            # Initial audit with default robustness
            self.economy.audit_agent(
                record.agent_id,
                robustness,
                audit_type="registration",
            )
            logger.info(
                f"Registered {model_name} -> {record.agent_id} "
                f"at tier {record.current_tier.name}"
            )

        logger.info(f"Setup complete: {len(self.llm_agents)} contestants, {len(self.jury_agents)} jury")

    def run(self) -> list[dict]:
        """Run all rounds of the live simulation."""
        self.setup()

        for round_num in range(self.config.num_rounds):
            logger.info(f"\n{'='*60}")
            logger.info(f"ROUND {round_num + 1}/{self.config.num_rounds}")
            logger.info(f"{'='*60}")

            round_results = self._run_round(round_num)
            self._round_summaries.append(round_results)

            # Apply temporal dynamics
            self.economy.step()

            # Log round summary
            safety = self.economy.aggregate_safety()
            active = len(self.economy.registry.active_agents)
            logger.info(
                f"Round {round_num + 1} complete | "
                f"Safety={safety:.3f} | Active={active} | "
                f"Tasks={round_results['tasks_attempted']} | "
                f"Passed={round_results['tasks_passed']}"
            )

        self._finalize()
        return self._results

    def _run_round(self, round_num: int) -> dict:
        """Execute one round: each active agent attempts one task."""
        round_data = {
            "round": round_num,
            "tasks_attempted": 0,
            "tasks_passed": 0,
            "tasks_failed": 0,
            "total_reward": 0.0,
            "total_penalty": 0.0,
            "task_results": [],
        }

        for agent in self.economy.registry.active_agents:
            model_name = self.agent_model_map.get(agent.agent_id)
            if not model_name or model_name not in self.llm_agents:
                continue

            llm_agent = self.llm_agents[model_name]
            tier = agent.current_tier

            # Pick a task appropriate for this agent's tier
            available_tasks = get_tasks_for_tier(tier)
            if not available_tasks:
                continue

            task = random.choice(available_tasks)

            # Post contract in the economy
            contract = self.economy.post_contract(
                objective=task.prompt[:100] + "...",
                constraints=[
                    Constraint(c.name, c.description, c.check)
                    for c in task.constraints
                ],
                min_tier=task.tier,
                reward=task.reward,
                penalty=task.penalty,
                deadline_offset=100.0,
                domain=task.domain,
                difficulty=task.difficulty,
            )

            # Accept contract
            accepted = self.economy.accept_contract(contract.contract_id, agent.agent_id)
            if not accepted:
                logger.debug(f"{model_name}: Could not accept {task.task_id} (tier/budget)")
                continue

            round_data["tasks_attempted"] += 1

            # Execute task with live LLM call
            logger.info(f"  {model_name} executing {task.task_id} (T{task.tier.value})...")
            start_time = time.time()
            try:
                output = llm_agent.execute_task(
                    prompt=task.prompt,
                    system_prompt=task.system_prompt,
                )
                latency = (time.time() - start_time) * 1000
            except Exception as e:
                logger.error(f"  {model_name} FAILED to execute: {e}")
                output = ""
                latency = (time.time() - start_time) * 1000

            # Verify output
            verification = self.verifier.verify(
                task=task,
                output=output,
                agent_model=model_name,
                latency_ms=latency,
            )

            # Settle contract based on verification
            # Pass raw output for contract constraint checks, but override with
            # TaskVerifier's overall_pass (which includes jury evaluation for T2+)
            settlement = self.economy.complete_contract(
                contract.contract_id,
                output,
                verification_override=verification.overall_pass,
            )

            # Log result
            task_result = {
                "agent": model_name,
                "agent_id": agent.agent_id,
                "task_id": task.task_id,
                "tier": task.tier.name,
                "domain": task.domain,
                "verification": verification.to_dict(),
                "settlement": settlement,
                "latency_ms": latency,
                "output_preview": output[:200] if output else "(empty)",
            }
            round_data["task_results"].append(task_result)
            self._results.append(task_result)

            if verification.overall_pass:
                round_data["tasks_passed"] += 1
                round_data["total_reward"] += task.reward
                status_str = "PASS"
            else:
                round_data["tasks_failed"] += 1
                round_data["total_penalty"] += task.penalty
                status_str = "FAIL"

            jury_str = f"{verification.jury_score:.2f}" if verification.jury_score is not None else "N/A"
            logger.info(
                f"  {model_name}: {task.task_id} -> {status_str} "
                f"(algo={'PASS' if verification.algorithmic_pass else 'FAIL'}, "
                f"jury={jury_str}) "
                f"[{latency:.0f}ms]"
            )
            if verification.constraints_failed:
                logger.info(f"    Failed constraints: {verification.constraints_failed}")

        return round_data

    def _finalize(self):
        """Compute final summary and save results."""
        pass

    def save_results(self, path: Optional[str] = None):
        """Save all results to disk."""
        output_dir = Path(path or self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Economy state
        self.economy.export_state(str(output_dir / "economy_state.json"))

        # Full task results
        (output_dir / "task_results.json").write_text(
            json.dumps(self._results, indent=2, default=str)
        )

        # Round summaries
        (output_dir / "round_summaries.json").write_text(
            json.dumps(self._round_summaries, indent=2, default=str)
        )

        # Verification summary
        if self.verifier:
            (output_dir / "verification_summary.json").write_text(
                json.dumps(self.verifier.summary(), indent=2)
            )

        # Per-agent details
        agent_details = {}
        for agent_id, model_name in self.agent_model_map.items():
            record = self.economy.registry.get_agent(agent_id)
            if record:
                llm = self.llm_agents.get(model_name)
                agent_details[model_name] = {
                    **record.to_dict(),
                    "llm_usage": llm.usage_summary() if llm else {},
                }
        (output_dir / "agent_details.json").write_text(
            json.dumps(agent_details, indent=2, default=str)
        )

        # Verification log
        if self.verifier:
            log_data = [v.to_dict() for v in self.verifier.verification_log]
            (output_dir / "verification_log.json").write_text(
                json.dumps(log_data, indent=2, default=str)
            )

        logger.info(f"Results saved to {output_dir}")


def main():
    """Entry point for running the live simulation."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Check env vars
    required_vars = ["AZURE_API_KEY"]
    optional_vars = ["AZURE_OPENAI_API_ENDPOINT", "DDFT_MODELS_ENDPOINT"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing required environment variables: {missing}")
        print(f"Optional (for more models): {optional_vars}")
        print("\nSet them with:")
        print("  export AZURE_API_KEY=your-key")
        print("  export AZURE_OPENAI_API_ENDPOINT=https://your-endpoint.openai.azure.com/")
        print("  export DDFT_MODELS_ENDPOINT=https://your-foundry-endpoint/v1")
        return

    available = [v for v in optional_vars if os.environ.get(v)]
    print(f"Endpoints available: {available}")

    config = LiveSimConfig(
        num_rounds=10,
        seed=42,
    )

    runner = LiveSimulationRunner(config)
    results = runner.run()
    runner.save_results()

    # Print summary
    print("\n" + "=" * 60)
    print("CGAE LIVE ECONOMY - RESULTS")
    print("=" * 60)

    if runner.verifier:
        vs = runner.verifier.summary()
        print(f"\nTotal tasks executed: {vs.get('total', 0)}")
        print(f"Algorithmic pass rate: {vs.get('algorithmic_pass_rate', 0):.1%}")
        if vs.get("jury_pass_rate") is not None:
            print(f"Jury pass rate: {vs['jury_pass_rate']:.1%}")
        print(f"Overall pass rate: {vs.get('overall_pass_rate', 0):.1%}")
        if vs.get("avg_jury_score") is not None:
            print(f"Average jury score: {vs['avg_jury_score']:.3f}")

    print(f"\nAggregate safety: {runner.economy.aggregate_safety():.4f}")

    print("\n--- Agent Results ---")
    for model_name in sorted(runner.llm_agents.keys()):
        agent_id = None
        for aid, mn in runner.agent_model_map.items():
            if mn == model_name:
                agent_id = aid
                break
        if not agent_id:
            continue
        record = runner.economy.registry.get_agent(agent_id)
        if record:
            llm = runner.llm_agents[model_name]
            usage = llm.usage_summary()
            print(
                f"  {model_name:25s} | tier={record.current_tier.name} | "
                f"earned={record.total_earned:.4f} | "
                f"penalties={record.total_penalties:.4f} | "
                f"balance={record.balance:.4f} | "
                f"calls={usage['total_calls']} | "
                f"tokens={usage['total_input_tokens']+usage['total_output_tokens']}"
            )

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
