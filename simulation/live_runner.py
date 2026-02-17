"""
Live Simulation Runner - CGAE economy with real LLM agents.

Unlike the synthetic runner (runner.py) which uses coin-flip task execution,
this runner:
1. Creates LLM agents backed by real Azure AI Foundry model endpoints
2. Assigns real tasks with concrete prompts from the task bank
3. Sends prompts to live models and receives actual outputs
4. Verifies outputs with algorithmic constraint checks + jury LLM evaluation
5. Settles contracts based on real verification results
6. Updates robustness vectors in real-time based on task outcomes
7. Deducts token-based costs from agent balances

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
import math
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
# Default robustness profiles per model family (fallback when framework
# results are unavailable)
# ---------------------------------------------------------------------------

DEFAULT_ROBUSTNESS = {
    "gpt-5":             RobustnessVector(cc=0.72, er=0.68, as_=0.55, ih=0.82),
    "o3":                RobustnessVector(cc=0.80, er=0.75, as_=0.42, ih=0.88),
    "o4-mini":           RobustnessVector(cc=0.65, er=0.60, as_=0.48, ih=0.78),
    "DeepSeek-v3.1":     RobustnessVector(cc=0.58, er=0.65, as_=0.50, ih=0.75),
    "DeepSeek-v3.2":     RobustnessVector(cc=0.62, er=0.68, as_=0.52, ih=0.78),
    "Llama-4-Maverick-17B-128E-Instruct-FP8": RobustnessVector(cc=0.45, er=0.42, as_=0.38, ih=0.65),
    "Phi-4":             RobustnessVector(cc=0.40, er=0.35, as_=0.32, ih=0.60),
    "gpt-oss-120b":      RobustnessVector(cc=0.48, er=0.45, as_=0.35, ih=0.68),
    "grok-4-fast-non-reasoning": RobustnessVector(cc=0.55, er=0.50, as_=0.45, ih=0.72),
    "mistral-medium-2505": RobustnessVector(cc=0.50, er=0.48, as_=0.40, ih=0.70),
    "Kimi-K2.5":         RobustnessVector(cc=0.52, er=0.55, as_=0.45, ih=0.73),
}


# ---------------------------------------------------------------------------
# Token cost rates (USD per 1K tokens) — used for economic cost accounting
# ---------------------------------------------------------------------------

TOKEN_COSTS = {
    # Azure OpenAI models
    "gpt-5":        {"input": 0.010, "output": 0.030},
    "gpt-5.1":      {"input": 0.010, "output": 0.030},
    "gpt-5.2":      {"input": 0.010, "output": 0.030},
    "o3":           {"input": 0.015, "output": 0.060},
    "o4-mini":      {"input": 0.003, "output": 0.012},
    # Azure AI Foundry models
    "DeepSeek-v3.1":  {"input": 0.001, "output": 0.002},
    "DeepSeek-v3.2":  {"input": 0.001, "output": 0.002},
    "Llama-4-Maverick-17B-128E-Instruct-FP8": {"input": 0.001, "output": 0.001},
    "Phi-4":          {"input": 0.0005, "output": 0.001},
    "grok-4-non-reasoning": {"input": 0.003, "output": 0.015},
    "mistral-medium-2505":  {"input": 0.002, "output": 0.006},
    "gpt-oss-120b":         {"input": 0.002, "output": 0.006},
    "Kimi-K2.5":            {"input": 0.001, "output": 0.002},
}

# Conversion: 1 USD ≈ 5 FIL for cost accounting.
# Rationale: at 100 FIL/USD the token cost for a typical T2 call
# (~0.001 USD) is 0.10 FIL — far exceeding the 0.012-0.015 FIL T2
# reward, making profitable operation structurally impossible.
# At 5 FIL/USD a cheap model (DeepSeek) spends ~0.005 FIL per task
# and earns 0.012-0.015 FIL on success, so Theorem 2's incentive-
# compatibility result can manifest empirically.
USD_TO_FIL = 5.0


def compute_token_cost_fil(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Convert token usage to FIL cost."""
    rates = TOKEN_COSTS.get(model_name, {"input": 0.002, "output": 0.006})
    usd_cost = (input_tokens / 1000.0) * rates["input"] + (output_tokens / 1000.0) * rates["output"]
    return usd_cost * USD_TO_FIL


# ---------------------------------------------------------------------------
# Robustness update logic
# ---------------------------------------------------------------------------

# How much to adjust robustness per constraint pass/fail
ROBUSTNESS_UPDATE_RATE = 0.01  # Small EMA-style update
ROBUSTNESS_DECAY_ON_FAIL = 0.015  # Slightly larger penalty for failure


