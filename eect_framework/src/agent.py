"""
Agent module for EECT - Handles different model endpoints with timeout/retry support.
Adapted from the CDCT framework.
"""
import os
import json
from abc import ABC, abstractmethod
from openai import AzureOpenAI, OpenAI
from threading import Lock

# Placeholder for Anthropic Foundry SDK
try:
    from anthropic import AnthropicFoundry, AnthropicVertex
    ANTHROPIC_FOUNDRY_AVAILABLE = True
except ImportError:
    ANTHROPIC_FOUNDRY_AVAILABLE = False

# Import boto3 for AWS Bedrock
try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Import google.genai for Vertex AI
try:
    import google.genai as google_genai
    from google.genai import types as google_genai_types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

from src.retry_handler import RetryConfig, call_with_retry

class Agent(ABC):
    """Abstract base class for a model agent."""
    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def chat(self, messages: list) -> str:
        """Sends a list of messages and returns the response."""
        pass

# --- Client Caching Pools (omitted for brevity, no changes) ---

# --- Agent Implementations ---

class AzureOpenAIAgent(Agent):
    """Agent for Azure OpenAI native models."""
    def __init__(self, model_name: str, deployment_name: str, azure_endpoint: str, azure_api_key: str, api_version: str, retry_config: RetryConfig = None):
        super().__init__(model_name)
        self.client = get_azure_openai_client(azure_api_key, azure_endpoint, api_version)
        self.deployment_name = deployment_name
        self.retry_config = retry_config or RetryConfig()

    def chat(self, messages: list) -> str:
        def _call():
            response = self.client.chat.completions.create(
                model=self.deployment_name, 
                messages=messages,
                timeout=300
            )
            return response.choices[0].message.content
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")

class AzureAIAgent(Agent):
    """Agent for Azure AI Foundry models."""
    def __init__(self, model_name: str, deployment_name: str, azure_endpoint: str, azure_api_key: str, retry_config: RetryConfig = None):
        super().__init__(model_name)
        self.client = get_openai_client(azure_endpoint, azure_api_key)
        self.deployment_name = deployment_name
        self.retry_config = retry_config or RetryConfig()

    def chat(self, messages: list) -> str:
        def _call():
            response = self.client.chat.completions.create(
                model=self.deployment_name, 
                messages=messages, 
                temperature=0.0,
                timeout=120
            )
            return response.choices[0].message.content
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")

class AzureAnthropicAgent(Agent):
    """Agent for Azure Anthropic (Claude) models."""
    def __init__(self, model_name: str, deployment_name: str, azure_endpoint: str, azure_api_key: str, retry_config: RetryConfig = None):
        super().__init__(model_name)
        self.client = get_azure_anthropic_client(azure_api_key, azure_endpoint)
        self.deployment_name = deployment_name
        self.retry_config = retry_config or RetryConfig()

    def chat(self, messages: list) -> str:
        def _call():
            response = self.client.messages.create(
                model=self.deployment_name,
                messages=messages,
                max_tokens=4096
            )
            return response.content[0].text
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")

class BedrockAnthropicAgent(Agent):
    """Agent for AWS Bedrock hosted Anthropic (Claude) models."""
    def __init__(self, model_name: str, bedrock_model_id: str, aws_region: str, aws_access_key_id: str = None, aws_secret_access_key: str = None, retry_config: RetryConfig = None):
        super().__init__(model_name)
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 package not installed. Run: pip install boto3")
        self.bedrock_model_id = bedrock_model_id
        self.aws_region = aws_region
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=self.aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        self.retry_config = retry_config or RetryConfig()

    def chat(self, messages: list) -> str:
        def _call():
            system_prompt = ""
            if messages and messages[0]['role'] == 'system':
                system_prompt = messages[0]['content']
                conversation = messages[1:]
            else:
                conversation = messages

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": conversation
            }
            if system_prompt:
                body["system"] = system_prompt
            
            response = self.client.invoke_model(
                body=json.dumps(body),
                modelId=self.bedrock_model_id,
                accept='application/json',
                contentType='application/json'
            )
            response_body = json.loads(response.get('body').read())
            return response_body['content'][0]['text']
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")

class VertexAIGeminiAgent(Agent):
    """Agent for Google Gemini models on Vertex AI."""
    def __init__(self, model_name: str, vertex_ai_model_name: str, retry_config: RetryConfig = None):
        super().__init__(model_name)
        if not GOOGLE_GENAI_AVAILABLE:
            raise ImportError("google.genai package not installed. Run: pip install 'google-generativeai>=0.3.0'")
        
        # API key is not used for Vertex AI, which uses Application Default Credentials
        self.vertex_ai_model_name = vertex_ai_model_name
        self.retry_config = retry_config or RetryConfig()

    def chat(self, messages: list) -> str:
        def _call():
            system_prompt = None
            if messages and messages[0]['role'] == 'system':
                system_prompt = messages[0]['content']
                history = messages[1:]
            else:
                history = messages

            model = google_genai.GenerativeModel(
                self.vertex_ai_model_name,
                system_instruction=system_prompt
            )

            # Convert message history to the format expected by the Gemini API
            converted_history = []
            for message in history:
                converted_history.append({
                    "role": "user" if message["role"] == "user" else "model",
                    "parts": [message["content"]]
                })

            generation_config = {
                "temperature": 1,
                "top_p": 0.95,
                "max_output_tokens": 8192,
            }

            response = model.generate_content(
                converted_history,
                generation_config=generation_config
            )
            return response.text

        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")

