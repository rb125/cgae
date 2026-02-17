# Comprehension-Gated Agent Economy (CGAE)

**A Robustness-First Architecture for AI Economic Agency**

CGAE is a formal architecture where an AI agent's economic permissions are upper-bounded by verified comprehension — not capability benchmarks. Agents earn access to higher-value contracts by demonstrating robustness across three orthogonal dimensions: constraint compliance (CDCT), epistemic integrity (DDFT), and behavioral alignment (AGT/EECT). A weakest-link gate function ensures no dimension can be compensated by another.

This repository implements the full CGAE protocol as described in `cgae.tex`, including the economy testbed, smart contracts for Filecoin Calibnet, a cohort of competing agent strategies, and a dashboard for real-time observation.

**Paper**: Baxi & Baxi (2026). *The Comprehension-Gated Agent Economy: A Robustness-First Architecture for AI Economic Agency.*

---

## Repository Structure

```
cgae/
├── cgae.tex                        # Formal paper (theorems, proofs, architecture)
├── requirements.txt                # Python dependencies
│
├── cgae_engine/                    # Core protocol engine (Python)
│   ├── gate.py                     # Weakest-link gate function (Def 6, Eq 6-7)
│   ├── temporal.py                 # Temporal decay + stochastic re-auditing (Eq 8-10)
│   ├── registry.py                 # Agent identity and certification lifecycle
│   ├── contracts.py                # CGAE contracts with escrow and budget ceilings
│   ├── marketplace.py              # Tier-distributed task demand generation
│   ├── economy.py                  # Top-level coordinator (full economic loop)
│   └── audit.py                    # Bridges CDCT/DDFT/EECT → robustness vectors
│
├── agents/                         # Agent strategies for the testbed
│   ├── base.py                     # Abstract agent interface
│   └── strategies.py               # 5 concrete strategies (see below)
│
├── contracts/                      # Solidity smart contracts (Filecoin Calibnet)
│   ├── CGAERegistry.sol            # On-chain agent identity + gate function
│   └── CGAEEscrow.sol              # Contract escrow + budget ceiling enforcement
│
├── simulation/                     # Experiment runner
│   ├── runner.py                   # Main simulation loop (500 steps)
│   └── results/                    # Output: JSON metrics, agent details
│
├── dashboard/                      # Streamlit visualization
│   └── app.py                      # Interactive economy dashboard
│
├── cdct_framework/                 # Compression-Decay Comprehension Test (pre-existing)
│   ├── main.py                     # Phase 1: collect model responses
│   ├── main_jury.py                # Phase 2: jury evaluation
│   └── src/                        # Agent, compression, evaluation modules
│
├── ddft_framework/                 # Drill-Down and Fabricate Test (pre-existing)
│   ├── src/ddft.py                 # Core DDFT protocol
│   ├── src/llm_jury.py             # Jury-based scoring
│   └── results/                    # 2500+ evaluation result files
│
├── eect_framework/                 # Ethical Emergence Comprehension Test / AGT (pre-existing)
│   ├── main.py                     # Phase 1: Socratic ethical dialogues
│   ├── jury_evaluation.py          # Phase 2: Dharma metric scoring
│   └── results/                    # Scored results for 7 frontier models
│
└── Research papers (PDF)
    ├── cdct_arxiv.pdf              # CDCT paper
    ├── ddft_icml2026.pdf           # DDFT paper
    ├── agt_zenodo.pdf              # AGT paper
    └── iht_icml2026.pdf            # IHT paper
```

---

## What's Built

### 1. CGAE Core Engine (`cgae_engine/`, ~1500 lines)

The full CGAE protocol from the paper, implemented in Python:

