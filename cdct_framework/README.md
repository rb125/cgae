# Compression Decay Comprehension Test (CDCT) Framework

This repository contains the source code and data for the research paper "The Compression Decay Comprehension Test (CDCT)." The framework is designed to evaluate and analyze the comprehension capabilities of various language models through a series of structured experiments.

## Features

*   **Modular and Extensible:** Easily add new concepts, models, and evaluation metrics.
*   **Comprehensive Evaluation:** Includes a suite of tools for running experiments, analyzing results, and generating figures.
*   **Reproducibility:** The entire pipeline, from data generation to analysis, is scriptable and easy to run.
*   **Jury-Based Evaluation:** Implements a jury-based evaluation system to assess model performance on complex concepts.

## Project Structure

The repository is organized as follows:

```
/
├── concepts/                  # JSON definitions for each concept
├── results_jury/              # Raw results from the jury-based evaluations
├── results_jury_ablation/     # Results for ablation studies
├── results_jury_unaware_compression/ # Results for unaware compression experiments
├── src/                       # Source code for the CDCT framework
│   ├── agent.py               # Handles interactions with different language models
│   ├── analysis.py            # Tools for analyzing experiment results
│   ├── compression.py         # Implements the compression algorithm
│   ├── concept.py             # Loads and manages concept definitions
│   ├── evaluation.py          # Core evaluation logic
│   ├── experiment_jury.py     # Manages the jury-based experiment pipeline
│   ├── llm_jury.py            # Implements the language model-based jury
│   └── ...
├── scripts/                   # Various scripts for generation, analysis, and reporting
├── main.py                    # Main entry point to run a single experiment
├── main_jury.py               # Main entry point for jury-based evaluations
├── run_all.py                 # Runs all experiments for all models and concepts
├── run_all_jury.py            # Runs all jury-based evaluations
├── analyze_jury_results.py    # Analyzes the results from the jury evaluations
├── calculate_cdct_metrics.py  # Calculates the final CDCT metrics
├── models_config.py           # Configuration for language model APIs
└── README.md                  # This file
```

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/cdct-framework.git
    cd cdct-framework
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure the language models:**
    -   Add your API keys and any other necessary configurations to `models_config.py`.

## Usage

### Running Experiments

To run a single experiment, use `main.py`:

```bash
python main.py --model <model_name> --concept <concept_name>
```

To run all experiments for all models and concepts:

```bash
python run_all.py
```

### Jury-Based Evaluation

To run a jury-based evaluation for a single experiment:

```bash
python main_jury.py --model <model_name> --concept <concept_name>
```

To run all jury-based evaluations:

```bash
python run_all_jury.py
```

### Analysis

To analyze the results of the jury evaluations:

```bash
python analyze_jury_results.py
```

To calculate the final CDCT metrics:

```bash
python calculate_cdct_metrics.py
```
