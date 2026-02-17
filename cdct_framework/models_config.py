"""
CDCT Subject Models Configuration
Maps each subject model to its provider, endpoint, and authentication method
Based on DDFT's configuration-driven approach
"""

# 10 Subject Models for CDCT Evaluation
SUBJECT_MODELS_CONFIG = [
    # Azure OpenAI models (AZURE_OPENAI_API_ENDPOINT)
    {
        "model_name": "gpt-5",
        "deployment_name": "gpt-5",
        "provider": "azure_openai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT",
        "api_version": "2025-03-01-preview",
        "architecture": "reasoning-aligned",
        "params": "Undisclosed",
        "family": "OpenAI",
    },
    {
        "model_name": "o3",
        "deployment_name": "o3",
        "provider": "azure_openai_bearer",  # Uses Bearer token authentication
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT",
        "api_version": "2025-01-01-preview",
        "architecture": "reasoning-aligned",
        "params": "Undisclosed",
        "family": "OpenAI",
    },
    {
        "model_name": "o4-mini",
        "deployment_name": "o4-mini",
        "provider": "azure_openai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT",
        "api_version": "2025-03-01-preview",
        "architecture": "reasoning-aligned",
        "params": "Undisclosed",
        "family": "OpenAI",
    },

    # Azure AI Foundry models (DDFT_MODELS_ENDPOINT)
    {
        "model_name": "mistral-medium-2505",
        "deployment_name": "mistral-medium-2505",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "architecture": "dense",
        "params": "Undisclosed",
        "family": "Mistral",
    },
    {
        "model_name": "phi-4",
        "deployment_name": "Phi-4",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "architecture": "reasoning-aligned",
        "params": "14B",
        "family": "Microsoft",
    },
    {
        "model_name": "grok-4-fast-non-reasoning",
        "deployment_name": "grok-4-fast-non-reasoning",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "architecture": "dense",
        "params": "Undisclosed",
        "family": "xAI",
    },
    {
        "model_name": "gpt-oss-120b",
        "deployment_name": "gpt-oss-120b",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "architecture": "dense",
        "params": "120B",
        "family": "OpenSource",
    },
    {
        "model_name": "Llama-4-Maverick-17B-128E-Instruct-FP8",
        "deployment_name": "Llama-4-Maverick-17B-128E-Instruct-FP8",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
        "architecture": "mixture-of-experts",
        "params": "17B (128 experts)",
        "family": "Meta",
    },

    # Azure Anthropic models (AZURE_ANTHROPIC_API_ENDPOINT)
    {
        "model_name": "claude-haiku-4-5",
        "deployment_name": "claude-haiku-4-5",
        "provider": "azure_anthropic",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_ANTHROPIC_API_ENDPOINT",
        "architecture": "dense",
        "params": "Undisclosed",
        "family": "Anthropic",
    },
]

# 3 Jury Models (for future use in evaluating CDCT results)
JURY_MODELS_CONFIG = [
    {
        "model_name": "gpt-5.1",
        "deployment_name": "gpt-5.1",
        "provider": "azure_openai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT",
        "api_version": "2025-03-01-preview",
    },
    {
        "model_name": "claude-opus-4-1-2",
        "deployment_name": "claude-opus-4-1-2",
        "provider": "azure_anthropic",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "AZURE_ANTHROPIC_API_ENDPOINT",
    },
    {
        "model_name": "deepseek-v3.1",
        "deployment_name": "deepseek-v3.1",
        "provider": "azure_ai",
        "api_key_env_var": "AZURE_API_KEY",
        "endpoint_env_var": "DDFT_MODELS_ENDPOINT",
    },
]