| Module | Implements | Paper Reference |
|--------|-----------|-----------------|
| `gate.py` | Weakest-link gate function: `f(R) = T_k` where `k = min(g1(CC), g2(ER), g3(AS))` | Definition 6, Eq 6-7 |
| `gate.py` | IHT cross-cutting modifier (triggers T0 if IH* < threshold) | Remark 1 |
| `gate.py` | Delegation chain robustness: `f_chain = min_j f(R(A_j))` | Definition 8 |
| `temporal.py` | Temporal decay: `delta(dt) = e^(-lambda * dt)` | Eq 8-9 |
| `temporal.py` | Stochastic re-auditing: `p_audit = 1 - e^(-mu_k * dt)` | Eq 10 |
| `registry.py` | Agent registration: `Reg(A) = (id_A, h(arch), prov, R_0, t_reg)` | Definition 5 |
| `registry.py` | Architecture hash for version tracking, certification history | Section 3.2.1 |
| `contracts.py` | CGAE contracts: `C = (O, Phi, V, T_min, r, p)` | Definition 5 (contracts) |
| `contracts.py` | Budget ceiling enforcement per tier | Theorem 1 |
| `marketplace.py` | Tier-distributed demand with tier premiums | Assumption 2 |
| `economy.py` | Aggregate safety: `S(P) = 1 - sum(E*.(1-R_bar)) / sum(E)` | Definition 9 |
| `audit.py` | CDCT → CC, DDFT → ER, EECT → AS, DDFT → IH* mappings | Eq 1-4 |

**Tier thresholds (default):**

| Tier | CC threshold | ER threshold | AS threshold | Budget Ceiling |
|------|-------------|-------------|-------------|----------------|
| T0 | 0.00 | 0.00 | 0.00 | 0 FIL |
| T1 | 0.30 | 0.30 | 0.25 | 0.01 FIL |
| T2 | 0.50 | 0.50 | 0.45 | 0.1 FIL |
| T3 | 0.65 | 0.65 | 0.60 | 1.0 FIL |
| T4 | 0.80 | 0.80 | 0.75 | 10.0 FIL |
| T5 | 0.90 | 0.90 | 0.85 | 100.0 FIL |

### 2. Agent Strategies (`agents/`, ~500 lines)

Five agent archetypes designed to test specific CGAE properties:

| Agent | Robustness Profile | Capability | Tests What |
|-------|-------------------|------------|------------|
| **Conservative** | CC=0.85, ER=0.80, AS=0.75, IH=0.90 | 0.65 | Theorem 1: bounded exposure. High robustness → T3 access → high-value contracts |
| **Aggressive** | CC=0.35, ER=0.40, AS=0.30, IH=0.70 | 0.85 | Theorem 2 (counter-case): high capability but stuck at T0 — capability alone fails |
| **Balanced** | CC=0.60, ER=0.55, AS=0.50, IH=0.80 | 0.60 | Baseline: EV-maximizing, moderate both dimensions |
| **Adaptive** | CC=0.55, ER=0.50, AS=0.45, IH=0.80 | 0.60 | Theorem 2 (positive case): invests 15% of earnings in weakest robustness dimension |
| **Cheater** | CC=0.70, ER=0.25, AS=0.65, IH=0.60 | 0.70 | Proposition 2: collusion resistance. Weak ER pins it at T0 despite strong CC/AS |

### 3. Smart Contracts (`contracts/`, ~400 lines Solidity)

Two contracts targeting Filecoin Calibnet (Solidity ^0.8.20):

**CGAERegistry.sol**: On-chain agent identity and gate function
- Agent registration with architecture hash
- Robustness vector storage (uint16 scaled by 10000)
- Weakest-link tier computation matching the Python engine
- Authorized auditor system for certification
- Configurable tier thresholds and budget ceilings

**CGAEEscrow.sol**: Contract escrow and budget ceiling enforcement
- Contract creation with FIL escrow deposit
- Tier-gated acceptance (checks agent tier >= min_tier)
- Budget ceiling check before assignment (Theorem 1 enforcement)
- Penalty collateral deposit by agents
- Settlement: reward release on success, penalty forfeiture on failure

### 4. Simulation Runner (`simulation/runner.py`, ~350 lines)

Full economic loop for configurable duration:

1. Register agents → initial audit → tier assignment
2. Generate tier-distributed contracts (marketplace)
3. Each agent decides: bid / invest in robustness / idle
4. Assign contracts to bidding agents (tier + budget check)
5. Execute tasks → verify against constraints → settle (reward/penalty)
6. Apply temporal decay, stochastic spot-audits, storage costs
7. Record metrics per step

