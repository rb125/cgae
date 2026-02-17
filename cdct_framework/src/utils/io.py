# API Keys and endpoints for different models
# Loaded from environment variables for security
import os

AZURE_OPENAI_SETTINGS = {
    "api_key": os.getenv("AZURE_API_KEY"),
    "azure_endpoint": os.getenv("AZURE_OPENAI_API_ENDPOINT"),
    "api_version": "2025-03-01-preview"
}

DDFT_MODELS_ENDPOINT = os.getenv("DDFT_MODELS_ENDPOINT")
AZURE_ANTHROPIC_API_ENDPOINT = os.getenv("AZURE_ANTHROPIC_API_ENDPOINT")
