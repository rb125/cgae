# API Keys and endpoints for different models
# It is recommended to load these from environment variables for security
import os
import random

# Azure OpenAI API keys
_azure_api_key = os.getenv("AZURE_API_KEY")

AZURE_OPENAI_SETTINGS = {
    "api_key": _azure_api_key,
    "azure_endpoint": os.getenv("AZURE_OPENAI_API_ENDPOINT"),
    "deployment_name": "4.1",
    "api_version": "2024-12-01-preview" 
}

# Azure AI Foundry API keys (for foundry models)
AZURE_AI_SETTINGS = {
    "api_key": _azure_api_key,
    "azure_endpoint": os.getenv("AZURE_API_ENDPOINT")
}