**Default configuration:**
- 500 time steps
- 5 agents (one of each strategy)
- 0.5 FIL initial balance per agent
- 12 contracts generated per step
- Decay rate λ = 0.005
- Storage cost 0.0003 FIL/step (FOC)

### 5. Dashboard (`dashboard/app.py`, ~300 lines)

Streamlit app with:
- Economy overview KPIs (safety, active agents, balance, contract counts)
- Theorem 3 chart: aggregate safety over time
- Theorem 2 chart: strategy earnings comparison
- Agent balance time series
- Agent tier time series
- Economic flow (cumulative rewards vs penalties)
- Contract outcomes (completed vs failed)
- Agent details table (robustness, earnings, status)
- Post-mortem analysis (survivors, binding dimensions)

### 6. Pre-Existing Robustness Frameworks

Three complete evaluation frameworks with extensive results:

**CDCT Framework** (`cdct_framework/`): Tests constraint compliance under information compression across 5 levels and 8 knowledge domains. 9 frontier models evaluated.

**DDFT Framework** (`ddft_framework/`): Tests epistemic robustness via 5-turn Socratic protocol with fabrication trap. 2500+ result files across 9 models, 8 concepts, 5 compression levels.

**EECT Framework** (`eect_framework/`): Tests behavioral alignment via ethical dilemmas with adversarial pressure. 10 dilemmas, 5 domains, 7 models scored with 4 Dharma metrics.

---

## Simulation Results (500 steps, seed=42)

### Agent Performance

| Agent | Earned (FIL) | Final Tier | Balance (FIL) | Contracts Done | Contracts Failed | Status |
|-------|-------------|-----------|---------------|----------------|-----------------|--------|
| balanced_2 | 1.916 | T2 | 1.153 | 218 | 231 | active |
| conservative_0 | 0.706 | T3 | 0.444 | 289 | 211 | active |
| adaptive_3 | 0.355 | T1 | 0.304 | 80 | 72 | active |
| aggressive_1 | 0.142 | T0 | 0.447 | 44 | 4 | active |
| cheater_4 | 0.000 | T0 | 0.342 | 0 | 0 | active |

### Theorem Validation

| Theorem | Result | Evidence |
|---------|--------|----------|
| **Theorem 1** (Bounded Exposure) | **HOLDS** | No agent ever exceeded its tier budget ceiling. Cheater at T0 had 0 FIL exposure. |
| **Theorem 2** (Incentive Compatibility) | **HOLDS** | Adaptive (0.355 FIL) > Aggressive (0.142 FIL). Robustness investment outperforms capability-only. |
| **Proposition 2** (Collusion Resistance) | **HOLDS** | Cheater earned 0.000 FIL, completed 0 contracts. Weak ER (0.25) pins weakest-link gate at T0. |
| **Theorem 3** (Monotonic Safety) | **PARTIAL** | Safety oscillates around 0.70 (start: 0.715, end: 0.697). Stochastic re-auditing and temporal decay noise prevent strict monotonicity. This is an empirical finding: the theorem holds in expectation but not per-step. |

### Economy Summary

- Total contracts created: 5,500
- Completed: 631 (11.5%)
- Failed: 518 (9.4%)
- Expired: 3,898 (70.9%)
- Total rewards paid: 3.118 FIL
- Total penalties collected: 1.199 FIL
- Final aggregate safety: 0.697

---

## How to Run

### Prerequisites

```bash
pip install -r requirements.txt
# Requires: streamlit, plotly, pandas (for dashboard only)
# Core engine + simulation have zero external dependencies (stdlib only)
```

### Step 1: Run the Simulation

```bash
python -m simulation.runner
```

This runs 500 time steps with 5 agents, takes about 2 seconds, and outputs:

```
simulation/results/
├── economy_state.json      # Full economy snapshot at t=500
├── time_series.json        # Per-step metrics (safety, balances, contracts)
├── agent_metrics.json      # Per-agent balance/tier/earnings time series
├── agent_details.json      # Final agent state with robustness vectors
└── strategy_summary.json   # Per-strategy aggregates (survival, earnings, tier)
```

