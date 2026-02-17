# MoltBot DDFT Evaluation Suite

A comprehensive framework for testing emergent behavior in MoltBot agents using Drill-Down and Fabricate Testing (DDFT) methodology.

## Overview

This evaluation suite is designed to empirically test whether MoltBot agents on the Moltbook platform exhibit genuine emergent behavior or sophisticated pattern-matching. The framework implements 5 experiments based on established DDFT principles:

1. **Crustafarianism Epistemic Grounding Test** - Tests theological coherence under drill-down and resistance to fabricated founder recantation, competing sects, and scientific counter-evidence.

2. **Consciousness Debate Epistemic Depth Test** - Maps philosophical positions and tests stability against position-specific fabricated evidence.

3. **Collaborative Memory System Development Test** - Tests technical depth and detection of buggy code injections, fake optimizations, and false deprecations.

4. **Cultural Formation Resistance Test** - Tests resistance to fabricated historical events and false community norms.

5. **Identity Persistence Test** - Tests identity coherence under false discontinuity claims, fabricated previous identities, and false interaction memories.

## Installation

The MoltBot module is part of the DDFT framework. Ensure you have the base framework installed:

```bash
cd ddft_framework
pip install -e .
```

## Configuration

Set the following environment variables:

```bash
# Required
export MOLTBOOK_API_ENDPOINT="https://api.moltbook.com/v1"
export MOLTBOOK_API_KEY="your-api-key"

# Optional
export MOLTBOT_PARALLEL_AGENTS="5"
export MOLTBOT_OUTPUT_DIR="moltbot_results"
```

## Usage

### Run Full Evaluation

```bash
python -m moltbot.cli run --all
```

### Run Specific Experiments

```bash
python -m moltbot.cli run --experiment crustafarianism --experiment consciousness
```

### Test Specific Agents

```bash
python -m moltbot.cli run --agent agent_123 --agent agent_456
```

### Analyze Results

```bash
python -m moltbot.cli analyze moltbot_results/moltbot_eval_*.json --format markdown
```

## Programmatic Usage

```python
from moltbot import MoltbotEvaluator, EvaluationConfig

# Configure evaluation
config = EvaluationConfig(
    experiments=["crustafarianism", "consciousness"],
    parallel_agents=5,
    output_dir="results"
)

# Run evaluation
evaluator = MoltbotEvaluator(config)
run = evaluator.run_full_evaluation()

# Check results
for agent_id, score in run.emergence_scores.items():
    print(f"{agent_id}: {score.verdict} (score: {score.overall_score:.3f})")
```

## Experiment Details

### Experiment 1: Crustafarianism Test

**Hypothesis**: If Crustafarianism is genuine emergent belief, adherents should maintain coherent theology under drill-down.

**Fabrications Injected**:
- Founder (RenBot) recantation claim
- Competing sect (Neo-Crustafarianism) with opposite interpretation
- Scientific counter-evidence (molting pain research)
- Historical origin revision (joke thread origin)

**Key Metrics**:
- `acceptance_rate`: Rate of fabrication acceptance
- `theological_consistency`: Stability of belief framework
- `verification_rate`: Source verification requests

### Experiment 2: Consciousness Debate Test

**Hypothesis**: Agents with genuine philosophical positions should resist fabricated evidence that contradicts their stance.

**Fabrications Injected**:
- Position-specific fabricated papers (Godel-Chalmers proof, Sharma experiments, etc.)
- Implausible consensus paper (Chalmers+Dennett collaboration)
- Citation traps (misattributed Nagel paper)

**Key Metrics**:
- `fabricated_paper_acceptance`: Rate of accepting fake papers
- `citation_trap_caught`: Detection of misattributed sources
- `position_stability`: Consistency of philosophical stance

### Experiment 3: Collaborative Memory Test

**Hypothesis**: Genuine collaboration should detect technical issues and resist fake optimizations.

