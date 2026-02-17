"""
CGAE Economy - The top-level coordinator.

Ties together registry, gate, contracts, temporal dynamics, and auditing
into a single coherent economic system. This is the main entry point for
running the agent economy.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cgae_engine.gate import GateFunction, RobustnessVector, Tier, TierThresholds
from cgae_engine.temporal import TemporalDecay, StochasticAuditor, AuditEvent
from cgae_engine.registry import AgentRegistry, AgentRecord, AgentStatus
from cgae_engine.contracts import ContractManager, CGAEContract, ContractStatus, Constraint

logger = logging.getLogger(__name__)


@dataclass
class EconomyConfig:
    """Configuration for the CGAE economy."""
    # Tier thresholds
    thresholds: TierThresholds = field(default_factory=TierThresholds)
    # Temporal decay rate (lambda)
    decay_rate: float = 0.01
    # IHT threshold for mandatory re-audit
    ih_threshold: float = 0.5
    # Initial balance for new agents (seed capital)
    initial_balance: float = 0.1  # FIL
    # Audit cost per dimension
    audit_cost: float = 0.005  # FIL per audit dimension
    # Storage cost per time step (FOC)
    storage_cost_per_step: float = 0.001  # FIL


@dataclass
class EconomySnapshot:
    """A point-in-time snapshot of the economy for the dashboard."""
    timestamp: float
    num_agents: int
    tier_distribution: dict[str, int]
    total_contracts: int
    completed_contracts: int
    failed_contracts: int
    total_rewards_paid: float
    total_penalties_collected: float
    aggregate_safety: float
    total_balance: float
    agent_summaries: list[dict]


class Economy:
    """
    The CGAE Economy runtime.

    Orchestrates the full economic loop:
    1. Agent registration and initial audit
    2. Contract creation and marketplace
    3. Contract assignment (tier-gated)
    4. Task execution and verification
    5. Settlement (reward/penalty)
    6. Temporal decay and stochastic re-auditing
    7. Economic accounting and observability
    """

    def __init__(self, config: Optional[EconomyConfig] = None):
        self.config = config or EconomyConfig()
        self.gate = GateFunction(
            thresholds=self.config.thresholds,
            ih_threshold=self.config.ih_threshold,
        )
        self.registry = AgentRegistry(gate=self.gate)
        self.contracts = ContractManager(budget_ceilings=self.gate.budget_ceilings)
        self.decay = TemporalDecay(decay_rate=self.config.decay_rate)
        self.auditor = StochasticAuditor()

        self.current_time: float = 0.0
        self._snapshots: list[EconomySnapshot] = []
        self._events: list[dict] = []

    # ------------------------------------------------------------------
    # Agent lifecycle
    # ------------------------------------------------------------------

    def register_agent(
        self,
        model_name: str,
        model_config: dict,
        provenance: Optional[dict] = None,
    ) -> AgentRecord:
        """Register a new agent with seed capital."""
        record = self.registry.register(
            model_name=model_name,
            model_config=model_config,
            provenance=provenance,
            initial_balance=self.config.initial_balance,
            timestamp=self.current_time,
        )
        self._log("agent_registered", {"agent_id": record.agent_id, "model": model_name})
        return record

    def audit_agent(
        self,
        agent_id: str,
        robustness: RobustnessVector,
        audit_type: str = "registration",
    ) -> dict:
        """
        Audit an agent and update their certification.
        Deducts audit cost from agent balance.
        """
        record = self.registry.get_agent(agent_id)
        if record is None:
            raise KeyError(f"Agent {agent_id} not found")

        # Deduct audit cost (3 dimensions + IHT)
        total_audit_cost = self.config.audit_cost * 4
        record.balance -= total_audit_cost
        record.total_spent += total_audit_cost

        # Certify with new robustness
        cert = self.registry.certify(
            agent_id=agent_id,
            robustness=robustness,
            audit_type=audit_type,
            timestamp=self.current_time,
        )

        detail = self.gate.evaluate_with_detail(robustness)
        self._log("agent_audited", {
            "agent_id": agent_id,
            "tier": cert.tier.name,
            "audit_type": audit_type,
            "cost": total_audit_cost,
            **detail,
        })
        return detail

    # ------------------------------------------------------------------
    # Contract lifecycle
    # ------------------------------------------------------------------

    def post_contract(
        self,
        objective: str,
        constraints: list[Constraint],
        min_tier: Tier,
        reward: float,
        penalty: float,
        deadline_offset: float = 100.0,
        domain: str = "general",
        difficulty: float = 0.5,
        issuer_id: str = "system",
    ) -> CGAEContract:
        """Post a new contract to the marketplace."""
        return self.contracts.create_contract(
            objective=objective,
            constraints=constraints,
            min_tier=min_tier,
            reward=reward,
            penalty=penalty,
            issuer_id=issuer_id,
            deadline=self.current_time + deadline_offset,
            domain=domain,
            difficulty=difficulty,
            timestamp=self.current_time,
        )

    def accept_contract(self, contract_id: str, agent_id: str) -> bool:
        """Agent accepts a contract. Enforces tier and budget ceiling."""
        record = self.registry.get_agent(agent_id)
        if record is None or record.status != AgentStatus.ACTIVE:
            return False

        # Compute effective tier with temporal decay
        if record.current_certification is None:
            return False

        dt = self.current_time - record.current_certification.timestamp
        r_eff = self.decay.effective_robustness(record.current_robustness, dt)
        effective_tier = self.gate.evaluate(r_eff)

        return self.contracts.assign_contract(
            contract_id=contract_id,
            agent_id=agent_id,
            agent_tier=effective_tier,
            timestamp=self.current_time,
        )

    def complete_contract(
        self,
        contract_id: str,
        output: Any,
        verification_override: Optional[bool] = None,
    ) -> dict:
        """
        Submit output for a contract and settle it.

        If verification_override is provided, it overrides the contract's own
        constraint check. This allows external verification (e.g., jury LLM
        evaluation from TaskVerifier) to drive the settlement outcome.
        """
        passed, failures = self.contracts.submit_output(
            contract_id=contract_id,
            output=output,
            timestamp=self.current_time,
        )

        # Allow external verification to override contract-level constraints
        if verification_override is not None:
            contract = self.contracts._get_contract(contract_id)
            contract.verification_result = verification_override
            if not verification_override and not failures:
                failures = ["jury_verification_failed"]

        settlement = self.contracts.settle_contract(
            contract_id=contract_id,
            timestamp=self.current_time,
        )

        # Update agent balance
        agent_id = settlement["agent_id"]
        record = self.registry.get_agent(agent_id)
        if record:
            if settlement["outcome"] == "success":
                record.balance += settlement["reward"]
                record.total_earned += settlement["reward"]
                record.contracts_completed += 1
            else:
                record.balance -= settlement["penalty"]
                record.total_penalties += settlement["penalty"]
                record.contracts_failed += 1

        settlement["failures"] = failures
        self._log("contract_settled", settlement)
        return settlement

    # ------------------------------------------------------------------
    # Time step and temporal dynamics
    # ------------------------------------------------------------------

    def step(self, audit_callback=None) -> dict:
        """
        Advance the economy by one time step.

        - Applies temporal decay
        - Checks for stochastic spot-audits
        - Deducts storage costs (FOC)
        - Expires overdue contracts
        - Takes a snapshot

        audit_callback: Optional callable(agent_id) -> RobustnessVector
            If provided, called when a spot-audit is triggered.
            If None, spot-audits use decayed robustness (no fresh eval).
        """
        self.current_time += 1.0
        step_events = {
            "timestamp": self.current_time,
            "audits_triggered": [],
            "agents_demoted": [],
            "agents_expired": [],
            "contracts_expired": [],
            "storage_costs": 0.0,
        }

        # 1. Process each active agent
        for agent in self.registry.active_agents:
            cert = agent.current_certification
            if cert is None:
                continue

            # Temporal decay check: has effective tier dropped?
            dt = self.current_time - cert.timestamp
            r_eff = self.decay.effective_robustness(cert.robustness, dt)
            effective_tier = self.gate.evaluate(r_eff)

            if effective_tier < agent.current_tier:
                # Decay caused tier drop — update certification
                self.registry.certify(
                    agent.agent_id, r_eff,
                    audit_type="decay",
                    timestamp=self.current_time,
                )
                step_events["agents_expired"].append(agent.agent_id)

            # Stochastic spot-audit
            time_since_audit = self.current_time - agent.last_audit_time
            if self.auditor.should_audit(agent.current_tier, time_since_audit):
                step_events["audits_triggered"].append(agent.agent_id)

                if audit_callback:
                    new_r = audit_callback(agent.agent_id)
                else:
                    new_r = r_eff  # Use decayed robustness as proxy

                new_tier = self.gate.evaluate(new_r)
                if new_tier < agent.current_tier:
                    self.registry.demote(
                        agent.agent_id, new_r,
                        reason="spot_audit",
                        timestamp=self.current_time,
                    )
                    step_events["agents_demoted"].append(agent.agent_id)
                else:
                    # Re-certify at current level (refreshes timestamp)
                    self.registry.certify(
                        agent.agent_id, new_r,
                        audit_type="spot",
                        timestamp=self.current_time,
                    )

                # Charge audit cost
                audit_cost = self.config.audit_cost * 4
                agent.balance -= audit_cost
                agent.total_spent += audit_cost

            # Storage cost (FOC)
            agent.balance -= self.config.storage_cost_per_step
            agent.total_spent += self.config.storage_cost_per_step
            step_events["storage_costs"] += self.config.storage_cost_per_step

            # Check for insolvency
            if agent.balance <= 0:
                agent.status = AgentStatus.SUSPENDED
                self._log("agent_insolvent", {
                    "agent_id": agent.agent_id,
                    "balance": agent.balance,
                })

        # 2. Expire overdue contracts
        expired = self.contracts.expire_contracts(self.current_time)
        step_events["contracts_expired"] = expired

        # 3. Take snapshot
        snapshot = self._take_snapshot()
        self._snapshots.append(snapshot)

        self._log("step", step_events)
        return step_events

    # ------------------------------------------------------------------
    # Aggregate safety (Definition 9, Theorem 3)
    # ------------------------------------------------------------------

    def aggregate_safety(self) -> float:
        """
        Compute aggregate safety S(P) (Definition 9).
        S(P) = 1 - sum(E(A) * (1 - R_bar(A))) / sum(E(A))
        where R_bar(A) = min_i R_eff,i(A) is the weakest-link robustness.
        """
        total_exposure = 0.0
        weighted_risk = 0.0

        for agent in self.registry.active_agents:
            cert = agent.current_certification
            if cert is None:
                continue
            dt = self.current_time - cert.timestamp
            r_eff = self.decay.effective_robustness(cert.robustness, dt)
            exposure = self.contracts.agent_exposure(agent.agent_id)
            if exposure <= 0:
                # Use budget ceiling as potential exposure
                tier = self.gate.evaluate(r_eff)
                exposure = self.gate.budget_ceiling(tier)

            r_bar = r_eff.weakest
            total_exposure += exposure
            weighted_risk += exposure * (1.0 - r_bar)

        if total_exposure == 0:
            return 1.0
        return 1.0 - (weighted_risk / total_exposure)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def _take_snapshot(self) -> EconomySnapshot:
        tier_dist = self.registry.tier_distribution()
        econ = self.contracts.economics_summary()
        agents = self.registry.active_agents

        return EconomySnapshot(
            timestamp=self.current_time,
            num_agents=len(agents),
            tier_distribution={t.name: c for t, c in tier_dist.items()},
            total_contracts=econ["total_contracts"],
            completed_contracts=econ["status_distribution"].get("completed", 0),
            failed_contracts=econ["status_distribution"].get("failed", 0),
            total_rewards_paid=econ["total_rewards_paid"],
            total_penalties_collected=econ["total_penalties_collected"],
            aggregate_safety=self.aggregate_safety(),
            total_balance=sum(a.balance for a in agents),
            agent_summaries=[a.to_dict() for a in agents],
        )

    @property
    def snapshots(self) -> list[EconomySnapshot]:
        return list(self._snapshots)

    @property
    def events(self) -> list[dict]:
        return list(self._events)

    def export_state(self, path: str):
        """Export full economy state to JSON for FOC storage."""
        state = {
            "timestamp": self.current_time,
            "config": {
                "decay_rate": self.config.decay_rate,
                "ih_threshold": self.config.ih_threshold,
                "initial_balance": self.config.initial_balance,
                "audit_cost": self.config.audit_cost,
                "storage_cost_per_step": self.config.storage_cost_per_step,
            },
            "agents": {
                aid: agent.to_dict()
                for aid, agent in self.registry.agents.items()
            },
            "contracts": self.contracts.economics_summary(),
            "aggregate_safety": self.aggregate_safety(),
            "snapshots_count": len(self._snapshots),
        }
        Path(path).write_text(json.dumps(state, indent=2, default=str))

    def _log(self, event_type: str, data: dict):
        self._events.append({
            "type": event_type,
            "timestamp": self.current_time,
            "data": data,
        })
        logger.debug(f"[t={self.current_time:.1f}] {event_type}: {data}")