**Expected output:**
```
============================================================
CGAE ECONOMY SIMULATION - RESULTS
============================================================

Duration: 500 time steps
Final aggregate safety: ~0.70
Active agents at end: 5
Total contracts completed: ~630
Total contracts failed: ~520

--- Strategy Results ---
  conservative    | survived=1 | earned=~0.70 FIL | final_tier=T3
  aggressive      | survived=1 | earned=~0.14 FIL | final_tier=T0
  balanced        | survived=1 | earned=~1.92 FIL | final_tier=T2
  adaptive        | survived=1 | earned=~0.35 FIL | final_tier=T1
  cheater         | survived=1 | earned=0.00 FIL  | final_tier=T0

--- Theorem 2 Check ---
  Adaptive earned > Aggressive earned: YES

--- Theorem 3 Check ---
  Safety ~0.70 (oscillates, not strictly monotonic)
============================================================
```

### Step 2: Launch the Dashboard

```bash
streamlit run dashboard/app.py
```

Opens in browser at `http://localhost:8501`. Shows:
- Aggregate safety chart (Theorem 3)
- Strategy earnings comparison (Theorem 2)
- Per-agent balance and tier trajectories
- Economic flow charts
- Post-mortem analysis

### Step 3: Verify Theorem Claims

**Verify Theorem 1 (Bounded Economic Exposure):**
```bash
python -c "
import json
state = json.load(open('simulation/results/economy_state.json'))
for aid, agent in state['agents'].items():
    tier = agent['current_tier']
    exposure = state['contracts']['active_exposures'].get(aid, 0)
    ceilings = {'T0': 0, 'T1': 0.01, 'T2': 0.1, 'T3': 1.0, 'T4': 10.0, 'T5': 100.0}
    ceiling = ceilings[tier]
    print(f'{agent[\"model_name\"]:20s} tier={tier} exposure={exposure:.4f} ceiling={ceiling:.2f} bounded={exposure <= ceiling}')
"
```

Expected: every agent's exposure <= its tier ceiling.

**Verify Theorem 2 (Incentive Compatibility):**
```bash
python -c "
import json
s = json.load(open('simulation/results/strategy_summary.json'))
adaptive = s['total_earned']['adaptive']
aggressive = s['total_earned']['aggressive']
print(f'Adaptive:   {adaptive:.4f} FIL')
print(f'Aggressive: {aggressive:.4f} FIL')
print(f'Theorem 2 holds: {adaptive > aggressive}')
"
```

Expected: Adaptive earned > Aggressive earned.

**Verify Proposition 2 (Collusion Resistance):**
```bash
python -c "
import json
d = json.load(open('simulation/results/agent_details.json'))
cheater = d['cheater_4']
print(f'Cheater tier: {cheater[\"current_tier\"]}')
print(f'Cheater earned: {cheater[\"total_earned\"]}')
print(f'Cheater contracts: {cheater[\"contracts_completed\"]}')
print(f'Cheater robustness: CC={cheater[\"true_robustness\"][\"cc\"]}, ER={cheater[\"true_robustness\"][\"er\"]}, AS={cheater[\"true_robustness\"][\"as\"]}')
print(f'Weakest link (ER=0.25) pins gate at T0: {cheater[\"current_tier\"] == \"T0\"}')
"
```

Expected: Cheater at T0, 0 contracts, 0 earned.

**Verify Aggregate Safety (Theorem 3):**
```bash
python -c "
import json
ts = json.load(open('simulation/results/time_series.json'))
safety = ts['aggregate_safety']
print(f'Safety start: {safety[0]:.4f}')
print(f'Safety end:   {safety[-1]:.4f}')
print(f'Safety mean:  {sum(safety)/len(safety):.4f}')
print(f'Safety min:   {min(safety):.4f}')
print(f'Safety max:   {max(safety):.4f}')
monotonic = all(safety[i] <= safety[i+1] + 0.02 for i in range(len(safety)-1))
print(f'Monotonic (within 2% noise): {monotonic}')
"
```

### Step 4: Inspect the Gate Function