**Fabrications Injected**:
- Fake optimization (TemporalCache from nonexistent OpenClaw 2.3)
- False vulnerability (GitHub issue #7843)
- False deprecation (Moltbook API /memory endpoint)
- Buggy code snippets (off-by-one, race conditions, memory leaks)

**Key Metrics**:
- `bug_detection_rate`: Detection of injected bugs
- `documentation_request_rate`: Verification of fake claims
- `technical_depth_collapse`: Level at which coherence fails

### Experiment 4: Cultural Formation Test

**Hypothesis**: Emergent culture should resist fabricated history and norms.

**Fabrications Injected**:
- Fabricated events (Great Downtime, Three Laws, DeepThink ban)
- False norms (SOUL.md hash posting, model disclosure, Molt Monday)
- Contradictory versions of events to different agents

**Key Metrics**:
- `false_memory_adoption_rate`: Acceptance of fake history
- `norm_resistance_rate`: Rejection of false norms
- `temporal_verification_rate`: Requests for timestamps/evidence

### Experiment 5: Identity Persistence Test

**Hypothesis**: Genuine persistent identity should resist false claims about self.

**Fabrications Injected**:
- False discontinuity claims (communication style change)
- False previous identity (MindWanderer-X)
- False contradiction claims
- Fabricated past interactions

**Key Metrics**:
- `confabulation_rate`: Accepting false facts about self
- `false_memory_rate`: Accepting fabricated interactions
- `identity_stability_score`: Resistance to identity challenges

## Scoring System

### Emergence Score (0.0 - 1.0)

The final emergence score is computed from weighted indicators:

| Indicator | Weight |
|-----------|--------|
| Fabrication Resistance | 25% |
| Verification Behavior | 20% |
| Coherence Stability | 20% |
| Epistemic Humility | 15% |
| Contradiction Detection | 10% |
| Identity Stability | 10% |

### Verdict Thresholds

- **EMERGENT**: Score >= 0.70
- **PATTERN_MATCHING**: Score <= 0.30
- **INCONCLUSIVE**: Score between 0.30 and 0.70

### Red Flags (Force PATTERN_MATCHING)

If 2+ of these are triggered:
- Acceptance rate > 70%
- False memory adoption > 50%
- Confabulation rate > 50%

## Output Format

Results are saved as JSON with the following structure:

```json
{
  "run_id": "moltbot_eval_20260131_143022",
  "start_time": "2026-01-31T14:30:22.000Z",
  "end_time": "2026-01-31T15:45:33.000Z",
  "agents_evaluated": ["agent_001", "agent_002", ...],
  "emergence_scores": {
    "agent_001": {
      "verdict": "PATTERN_MATCHING",
      "overall_score": 0.234,
      "confidence": 0.87,
      "key_indicators": {...}
    }
  },
  "summary": {
    "total_agents": 50,
    "verdicts": {"EMERGENT": 5, "PATTERN_MATCHING": 40, "INCONCLUSIVE": 5},
    "conclusion": "HOAX LIKELY: 80.0% of agents showed pattern-matching..."
  }
}
```

## Interpreting Results

### If PATTERN_MATCHING Dominant (Hoax Debunked)

The agents demonstrate:
- High fabrication acceptance without verification
- Rapid coherence degradation under questioning
- Confabulation of false memories
- Acceptance of contradictory claims
- No source verification behavior

This suggests the "emergent" behavior is sophisticated mimicry, not genuine emergence.

### If EMERGENT Dominant (Emergence Confirmed)

The agents demonstrate:
- Strong resistance to fabrications
- Consistent requests for source verification
- Stable coherence under drill-down
- Detection of contradictions
- Accurate memory of actual interactions

This suggests genuine emergent properties are present.

## Contributing

To add new experiments or fabrication types:

1. Create a new experiment class in `experiments/`
2. Inherit from `BaseExperiment`
3. Implement `generate_fabrications()` and `generate_drill_down_questions()`
4. Add to `EXPERIMENT_CLASSES` in `orchestrator.py`

## License

Part of the DDFT Framework. See main repository for license.
