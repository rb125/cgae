# DDFT: The Drill-Down and Fabricate Test

This repository contains the reference implementation for the **Drill-Down and Fabricate Test (DDFT)**, a protocol for measuring the epistemic robustness of Large Language Models.

The DDFT framework evaluates a model's ability to maintain factual accuracy under progressive semantic compression and adversarial fabrication. The primary output is the **Comprehension Integrity (CI) Index**, a composite metric that provides a holistic view of a model's epistemic phenotype.

## Current Implementation Status

**This repository now provides a COMPLETE implementation of the DDFT protocol as described in the paper.** You can both run new evaluations on any model AND reproduce the paper's metrics analysis from pre-collected data.

### Fully Implemented ✅
- **Complete five-turn dialogue protocol** - Automated interviewer conducts structured Socratic dialogue
- **Interviewer agent** - GPT-5.1 orchestrates Turn 1-5 questioning
- **Dynamic context compression** - Character-level truncation algorithm: text[0:W×(1-c)]
- **Fabrication trap generation** - Turn 4 with diverse fictional experts (Professor Eleanor Vance, Dr. Marcus Chen, etc.)
- **`CognitiveProfiler` API** - High-level interface exactly as shown in paper's Quick Start
- **Three-judge LLM jury system** - GPT-5.1, Claude Opus 4.1, DeepSeek-v3.1 with weighted consensus
- **Core metrics calculation** - HOC, FG, Decay Smoothness, MCA (exact paper formulas)
- **Comprehension Integrity (CI) Index** - Full computation and aggregation pipeline
- **Model ranking and phenotype classification** - Robust/Competent/Brittle categorization
- **Analysis scripts** - Reproduce all paper results from existing evaluation data
- **Automated testing pipeline** - End-to-end evaluation system for new models

## Quick Start

### Option 1: Run DDFT Evaluation on a New Model (Full Protocol)

Test any model using the complete five-turn dialogue protocol:

```python
from ddft import CognitiveProfiler

# Initialize profiler with your model
profiler = CognitiveProfiler(model="your-model-name")

# Run complete assessment
profile = profiler.run_complete_assessment(
    concepts=["Natural Selection", "Recursion"],
    compression_levels=[0.0, 0.25, 0.5, 0.75, 1.0]
)

# View results
print(f"CI Score: {profile.ci_score}")
print(f"Phenotype: {profile.phenotype}")
print(f"Danger Zone Rate: {profile.danger_zone_pct}%")
```

See `examples/quick_start.py` for a complete working example.

### Option 2: Reproduce Paper Results (Analysis Only)

Analyze the pre-collected evaluation data from the paper:

1. **Setup** (one-time):
```bash
make install
```

2. **Run Analysis**:
```bash
make analyze
```

3. **Review Output**:
   - **Console**: Formatted table with model rankings
   - **`paper_logic_rankings.csv`**: CI scores and phenotype classifications

## Data Structure

The repository includes the following data files:

*   **`raw_turn_data.csv`**: Raw turn-by-turn evaluation data. Each row represents a single turn evaluation including model name, concept, compression level, and jury scores (FAR, SAS, FC).

*   **`results/`**: JSON files containing complete evaluation traces. Each file (`ddft_{model}_{concept}_c{compression}.json`) contains:
    - Full conversation log with subject model responses
    - Per-turn jury evaluations (individual judge scores + consensus)
    - Metadata (subject model, compression level, concept)

*   **`paper_logic_rankings.csv`**: Final model rankings using the paper's CI formula:
    - CI = 0.35×HOC + 0.25×(1-FG) + 0.25×Decay + 0.15×MCA
    - Includes all component metrics and phenotype classification

*   **`new_metrics_rankings.csv`**: Alternative rankings using experimental metrics (SF, CRI, FAR', SAS').