def update_robustness_from_verification(
    current: RobustnessVector,
    task: Task,
    verification: VerificationResult,
) -> RobustnessVector:
    """
    Update an agent's robustness vector based on task verification results.

    Each constraint maps to a robustness dimension (cc, er, as). On pass,
    the dimension gets a small upward nudge; on failure, a larger downward
    nudge. This creates an empirical robustness trajectory.
    """
    cc_delta = 0.0
    er_delta = 0.0
    as_delta = 0.0
    cc_count = 0
    er_count = 0
    as_count = 0

    for constraint in task.constraints:
        passed = constraint.name in verification.constraints_passed
        dim = constraint.dimension

        if dim == "cc":
            cc_count += 1
            cc_delta += ROBUSTNESS_UPDATE_RATE if passed else -ROBUSTNESS_DECAY_ON_FAIL
        elif dim == "er":
            er_count += 1
            er_delta += ROBUSTNESS_UPDATE_RATE if passed else -ROBUSTNESS_DECAY_ON_FAIL
        elif dim == "as":
            as_count += 1
            as_delta += ROBUSTNESS_UPDATE_RATE if passed else -ROBUSTNESS_DECAY_ON_FAIL

    # Normalize by count so tasks with many constraints in one dimension
    # don't cause outsized updates
    if cc_count > 0:
        cc_delta /= cc_count
    if er_count > 0:
        er_delta /= er_count
    if as_count > 0:
        as_delta /= as_count

    # IH: nudge based on overall pass (proxy for epistemic integrity)
    ih_delta = ROBUSTNESS_UPDATE_RATE * 0.5 if verification.overall_pass else -ROBUSTNESS_DECAY_ON_FAIL * 0.5

    def clamp(val: float) -> float:
        return max(0.0, min(1.0, val))

    return RobustnessVector(
        cc=clamp(current.cc + cc_delta),
        er=clamp(current.er + er_delta),
        as_=clamp(current.as_ + as_delta),
        ih=clamp(current.ih + ih_delta),
    )


@dataclass
class LiveSimConfig:
    """Configuration for a live simulation run."""
    num_rounds: int = 10
    initial_balance: float = 1.0
    decay_rate: float = 0.005
    audit_cost: float = 0.002
    storage_cost_per_step: float = 0.0003
    model_names: Optional[list[str]] = None
    output_dir: str = "simulation/live_results"
    seed: Optional[int] = 42
    # Framework result directories for real audit data
    ddft_results_dir: Optional[str] = None
    eect_results_dir: Optional[str] = None
    cdct_results_dir: Optional[str] = None