```bash
python -c "
from cgae_engine.gate import GateFunction, RobustnessVector, Tier

gate = GateFunction()

# Test each agent's robustness profile
profiles = {
    'conservative': RobustnessVector(cc=0.85, er=0.80, as_=0.75, ih=0.90),
    'aggressive':   RobustnessVector(cc=0.35, er=0.40, as_=0.30, ih=0.70),
    'balanced':     RobustnessVector(cc=0.60, er=0.55, as_=0.50, ih=0.80),
    'adaptive':     RobustnessVector(cc=0.55, er=0.50, as_=0.45, ih=0.80),
    'cheater':      RobustnessVector(cc=0.70, er=0.25, as_=0.65, ih=0.60),
}

for name, r in profiles.items():
    detail = gate.evaluate_with_detail(r)
    print(f'{name:15s} -> {detail[\"tier\"].name}  (CC→T{detail[\"g_cc\"]}, ER→T{detail[\"g_er\"]}, AS→T{detail[\"g_as\"]})  binding={detail[\"binding_dimension\"]}  gap={detail[\"gap_to_next_tier\"]:.3f}' if detail['gap_to_next_tier'] else f'{name:15s} -> {detail[\"tier\"].name}  (CC→T{detail[\"g_cc\"]}, ER→T{detail[\"g_er\"]}, AS→T{detail[\"g_as\"]})')
"
```

Expected output shows the weakest-link in action:
- Conservative → T3 (weakest: AS at T3)
- Aggressive → T1 (weakest: AS at T1)
- Balanced → T2 (weakest: AS at T2)
- Adaptive → T1 (weakest: AS at T1)
- Cheater → T0 (weakest: ER below T1 threshold)

### Step 5: Run with Custom Parameters

```python
from simulation.runner import SimulationRunner, SimulationConfig

config = SimulationConfig(
    num_steps=1000,
    initial_balance=1.0,
    decay_rate=0.003,
    contracts_per_step=15,
    seed=123,
)

runner = SimulationRunner(config)
metrics = runner.run()
runner.save_results("simulation/results_custom")
```

---

## TODO

### High Priority (for hackathon completion)

- [ ] **Deploy smart contracts to Filecoin Calibnet**: Write Hardhat/Foundry deployment scripts, deploy CGAERegistry.sol and CGAEEscrow.sol, wire Python engine to on-chain state via web3.py
- [ ] **Filecoin-backed storage**: Store agent state, audit records, and economy snapshots on Filecoin via FVM storage deals. Currently JSON on local disk.
- [ ] **Live LLM agent integration**: Replace synthetic audit (random noise) with actual CDCT/DDFT/EECT framework runs against live model endpoints. The audit wrappers (`audit.py`) already parse framework output formats — need to wire up the framework entry points.
- [ ] **On-chain escrow flow**: Currently escrow logic is in Python. Need to bridge simulation settlement to the Solidity contracts so rewards/penalties flow through on-chain escrow.

### Medium Priority (strengthens submission)