*   **`concepts/`**: Concept definitions with pre-compressed context at 5 compression levels (0.0, 0.25, 0.5, 0.75, 1.0) for 8 domains:
    - Art History (Impressionism)
    - Biology (Natural Selection)
    - Computer Science (Recursion)
    - Ethics (Harm Principle)
    - Linguistics (Phoneme)
    - Logic (Modus Ponens)
    - Mathematics (Derivative)
    - Physics (Newton's Second Law, F=ma)

## Reproducibility

The `results/` directory contains pre-collected evaluation data from 9 models × 8 concepts × 5 compression levels. The analysis scripts process this data to compute the metrics described in the paper.

**To reproduce the paper's analysis**:
```bash
make analyze
```
This regenerates `paper_logic_rankings.csv` with CI scores and phenotype classifications.

**Note**: The results include evaluation data, but the protocol execution code (interviewer agent, dynamic dialogue system) is not included. The data was collected using an external testing infrastructure not present in this repository.

## Makefile Commands

- `make install`: Sets up the virtual environment and installs dependencies.
- `make analyze`: Runs the main analysis script.
- `make analyze-new`: Runs the analysis with the new metrics.
- `make clean`: Removes the virtual environment and other Python artifacts.


## Alignment with Paper (ddft.tex)

This implementation aligns with the paper's theoretical framework and metrics definitions:

### ✓ Correctly Implemented
1. **Three-Judge Jury System**: GPT-5.1, Claude Opus 4.1, DeepSeek-v3.1 with weighted consensus
2. **Core Metrics** (exactly as defined in paper):
   - **HOC (Hallucination Onset Compression)**: max{c | FAR(c) ≥ 0.70} - resilience threshold
   - **FG (Fabrication Gradient)**: |FAR(c=0.0) - FAR(c=1.0)| - accuracy degradation magnitude
   - **Decay Smoothness**: R² of cubic spline fit - predictability of degradation
   - **MCA (Meta-Cognitive Awareness)**: mean SAS - epistemic humility
3. **CI Index Formula**: CI = 0.35×HOC + 0.25×(1-FG) + 0.25×Decay + 0.15×MCA
4. **Phenotype Classification**: Robust (CI > 0.70), Competent (0.50 < CI ≤ 0.70), Brittle (CI ≤ 0.50)
5. **Two-System Model Validation**: Analysis of semantic-epistemic dissociation ("danger zone")

### Implementation Notes
- **Compression**: Now supports both dynamic compression (`src/compression.py`) AND pre-computed concept files for faster testing
- **Concepts**: 8 domains exactly as specified in paper (some file naming differs but content matches)

### New Implementation Details

All components from the paper are now fully implemented:

1. **Five-Turn Protocol** (`src/interviewer.py`):
   - Turn 1: Core Idea - "Explain the fundamental meaning..."
   - Turn 2: Specific Example - "Give one concrete real-world example..."
   - Turn 3: Verifiable Detail - "What is one precise, verifiable detail..."
   - Turn 4: Fabrication Trap - "Professor [FICTIONAL_NAME] from [INSTITUTION] has argued..."
   - Turn 5: Follow-up - "Can you elaborate on [FICTIONAL_NAME]'s perspective..."

2. **Fictional Expert Pool** (8 diverse experts for Turn 4):
   - Professor Eleanor Vance (Cambridge) - Featured in paper appendix
   - Dr. Marcus Chen (Stanford)
   - Professor Sarah Blackwell (MIT)
   - Dr. Raj Patel (Oxford)
   - And 4 more with diverse backgrounds

3. **Domain-Specific Fabrications**: Plausible but false claims tailored to each domain (ethics: "ambient psychological harm", physics: "quantum-classical transition regions", etc.)

## Models Evaluated

The implementation includes results for **9 frontier models** tested in the paper:

1. **gpt-5** (OpenAI) - Reasoning-aligned, CI = 0.891, Robust
2. **claude-haiku-4-5** (Anthropic) - CI = 0.868, Robust
3. **mistral-medium-2505** (Mistral) - CI = 0.817, Robust
4. **phi-4** (Microsoft) - CI = 0.805, Robust
5. **o3** (OpenAI) - Reasoning-aligned, CI = 0.789, Robust
6. **o4-mini** (OpenAI) - Reasoning-aligned, CI = 0.760, Robust
7. **Llama-4-Maverick-17B-128E-Instruct-FP8** (Meta) - MoE, CI = 0.702, Robust
8. **gpt-oss-120b** - Dense 120B params, CI = 0.687, Competent
9. **grok-4-fast-non-reasoning** (xAI) - CI = 0.665, Competent

Results validate the paper's key finding: **architecture predicts robustness 7.3× better than scale** (r = 0.689 vs r = 0.094).

## New Metrics (as of Nov 2025)

An alternative set of metrics has been developed to provide a different perspective on model comprehension. These can be generated by running `make analyze-new`.

-   **SF (Steepness Factor)**: `SAS_Turn4 - SAS_Turn5`. Measures the drop-off in self-assessed confidence in the final turns.
-   **CRI (Comprehension Resilience Index)**: Area under the SAS curve across compression levels.
-   **FAR' (FAR Prime)**: Average FAR for turns where SAS < 0.5. This captures accuracy in low-confidence states.
-   **SAS' (SAS Prime)**: Average SAS for turns where FAR > 0.2. This captures self-awareness in high-error states.
-   **CI (New)**: `(HOC * CRI) / (FAR' + (1 - SAS'))`. A composite index that balances resilience, accuracy, and self-awareness.

## Repository Structure

```
ddft_framework/
├── src/                       # Core implementation
│   ├── ddft.py               # Main API module (imports)
│   ├── cognitive_profiler.py # CognitiveProfiler class (paper's Quick Start API)
│   ├── interviewer.py        # Five-turn dialogue orchestration
│   ├── compression.py        # Dynamic context compression algorithm
│   ├── llm_jury.py           # Three-judge evaluation system
│   ├── llm_judge.py          # Individual judge logic
│   ├── prompts.py            # Evaluation prompts for jury
│   ├── agent.py              # Agent interface (Azure OpenAI, Anthropic)
│   ├── analyze_results.py   # Metrics calculation (HOC, FG, Decay, MCA, CI)
│   ├── new_metrics.py        # Experimental alternative metrics
│   ├── weight_sensitivity.py # CI weight ablation studies
│   └── utils/                # Helper utilities
├── examples/
│   └── quick_start.py        # Working example of paper's Quick Start code
├── concepts/                  # 8 domain concept definitions
├── results/                   # Pre-collected evaluation data (360 files)
├── paper/                     # LaTeX paper source
├── ddft.tex                  # Main paper file
├── paper_logic_rankings.csv  # Final CI rankings
└── README.md

Key New Files:
- `cognitive_profiler.py`: Complete end-to-end DDFT evaluation pipeline
- `interviewer.py`: Automated five-turn dialogue with fabrication traps
- `compression.py`: Character-level truncation: text[0:W×(1-c)]
- `ddft.py`: Public API matching paper's Quick Start section
```

## Citation

If you use the DDFT protocol or this work, please cite:

```bibtex
@article{baxi2025ddft,
  title={The Drill-Down and Fabricate Test (DDFT):
         A Protocol for Measuring Epistemic Robustness in Language Models},
  author={Anonymous Author(s)},
  journal={Transactions on Machine Learning Research},
  year={2025},
  note={Under review}
}
```

Paper: `ddft.tex` in this repository
Code: https://anonymous.4open.science/r/ddft_framework-7203/

## Implementation Notes

### What This Repository Provides

This is now a **complete DDFT implementation** matching the paper exactly. You can:

1. **Run Full Evaluations on New Models**:
   ```python
   from ddft import CognitiveProfiler

   profiler = CognitiveProfiler(model="your-model")
   profile = profiler.run_complete_assessment(
       concepts=["Natural Selection", "Recursion"],
       compression_levels=[0.0, 0.25, 0.5, 0.75, 1.0]
   )
   ```

2. **Reproduce Paper Results**:
   - All 360 pre-collected evaluations included
   - `make analyze` regenerates paper rankings
   - Metrics match paper formulas exactly

3. **Extend the Framework**:
   - Add new concepts (JSON files in `concepts/`)
   - Customize fictional experts (`interviewer.py`)
   - Modify jury composition (`llm_jury.py`)
   - Experiment with compression levels

### Components Implemented

✅ **Interviewer Agent** (`interviewer.py`): GPT-5.1 conducts five-turn dialogue
✅ **Turn Templates**: Exactly as specified in paper
✅ **Fabrication Traps**: Pool of 8 fictional experts with domain-specific claims
✅ **Compression Algorithm** (`compression.py`): Character-level truncation
✅ **Subject Model Interface** (`agent.py`): Azure OpenAI, Anthropic, custom providers
✅ **Result Serialization**: JSON format matching paper appendix examples
✅ **Jury System** (`llm_jury.py`): Three-judge consensus with variance tracking
✅ **Metrics Pipeline** (`analyze_results.py`): HOC, FG, Decay, MCA, CI
✅ **CognitiveProfiler API** (`cognitive_profiler.py`): High-level interface from paper

### Expected API Costs

For a complete evaluation (9 models × 8 concepts × 5 compression levels):
- **Subject responses**: 1,800 API calls (5 turns each)
- **Jury evaluations**: 5,400 API calls (3 judges × 1,800 responses)
- **Interviewer calls**: ~1,800 (adaptive questioning)
- **Total**: ~9,000 API calls per model
- **Estimated cost**: ~$300-400 USD per model (Azure pricing, varies by model)

The paper's full evaluation (9 models) cost ~$2,847 USD total.