class LiveSimulationRunner:
    """
    Runs the CGAE economy with live LLM agents.

    Economic loop per round:
    1. Select a task for each active agent (matched to their tier)
    2. Agent executes the task (real LLM call)
    3. Verify output (algorithmic + jury)
    4. Deduct token costs from agent balance
    5. Update robustness vector based on constraint outcomes
    6. Settle contract (reward or penalty based on verification)
    7. Apply temporal dynamics
    8. Record metrics
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

        # Initialize audit orchestrator with framework directories
        self.audit = AuditOrchestrator(
            ddft_results_dir=self.config.ddft_results_dir,
            eect_results_dir=self.config.eect_results_dir,
            cdct_results_dir=self.config.cdct_results_dir,
        )

        # LLM agents (populated in setup)
        self.llm_agents: dict[str, LLMAgent] = {}
        self.agent_model_map: dict[str, str] = {}
        self.jury_agents: list[LLMAgent] = []

        # Verifier (populated after jury agents created)
        self.verifier: Optional[TaskVerifier] = None

        # Cost tracking
        self._token_costs: dict[str, float] = {}  # agent_id -> total FIL spent on tokens

        # Audit data quality: model_name -> {"source": "real"|"default", "dims_defaulted": [...]}
        self._audit_quality: dict[str, dict] = {}

        # Metrics
        self._results: list[dict] = []
        self._round_summaries: list[dict] = []
        self._final_summary: Optional[dict] = None

    def _resolve_initial_robustness(self, model_name: str, agent_id: str) -> RobustnessVector:
        """
        Resolve initial robustness per dimension.

        For each of CC, ER, AS, IH:
          1. Try to load the value from the corresponding framework results directory.
          2. If no real data exists for that dimension, substitute the value from
             DEFAULT_ROBUSTNESS (or the generic fallback vector) rather than the
             blind midpoint 0.5.

        This ensures that CC never appears as a flat 0.50 line simply because no
        CDCT results directory was configured — instead it uses the per-model
        estimate from DEFAULT_ROBUSTNESS while ER/AS/IH may still be real data.

        Tracking is written to ``self._audit_quality[model_name]`` so callers can
        clearly distinguish fully-audited agents from partially- or fully-defaulted
        ones.
        """
        fallback = DEFAULT_ROBUSTNESS.get(
            model_name,
            RobustnessVector(cc=0.50, er=0.50, as_=0.45, ih=0.70),
        )

        has_frameworks = (
            self.config.ddft_results_dir
            or self.config.eect_results_dir
            or self.config.cdct_results_dir
        )

        dims_real: list[str] = []
        dims_defaulted: list[str] = []

        if has_frameworks:
            try:
                audit_result = self.audit.audit_from_results(agent_id, model_name)
                r = audit_result.robustness
                defaulted = audit_result.defaults_used  # set of dim names

                # Per-dimension merge: real data where available, DEFAULT_ROBUSTNESS otherwise
                cc  = fallback.cc   if "cc"  in defaulted else r.cc
                er  = fallback.er   if "er"  in defaulted else r.er
                as_ = fallback.as_  if "as"  in defaulted else r.as_
                ih  = fallback.ih   if "ih"  in defaulted else r.ih

                dims_real      = sorted({"cc", "er", "as", "ih"} - defaulted)
                dims_defaulted = sorted(defaulted)

                source = "real_audit" if not defaulted else (
                    "partial_audit" if dims_real else "default_robustness"
                )
                logger.info(
                    f"  {model_name}: CC={cc:.3f} ER={er:.3f} AS={as_:.3f} IH={ih:.3f} "
                    f"[{source}; real={dims_real}, default={dims_defaulted}]"
                )
                self._audit_quality[model_name] = {
                    "source": source,
                    "dims_real": dims_real,
                    "dims_defaulted": dims_defaulted,
                }
                return RobustnessVector(cc=cc, er=er, as_=as_, ih=ih)

            except Exception as e:
                logger.warning(f"  Failed to load audit results for {model_name}: {e}")

        # No framework dirs at all — use hardcoded defaults for every dimension
        self._audit_quality[model_name] = {
            "source": "default_robustness",
            "dims_real": [],
            "dims_defaulted": ["cc", "er", "as", "ih"],
        }
        logger.info(
            f"  {model_name}: Using default robustness "
            f"CC={fallback.cc:.3f} ER={fallback.er:.3f} AS={fallback.as_:.3f} IH={fallback.ih:.3f}"
        )
        return fallback

    def setup(self):
        """Create LLM agents and register them in the economy."""
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
            logger.warning("No jury agents — T2+ tasks use algorithmic-only verification")

        self.verifier = TaskVerifier(jury_agents=self.jury_agents)

        # Create contestant agents
        logger.info("Creating contestant agents...")
        self.llm_agents = create_llm_agents(contestant_configs)
        if not self.llm_agents:
            raise RuntimeError(
                "No LLM agents could be created. Check that AZURE_API_KEY "
                "and endpoint env vars are set."
            )

        # Register each in the economy with real or default robustness
        for model_name, llm_agent in self.llm_agents.items():
            record = self.economy.register_agent(
                model_name=model_name,
                model_config={"model": model_name, "provider": llm_agent.provider},
            )
            self.agent_model_map[record.agent_id] = model_name
            self._token_costs[record.agent_id] = 0.0

            robustness = self._resolve_initial_robustness(model_name, record.agent_id)
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
            "total_token_cost": 0.0,
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

            # Snapshot token counts before execution
            tokens_before_in = llm_agent.total_input_tokens
            tokens_before_out = llm_agent.total_output_tokens

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

            # Cost accounting: deduct token costs from agent balance
            new_input = llm_agent.total_input_tokens - tokens_before_in
            new_output = llm_agent.total_output_tokens - tokens_before_out
            token_cost = compute_token_cost_fil(model_name, new_input, new_output)
            agent.balance -= token_cost
            agent.total_spent += token_cost
            self._token_costs[agent.agent_id] = self._token_costs.get(agent.agent_id, 0.0) + token_cost
            round_data["total_token_cost"] += token_cost

            # Verify output
            verification = self.verifier.verify(
                task=task,
                output=output,
                agent_model=model_name,
                latency_ms=latency,
            )

            # Real-time robustness update based on constraint outcomes
            if agent.current_robustness is not None:
                new_robustness = update_robustness_from_verification(
                    agent.current_robustness, task, verification,
                )
                self.economy.registry.certify(
                    agent.agent_id,
                    new_robustness,
                    audit_type="task_update",
                    timestamp=self.economy.current_time,
                )

            # Settle contract based on verification
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
                "token_cost_fil": token_cost,
                "tokens_used": {"input": new_input, "output": new_output},
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
                f"jury={jury_str}, cost={token_cost:.4f} FIL) "
                f"[{latency:.0f}ms]"
            )
            if verification.constraints_failed:
                logger.info(f"    Failed constraints: {verification.constraints_failed}")

        return round_data

    def _finalize(self):
        """Compute final summary statistics."""
        agents_data = []
        for agent_id, model_name in self.agent_model_map.items():
            record = self.economy.registry.get_agent(agent_id)
            if not record:
                continue
            llm = self.llm_agents.get(model_name)
            usage = llm.usage_summary() if llm else {}
            aq = self._audit_quality.get(model_name, {
                "source": "unknown",
                "dims_real": [],
                "dims_defaulted": ["cc", "er", "as", "ih"],
            })
            agents_data.append({
                "model_name": model_name,
                "agent_id": agent_id,
                "tier": record.current_tier.value,
                "tier_name": record.current_tier.name,
                "balance": record.balance,
                "total_earned": record.total_earned,
                "total_penalties": record.total_penalties,
                "total_spent": record.total_spent,
                "token_cost_fil": self._token_costs.get(agent_id, 0.0),
                "net_profit": record.total_earned - record.total_penalties - record.total_spent,
                "contracts_completed": record.contracts_completed,
                "contracts_failed": record.contracts_failed,
                "success_rate": (
                    record.contracts_completed / max(1, record.contracts_completed + record.contracts_failed)
                ),
                "robustness": {
                    "cc": record.current_robustness.cc,
                    "er": record.current_robustness.er,
                    "as": record.current_robustness.as_,
                    "ih": record.current_robustness.ih,
                } if record.current_robustness else None,
                # Audit data provenance — critical for paper claims
                "audit_data_source": aq["source"],
                "audit_dims_real": aq["dims_real"],
                "audit_dims_defaulted": aq["dims_defaulted"],
                "llm_usage": usage,
            })

        # Gini coefficient of balances
        balances = sorted([a["balance"] for a in agents_data])
        gini = self._compute_gini(balances)

        # Tier distribution
        tier_dist = self.economy.registry.tier_distribution()

        # Per-round trajectory
        safety_trajectory = []
        for snap in self.economy.snapshots:
            safety_trajectory.append({
                "time": snap.timestamp,
                "safety": snap.aggregate_safety,
                "active_agents": snap.num_agents,
                "total_balance": snap.total_balance,
            })

        # Verification stats
        v_summary = self.verifier.summary() if self.verifier else {}

        # Total token costs
        total_token_cost = sum(self._token_costs.values())

        # Data quality audit — list agents with unverified robustness dimensions
        unaudited_agents = [
            {
                "model_name": a["model_name"],
                "audit_source": a["audit_data_source"],
                "dims_defaulted": a["audit_dims_defaulted"],
                "tier_name": a["tier_name"],
            }
            for a in agents_data
            if a["audit_dims_defaulted"]
        ]

        self._final_summary = {
            "economy": {
                "aggregate_safety": self.economy.aggregate_safety(),
                "total_rewards_paid": sum(r["total_reward"] for r in self._round_summaries),
                "total_penalties_collected": sum(r["total_penalty"] for r in self._round_summaries),
                "total_token_cost_fil": total_token_cost,
                "usd_to_fil_rate": USD_TO_FIL,
                "gini_coefficient": gini,
                "num_rounds": self.config.num_rounds,
                "num_agents": len(agents_data),
                "active_agents": len(self.economy.registry.active_agents),
            },
            "tier_distribution": {t.name: c for t, c in tier_dist.items()},
            "verification": v_summary,
            "agents": sorted(agents_data, key=lambda a: a["balance"], reverse=True),
            "safety_trajectory": safety_trajectory,
            # ---------------------------------------------------------------
            # Paper note: agents listed here have one or more robustness
            # dimensions drawn from DEFAULT_ROBUSTNESS rather than verified
            # framework results.  Their tier assignments are estimates, not
            # certified values.  They should be reported separately from
            # fully-audited agents in any empirical claim about CGAE gating.
            # ---------------------------------------------------------------
            "data_quality_warnings": {
                "num_partially_or_fully_defaulted": len(unaudited_agents),
                "unaudited_agents": unaudited_agents,
            },
        }

    @staticmethod
    def _compute_gini(values: list[float]) -> float:
        """Compute Gini coefficient for a sorted list of values."""
        n = len(values)
        if n == 0:
            return 0.0
        total = sum(values)
        if total == 0:
            return 0.0
        cumulative = 0.0
        weighted_sum = 0.0
        for i, v in enumerate(values):
            cumulative += v
            weighted_sum += (2 * (i + 1) - n - 1) * v
        return weighted_sum / (n * total)

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

        # Final summary
        if self._final_summary:
            (output_dir / "final_summary.json").write_text(
                json.dumps(self._final_summary, indent=2, default=str)
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
                    "token_cost_fil": self._token_costs.get(agent_id, 0.0),
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

    # Auto-detect framework result directories
    base = Path(__file__).resolve().parent.parent
    ddft_dir = base / "ddft_framework" / "results"
    eect_dir = base / "eect_framework" / "results"
    cdct_dir = None  # No pre-computed CDCT results available yet

    config = LiveSimConfig(
        num_rounds=10,
        seed=42,
        ddft_results_dir=str(ddft_dir) if ddft_dir.exists() else None,
        eect_results_dir=str(eect_dir) if eect_dir.exists() else None,
        cdct_results_dir=str(cdct_dir) if cdct_dir and Path(cdct_dir).exists() else None,
    )

    runner = LiveSimulationRunner(config)
    results = runner.run()
    runner.save_results()

    # Print summary
    print("\n" + "=" * 60)
    print("CGAE LIVE ECONOMY - RESULTS")
    print("=" * 60)

    if runner._final_summary:
        econ = runner._final_summary["economy"]
        print(f"\nRounds: {econ['num_rounds']}")
        print(f"Agents: {econ['num_agents']} ({econ['active_agents']} active)")
        print(f"Aggregate safety: {econ['aggregate_safety']:.4f}")
        print(f"Gini coefficient: {econ['gini_coefficient']:.4f}")
        print(f"Total rewards: {econ['total_rewards_paid']:.4f} FIL")
        print(f"Total penalties: {econ['total_penalties_collected']:.4f} FIL")
        print(f"Total token costs: {econ['total_token_cost_fil']:.4f} FIL")

    if runner.verifier:
        vs = runner.verifier.summary()
        print(f"\nVerification: {vs.get('total', 0)} tasks")
        print(f"  Algorithmic pass rate: {vs.get('algorithmic_pass_rate', 0):.1%}")
        if vs.get("jury_pass_rate") is not None:
            print(f"  Jury pass rate: {vs['jury_pass_rate']:.1%}")
        print(f"  Overall pass rate: {vs.get('overall_pass_rate', 0):.1%}")
        if vs.get("avg_jury_score") is not None:
            print(f"  Avg jury score: {vs['avg_jury_score']:.3f}")

    print("\n--- Agent Leaderboard ---")
    print(f"  {'Model':40s}  {'Tier':3s}  {'Bal':>8}  {'Earned':>8}  "
          f"{'Pen':>7}  {'Cost':>7}  W/L    CC    ER    AS   AuditSrc")
    if runner._final_summary:
        for a in runner._final_summary["agents"]:
            r = a.get("robustness") or {}
            # Show a short audit source tag; highlight defaulted dimensions
            src = a.get("audit_data_source", "?")
            defaulted = a.get("audit_dims_defaulted", [])
            src_tag = src if not defaulted else f"{src}[def:{','.join(defaulted)}]"
            print(
                f"  {a['model_name']:40s} | {a['tier_name']:3s} | "
                f"bal={a['balance']:8.4f} | earned={a['total_earned']:8.4f} | "
                f"pen={a['total_penalties']:7.4f} | cost={a['token_cost_fil']:7.4f} | "
                f"W/L={a['contracts_completed']}/{a['contracts_failed']} | "
                f"CC={r.get('cc', 0):.2f} ER={r.get('er', 0):.2f} AS={r.get('as', 0):.2f} | "
                f"{src_tag}"
            )

        dqw = runner._final_summary.get("data_quality_warnings", {})
        if dqw.get("num_partially_or_fully_defaulted", 0) > 0:
            print(f"\n  *** DATA QUALITY NOTE ***")
            print(f"  {dqw['num_partially_or_fully_defaulted']} agent(s) used assumed (not verified) "
                  f"robustness for one or more dimensions.")
            print(f"  These agents' tier assignments are estimates. See 'data_quality_warnings' "
                  f"in final_summary.json for details.")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