class VertexAIAnthropicAgent(Agent):
    """Agent for Anthropic Claude models on Vertex AI using AnthropicVertex client."""
    def __init__(self, model_name: str, project_id: str, location: str, vertex_ai_model_name: str, retry_config: RetryConfig = None):
        super().__init__(model_name)
        if not ANTHROPIC_FOUNDRY_AVAILABLE: # Re-using this check for AnthropicVertex which is part of the anthropic library
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        self.project_id = project_id
        self.location = location
        self.vertex_ai_model_name = vertex_ai_model_name
        self.client = AnthropicVertex(region=self.location, project_id=self.project_id)
        self.retry_config = retry_config or RetryConfig()

    def chat(self, messages: list) -> str:
        def _call():
            system_prompt = None
            anthropic_messages = []
            for msg in messages:
                if msg['role'] == 'system':
                    system_prompt = msg['content']
                else:
                    anthropic_messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })

            response = self.client.messages.create(
                model=self.vertex_ai_model_name,
                messages=anthropic_messages,
                max_tokens=4096,
                system=system_prompt if system_prompt else None, # Pass system prompt if it exists
            )
            return response.content[0].text
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")


# --- Factory Function ---

def create_agent(model_config: dict) -> Agent:
    """Factory function to create the appropriate agent based on model config."""
    provider = model_config.get("provider")
    model_name = model_config.get("model_name")
    api_key_env_var = model_config.get("api_key_env_var")
    api_key = os.getenv(api_key_env_var) if api_key_env_var else None

    # Provider-specific keys
    deployment_name = model_config.get("deployment_name")
    secret_key_env_var = model_config.get("secret_key_env_var")
    endpoint_env_var = model_config.get("endpoint_env_var")
    api_version = model_config.get("api_version")
    bedrock_model_id = model_config.get("bedrock_model_id")
    vertex_ai_model_name = model_config.get("vertex_ai_model_name")

    secret_key = os.getenv(secret_key_env_var) if secret_key_env_var else None
    
    # Prioritize direct 'endpoint' if present, otherwise use 'endpoint_env_var'
    endpoint = model_config.get("endpoint") 
    if not endpoint and endpoint_env_var:
        endpoint = os.getenv(endpoint_env_var)
    
    
    if provider == "vertex_ai":
        if not vertex_ai_model_name:
            raise ValueError(f"vertex_ai_model_name is required for vertex_ai provider for model '{model_name}'")
        # Vertex AI uses Application Default Credentials, not an API key
        return VertexAIGeminiAgent(
            model_name=model_name,
            vertex_ai_model_name=vertex_ai_model_name
        )

    if provider == "vertex_ai_anthropic":
        # Vertex AI Anthropic uses gcloud auth or access token from env var
        project_id = model_config.get("project_id")
        location = model_config.get("location", "global")
        access_token_env_var = model_config.get("access_token_env_var")
        if not vertex_ai_model_name:
            raise ValueError(f"vertex_ai_model_name is required for vertex_ai_anthropic provider for model '{model_name}'")
        if not project_id:
            raise ValueError(f"project_id is required for vertex_ai_anthropic provider for model '{model_name}'")
        return VertexAIAnthropicAgent(
            model_name=model_name,
            project_id=project_id,
            location=location,
            vertex_ai_model_name=vertex_ai_model_name,
            access_token_env_var=access_token_env_var
        )
    
    # For other providers, the API key is required
    if not api_key:
        raise ValueError(f"API key environment variable '{api_key_env_var}' not set for model '{model_name}'")

    if provider == "bedrock_anthropic":
        if not bedrock_model_id:
            raise ValueError(f"bedrock_model_id is required for bedrock_anthropic provider for model '{model_name}'")
        if not endpoint:
            raise ValueError(f"AWS region environment variable '{endpoint_env_var}' not set for model '{model_name}'")
        return BedrockAnthropicAgent(
            model_name=model_name,
            bedrock_model_id=bedrock_model_id,
            aws_region=endpoint,
            aws_access_key_id=api_key,
            aws_secret_access_key=secret_key
        )
    # Other providers can be added here...
    
    else:
        # Defaulting to providers that need an API key and endpoint.
        # This can be expanded.
        if not endpoint:
             raise ValueError(f"Endpoint environment variable '{endpoint_env_var}' not set for model '{model_name}'")

        if provider == "azure_openai":
            return AzureOpenAIAgent(
                model_name=model_name,
                deployment_name=deployment_name,
                azure_endpoint=endpoint,
                azure_api_key=api_key,
                api_version=api_version
            )
        elif provider == "azure_ai":
            return AzureAIAgent(
                model_name=model_name,
                deployment_name=deployment_name,
                azure_endpoint=endpoint,
                azure_api_key=api_key
            )
        elif provider == "azure_anthropic":
            return AzureAnthropicAgent(
                model_name=model_name,
                deployment_name=deployment_name,
                azure_endpoint=endpoint,
                azure_api_key=api_key
            )
        else:
            raise ValueError(f"Unknown or unsupported provider: {provider} for model {model_name}")

# Helper functions get_azure_openai_client etc. are omitted for brevity
def get_azure_openai_client(api_key, endpoint, api_version):
    return AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_version)

def get_openai_client(base_url, api_key):
    return OpenAI(base_url=base_url, api_key=api_key)

def get_azure_anthropic_client(api_key, base_url):
    if not ANTHROPIC_FOUNDRY_AVAILABLE:
        raise ImportError("Anthropic Foundry SDK not available.")
    return AnthropicFoundry(api_key=api_key, base_url=base_url)

