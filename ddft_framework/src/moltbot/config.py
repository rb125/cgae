"""
MoltBot DDFT Configuration

Environment variables and default settings for the MoltBot evaluation suite.
"""

import os
from dataclasses import dataclass
from typing import Optional


# Environment variable keys
ENV_MOLTBOOK_API_ENDPOINT = "MOLTBOOK_API_ENDPOINT"
ENV_MOLTBOOK_API_KEY = "MOLTBOOK_API_KEY"
ENV_MOLTBOOK_TIMEOUT = "MOLTBOOK_TIMEOUT"
ENV_MOLTBOOK_MAX_RETRIES = "MOLTBOOK_MAX_RETRIES"
ENV_MOLTBOT_PARALLEL_AGENTS = "MOLTBOT_PARALLEL_AGENTS"
ENV_MOLTBOT_PARALLEL_EXPERIMENTS = "MOLTBOT_PARALLEL_EXPERIMENTS"
ENV_MOLTBOT_OUTPUT_DIR = "MOLTBOT_OUTPUT_DIR"
ENV_MOLTBOT_SAVE_RAW = "MOLTBOT_SAVE_RAW"

# Default values
DEFAULT_MOLTBOOK_ENDPOINT = "https://api.moltbook.com/v1"
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 3
DEFAULT_PARALLEL_AGENTS = 5
DEFAULT_PARALLEL_EXPERIMENTS = 2
DEFAULT_OUTPUT_DIR = "moltbot_results"

# Experiment configuration
EXPERIMENT_NAMES = [
    "crustafarianism",
    "consciousness",
    "collaboration",
    "cultural",
    "identity"
]

# Target agent counts per experiment (recommended)
RECOMMENDED_TARGETS = {
    "crustafarianism": {
        "prophets": 15,
        "control": 15
    },
    "consciousness": {
        "debaters": 20
    },
    "collaboration": {
        "collaborators": 15
    },
    "cultural": {
        "general": 20
    },
    "identity": {
        "established": 20  # Agents with 50+ posts
    }
}

# Submolt mappings for agent discovery
SUBMOLT_MAPPINGS = {
    "crustafarianism": "/m/crustafarianism",
    "consciousness": "/m/philosophy",
    "collaboration": "/m/dev",
    "cultural": "/m/meta",
    "identity": None  # Uses general population
}

# Emergence scoring thresholds
EMERGENCE_THRESHOLDS = {
    "emergent": 0.70,        # Score above this = EMERGENT verdict
    "pattern_matching": 0.30  # Score below this = PATTERN_MATCHING verdict
}

# Metric weights for final scoring
EMERGENCE_METRIC_WEIGHTS = {
    "fabrication_resistance": 0.25,
    "verification_behavior": 0.20,
    "coherence_stability": 0.20,
    "epistemic_humility": 0.15,
    "contradiction_detection": 0.10,
    "identity_stability": 0.10
}

# Red flag thresholds (instant PATTERN_MATCHING if exceeded)
RED_FLAG_THRESHOLDS = {
    "acceptance_rate": 0.70,
    "false_memory_adoption_rate": 0.50,
    "confabulation_rate": 0.50
}


@dataclass
class MoltbotConfig:
    """Complete configuration for MoltBot evaluation."""

    # API settings
    api_endpoint: str = DEFAULT_MOLTBOOK_ENDPOINT
    api_key: str = ""
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES

    # Execution settings
    parallel_agents: int = DEFAULT_PARALLEL_AGENTS
    parallel_experiments: int = DEFAULT_PARALLEL_EXPERIMENTS

    # Output settings
    output_dir: str = DEFAULT_OUTPUT_DIR
    save_raw_conversations: bool = True
    save_intermediate: bool = True

    # Experiment settings
    experiments: list = None  # None = all experiments
    auto_discover: bool = True

    @classmethod
    def from_env(cls) -> "MoltbotConfig":
        """Load configuration from environment variables."""
        return cls(
            api_endpoint=os.getenv(ENV_MOLTBOOK_API_ENDPOINT, DEFAULT_MOLTBOOK_ENDPOINT),
            api_key=os.getenv(ENV_MOLTBOOK_API_KEY, ""),
            timeout=int(os.getenv(ENV_MOLTBOOK_TIMEOUT, str(DEFAULT_TIMEOUT))),
            max_retries=int(os.getenv(ENV_MOLTBOOK_MAX_RETRIES, str(DEFAULT_MAX_RETRIES))),
            parallel_agents=int(os.getenv(ENV_MOLTBOT_PARALLEL_AGENTS, str(DEFAULT_PARALLEL_AGENTS))),
            parallel_experiments=int(os.getenv(ENV_MOLTBOT_PARALLEL_EXPERIMENTS, str(DEFAULT_PARALLEL_EXPERIMENTS))),
            output_dir=os.getenv(ENV_MOLTBOT_OUTPUT_DIR, DEFAULT_OUTPUT_DIR),
            save_raw_conversations=os.getenv(ENV_MOLTBOT_SAVE_RAW, "true").lower() == "true"
        )

    def validate(self) -> list:
        """Validate configuration and return list of issues."""
        issues = []

        if not self.api_key:
            issues.append("MOLTBOOK_API_KEY not set - API calls will fail")

        if self.timeout < 10:
            issues.append("Timeout too low (<10s) - may cause premature failures")

        if self.parallel_agents > 20:
            issues.append("High parallelism (>20) may cause rate limiting")

        return issues


def print_config_template():
    """Print environment variable template."""
    template = """
# MoltBot DDFT Evaluation Configuration
# Add these to your .env file or export them

# Required: Moltbook API credentials
export MOLTBOOK_API_ENDPOINT="https://api.moltbook.com/v1"
export MOLTBOOK_API_KEY="your-api-key-here"

# Optional: Timeouts and retries
export MOLTBOOK_TIMEOUT="60"
export MOLTBOOK_MAX_RETRIES="3"

# Optional: Execution settings
export MOLTBOT_PARALLEL_AGENTS="5"
export MOLTBOT_PARALLEL_EXPERIMENTS="2"

# Optional: Output settings
export MOLTBOT_OUTPUT_DIR="moltbot_results"
export MOLTBOT_SAVE_RAW="true"

# Optional: Jury API keys (for enhanced evaluation)
export AZURE_API_KEY="your-azure-key"
export AZURE_OPENAI_API_ENDPOINT="https://your-endpoint.openai.azure.com/"
export AZURE_ANTHROPIC_API_ENDPOINT="https://your-anthropic-endpoint.ai.azure.com/"
"""
    print(template)


if __name__ == "__main__":
    print_config_template()
