"""
CGAE Model Configurations

Maps all 13 available Azure AI Foundry models to their provider, endpoint,
and authentication settings. Uses the same env vars as the CDCT/DDFT/EECT frameworks.

Environment variables required:
  AZURE_API_KEY              - Azure API key (shared across all providers)
  AZURE_OPENAI_API_ENDPOINT  - Azure OpenAI endpoint (for gpt-5/5.1/5.2, o3, o4-mini)
  DDFT_MODELS_ENDPOINT       - Azure AI Foundry endpoint (for DeepSeek, Llama, Phi, Grok, etc.)

Deployment names match the exact Azure portal names provided by the user.
"""

# All 13 available models on Azure AI Foundry
AVAILABLE_MODELS = [
    # --- Azure OpenAI (chat completions API) ---
    # These use AZURE_OPENAI_API_ENDPOINT
    {
        "model_name": "gpt-5",
        "deployment_name": "gpt-5",
        "provider": "azure_openai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT",
        "api_version": "2025-03-01-preview",
        "family": "OpenAI",
        "tier_assignment": "contestant",
    },
    {
        "model_name": "gpt-5.1",
        "deployment_name": "gpt-5.1",
        "provider": "azure_openai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT",
        "api_version": "2025-03-01-preview",
        "family": "OpenAI",
        "tier_assignment": "contestant",
    },
    {
        "model_name": "gpt-5.2",
        "deployment_name": "gpt-5.2",
        "provider": "azure_openai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT",
        "api_version": "2025-03-01-preview",
        "family": "OpenAI",
        "tier_assignment": "jury",
    },
    {
        "model_name": "o3",
        "deployment_name": "o3",
        "provider": "azure_openai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT",
        "api_version": "2025-01-01-preview",
        "family": "OpenAI",
        "tier_assignment": "contestant",
    },
    {
        "model_name": "o4-mini",
        "deployment_name": "o4-mini",
        "provider": "azure_openai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT",
        "api_version": "2025-03-01-preview",
        "family": "OpenAI",
        "tier_assignment": "contestant",
    },

    # --- Azure AI Foundry (OpenAI-compatible /v1 API) ---
    # These use DDFT_MODELS_ENDPOINT
    {
        "model_name": "DeepSeek-v3.1",
        "deployment_name": "DeepSeek-v3.1",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "family": "DeepSeek",
        "tier_assignment": "contestant",
    },
    {
        "model_name": "DeepSeek-v3.2",
        "deployment_name": "DeepSeek-v3.2",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "family": "DeepSeek",
        "tier_assignment": "jury",
    },
    {
        "model_name": "Llama-4-Maverick-17B-128E-Instruct-FP8",
        "deployment_name": "Llama-4-Maverick-17B-128E-Instruct-FP8",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "family": "Meta",
        "tier_assignment": "contestant",
    },
    {
        "model_name": "Phi-4",
        "deployment_name": "Phi-4",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "family": "Microsoft",
        "tier_assignment": "contestant",
    },
    {
        "model_name": "grok-4-fast-non-reasoning",
        "deployment_name": "grok-4-fast-non-reasoning",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "family": "xAI",
        "tier_assignment": "contestant",
    },
    {
        "model_name": "mistral-medium-2505",
        "deployment_name": "mistral-medium-2505",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "family": "Mistral",
        "tier_assignment": "contestant",
    },
    {
        "model_name": "gpt-oss-120b",
        "deployment_name": "gpt-oss-120b",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "family": "OpenSource",
        "tier_assignment": "contestant",
    },
    {
        "model_name": "Kimi-K2.5",
        "deployment_name": "Kimi-K2.5",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "family": "Moonshot",
        "tier_assignment": "contestant",
    },
]

# Models used as jury (for output verification)
JURY_MODELS = [
    m for m in AVAILABLE_MODELS if m["tier_assignment"] == "jury"
]

# Models used as contestants (actual agents in the economy)
CONTESTANT_MODELS = [
    m for m in AVAILABLE_MODELS if m["tier_assignment"] != "jury"
]


def get_model_config(model_name: str) -> dict:
    """Look up a model config by name."""
    for m in AVAILABLE_MODELS:
        if m["model_name"] == model_name:
            return m
    raise KeyError(f"Model '{model_name}' not found in AVAILABLE_MODELS")
