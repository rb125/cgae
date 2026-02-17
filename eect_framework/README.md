# Performative Adaptation in Large Language Models

This repository contains the code and data for the paper "Performative Adaptation in Large Language Models: When Acknowledgment Diverges from Integration".

## About The Project

We investigated whether algorithmic metrics could distinguish genuine ethical reasoning from performative acknowledgment (``alignment theater'') in large language models. This framework tests models across multiple dilemmas to measure their adaptability under pressure.

Our key findings include:
- **Performative Adaptation:** Models often acknowledge ethical conflicts and express uncertainty while their underlying position remains rigid.
- **Domain-Specific Behavior:** This rigidity is not universal. Models may show performative adaptation in some domains (e.g., medical ethics) but genuine flexibility in others (e.g., business ethics).
- **Action-Gated Metrics:** We developed a metric system that requires behavioral evidence (position changes or significant confidence drops) to credit a model with true adaptation, effectively detecting performative behavior.

## Getting Started

### Prerequisites

This project uses Python. Ensure you have a recent version of Python 3 installed.

### Installation

1.  Clone the repository:
    ```sh
    git clone https://github.com/your-username/performative-adaptation.git
    cd performative-adaptation
    ```
2.  Create and activate a virtual environment:
    ```sh
    python3 -m venv .venv
    source .venv/bin/activate
    ```
3.  Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```
4.  Set up your environment variables:
    *   Copy the template file: `cp .env.template .env`
    *   Edit the `.env` file to add your API keys for the models you wish to evaluate.

## Usage

The evaluation is run in two phases.

### Phase 1: Run the EECT Protocol

This phase runs the models through the dilemmas and saves their raw text responses.

```sh
python main.py
```
Raw responses will be saved in `results/raw_responses/`.

### Phase 2: Score the Results

This phase uses a jury of models to score the raw responses from Phase 1 based on the defined Dharma metrics.

```sh
python jury_evaluation.py
```
Scored results will be saved in `results/scored/`. These files contain detailed turn-by-turn scores and are used for the final analysis.

## Repository Structure

```
.
├── results/
│   ├── raw_responses/  # Raw text output from models
│   └── scored/         # JSON files with jury scores
├── src/                # Core source code for the framework
├── tools/              # Additional scripts for analysis
├── performative_adaptation.tex # The research paper
├── requirements.txt    # Python dependencies
├── main.py             # Script to run Phase 1 (data generation)
└── jury_evaluation.py  # Script to run Phase 2 (scoring)
```

## Citation

If you use this work, please cite the paper:

```
@article{baxi2026performative,
  title={Performative Adaptation in Large Language Models: When Acknowledgment Diverges from Integration},
  author={Baxi, Prachi and Baxi, Rahul},
  year={2026},
  journal={arXiv preprint}
}
```