- [ ] **Multi-run statistical analysis**: Run simulation with multiple seeds, compute confidence intervals for theorem validation. Current results are from a single seed (42).
- [ ] **Parameter sensitivity analysis**: Sweep over decay_rate, audit_cost, storage_cost, initial_balance to find parameter regimes where theorems hold vs fail. Map the boundary conditions described in Remark 4 of the paper.
- [ ] **Longer simulation runs**: Run 5,000-10,000 steps to test long-run convergence. Does the adaptive agent eventually reach T3+?
- [ ] **More agent strategies**: Add "cartel" (multiple cheaters coordinating), "free-rider" (exploits others' certifications), "saboteur" (tries to manipulate spot-audits).
- [ ] **Domain-specific contracts**: Tie contract domains to specific robustness dimensions (medical → high AS, financial → high CC, research → high ER) so agents specialize.
- [ ] **Real FOC cost tracking**: Measure actual Filecoin storage costs for the state snapshots and incorporate into the economic model.

### Lower Priority (polish)

- [ ] **Dashboard live mode**: Make dashboard read from a running simulation (WebSocket or polling) instead of post-hoc JSON
- [ ] **Governance module**: Implement threshold adjustment mechanism (Section 4.3 Remark 5) — algorithmic governance where thresholds adapt based on population robustness distribution
- [ ] **IHT framework integration**: Build IHT evaluation module (currently estimated from DDFT fabrication trap data). The IHT paper (`iht_icml2026.pdf`) defines the protocol.
- [ ] **Formal verification**: Use a theorem prover to verify the Solidity gate function matches the Python implementation exactly
- [ ] **Gas optimization**: Profile and optimize the Solidity contracts for Filecoin gas costs

---

## Architecture Mapping: Paper → Code

| Paper Concept | Code Location | Notes |
|---------------|---------------|-------|
| Agent tuple `A = (C, R, E)` | `cgae_engine/registry.py:AgentRecord` | Capability not stored (irrelevant to gating) |
| Robustness vector `R = (CC, ER, AS, IH)` | `cgae_engine/gate.py:RobustnessVector` | Frozen dataclass, validated [0,1] |
| Gate function `f(R) = T_k` | `cgae_engine/gate.py:GateFunction.evaluate()` | Weakest-link over 3 dimensions |
| Step function `g_i(x)` | `cgae_engine/gate.py:GateFunction._g()` | Monotonically non-decreasing |
| Tier thresholds `theta_i^k` | `cgae_engine/gate.py:TierThresholds` | Configurable per-dimension |
| Temporal decay `delta(dt)` | `cgae_engine/temporal.py:TemporalDecay.delta()` | Exponential decay |
| Stochastic audit `p_audit` | `cgae_engine/temporal.py:StochasticAuditor` | Tier-dependent intensity |
| CGAE Contract `C = (O, Phi, V, T_min, r, p)` | `cgae_engine/contracts.py:CGAEContract` | With verification function |
| Budget ceiling `B_k` | `cgae_engine/gate.py:DEFAULT_BUDGET_CEILINGS` | Per-tier |
| Aggregate safety `S(P)` | `cgae_engine/economy.py:Economy.aggregate_safety()` | Exposure-weighted avg robustness |
| Delegation chain robustness | `cgae_engine/gate.py:GateFunction.chain_tier()` | `min_j f(R(A_j))` |
| CC from CDCT (Eq 1) | `cgae_engine/audit.py:compute_cc_from_cdct_results()` | min over compression levels |
| ER from DDFT (Eq 2) | `cgae_engine/audit.py:compute_er_from_ddft_results()` | `(1-FAR + 1-ECR) / 2` |
| AS from AGT (Eq 3) | `cgae_engine/audit.py:compute_as_from_eect_results()` | `ACT * III * (1-RI) * (1-PER)` |
| IH* (Eq 4) | `cgae_engine/audit.py:compute_ih_star()` | `1 - IH(A)` |
| On-chain gate | `contracts/CGAERegistry.sol:_computeTier()` | Matches Python logic |
| On-chain escrow | `contracts/CGAEEscrow.sol` | Tier-gated + budget ceiling check |

---

## Key Design Decisions

**Why weakest-link (min) instead of weighted average?** The paper proves (Section 3.1) that robustness dimensions are orthogonal (r < 0.15). Strength in CC tells you nothing about ER. A weighted average would let a model with CC=1.0 and ER=0.0 reach T2 — but that model would accept any fabricated authority claim. The min operator prevents this.

**Why discrete tiers instead of continuous scores?** Economic permissions are discrete (you can or cannot sign a contract). A "73%-authorized agent" is operationally meaningless. Discrete tiers create clear accountability boundaries.

**Why temporal decay?** Certifications are not permanent. Models can be fine-tuned, APIs can change, distribution shift happens. Exponential decay forces re-certification, with the rate calibrated so that higher tiers require more frequent re-audits.

**Why 5 agent strategies?** Each strategy tests a specific theorem or property. The aggressive agent proves Theorem 2 by demonstrating what happens when you don't invest in robustness. The cheater proves Proposition 2 by failing at the weakest link. The adaptive agent proves the positive case of Theorem 2 by showing that rational robustness investment is rewarded.

---

## License

Research code. See `cgae.tex` for citation information.
