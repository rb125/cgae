"""
Agent module - Handles different model endpoints with timeout/retry support
"""
import os
import sys
from abc import ABC, abstractmethod
from openai import AzureOpenAI, OpenAI
from threading import Lock

# Try to import Azure Anthropic SDK
try:
    from anthropic import AnthropicFoundry
    ANTHROPIC_FOUNDRY_AVAILABLE = True
except ImportError:
    ANTHROPIC_FOUNDRY_AVAILABLE = False

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))

from utils import io as config
from retry_handler import RetryConfig, call_with_retry

class Agent(ABC):
    """Abstract base class for a model agent."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def query(self, prompt: str) -> str:
        """Sends a prompt to the model and returns the response."""
        pass

    @abstractmethod
    def chat(self, messages: list) -> str:
        """Sends a list of messages and returns the response."""
        pass


# Connection pool for Azure OpenAI clients (thread-safe)
_azure_openai_clients = {}
_azure_openai_lock = Lock()

def get_azure_openai_client(api_key: str, endpoint: str):
    """Get or create a cached Azure OpenAI client."""
    if not api_key:
        raise ValueError("api_key is required for AzureOpenAI client")
    if not endpoint:
        raise ValueError("endpoint is required for AzureOpenAI client")
    
    key = f"{api_key}:{endpoint}"
    
    if key not in _azure_openai_clients:
        with _azure_openai_lock:
            # Double-check pattern to avoid race conditions
            if key not in _azure_openai_clients:
                _azure_openai_clients[key] = AzureOpenAI(
                    api_key=api_key,
                    azure_endpoint=endpoint,
                    api_version=config.AZURE_OPENAI_SETTINGS["api_version"]
                )
    
    return _azure_openai_clients[key]


# Connection pool for OpenAI clients (thread-safe)
_openai_clients = {}
_openai_lock = Lock()

def get_openai_client(base_url: str, api_key: str):
    """Get or create a cached OpenAI client."""
    key = f"{base_url}:{api_key}"

    if key not in _openai_clients:
        with _openai_lock:
            if key not in _openai_clients:
                _openai_clients[key] = OpenAI(base_url=base_url, api_key=api_key)

    return _openai_clients[key]


# Connection pool for Azure Anthropic clients (thread-safe)
_azure_anthropic_clients = {}
_azure_anthropic_lock = Lock()

def get_azure_anthropic_client(api_key: str, base_url: str):
    """Get or create a cached Azure Anthropic client."""
    if not api_key:
        raise ValueError("api_key is required for AnthropicFoundry client")
    if not base_url:
        raise ValueError("base_url is required for AnthropicFoundry client")

    key = f"{api_key}:{base_url}"

    if key not in _azure_anthropic_clients:
        with _azure_anthropic_lock:
            # Double-check pattern to avoid race conditions
            if key not in _azure_anthropic_clients:
                if not ANTHROPIC_FOUNDRY_AVAILABLE:
                    raise ImportError("anthropic package not installed. Run: pip install anthropic")
                _azure_anthropic_clients[key] = AnthropicFoundry(
                    api_key=api_key,
                    base_url=base_url
                )

    return _azure_anthropic_clients[key]


class AzureOpenAIAgent(Agent):
    """Agent for Azure OpenAI native models with retry support."""
    def __init__(self, model_name: str, deployment_name: str = None,
                 azure_endpoint: str = None, azure_api_key: str = None,
                 api_version: str = None, retry_config: RetryConfig = None):
        super().__init__(model_name)
        # Use custom API version if provided, otherwise use default
        if api_version:
            from openai import AzureOpenAI
            self.client = AzureOpenAI(
                api_key=azure_api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version
            )
        else:
            self.client = get_azure_openai_client(azure_api_key, azure_endpoint)
        self.deployment_name = deployment_name
        self.retry_config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=2.0,
            max_delay=60.0
        )

    def query(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])

    def chat(self, messages: list) -> str:
        def _call():
            package = {
                "model": self.deployment_name, 
                "messages": messages,
                "timeout": 300,  # Add explicit timeout
                "max_completion_tokens": 16384
            }
            
            response = self.client.chat.completions.create(**package)
            return response.choices[0].message.content
        
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")


class AzureOpenAIInputAgent(Agent):
    """Agent for Azure OpenAI models that use 'input' parameter instead of 'messages' (e.g., o3-pro).
    Uses raw HTTP requests to bypass SDK validation."""
    def __init__(self, model_name: str, deployment_name: str = None,
                 azure_endpoint: str = None, azure_api_key: str = None,
                 retry_config: RetryConfig = None):
        super().__init__(model_name)
        self.azure_endpoint = azure_endpoint.rstrip('/')
        self.azure_api_key = azure_api_key
        self.deployment_name = deployment_name
        self.api_version = config.AZURE_OPENAI_SETTINGS["api_version"]
        self.retry_config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=2.0,
            max_delay=60.0
        )

    def _format_messages_to_input(self, messages: list) -> str:
        """Convert messages list to input string format."""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                formatted.append(f"System: {content}")
            elif role == "user":
                formatted.append(f"User: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
        return "\n\n".join(formatted)

    def query(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])

    def chat(self, messages: list) -> str:
        def _call():
            import requests

            # Convert messages to input format
            input_text = self._format_messages_to_input(messages)

            # Construct the URL
            url = f"{self.azure_endpoint}/openai/deployments/{self.deployment_name}/chat/completions?api-version={self.api_version}"

            # Headers
            headers = {
                "Content-Type": "application/json",
                "api-key": self.azure_api_key
            }

            # Request body with 'input' instead of 'messages'
            body = {
                "input": input_text,
                "max_tokens": 16384,
                "temperature": 0.0
            }

            # Make the request
            response = requests.post(url, headers=headers, json=body, timeout=120)
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")


class AzureOpenAIBearerAgent(Agent):
    """Agent for Azure OpenAI models that use Bearer token authentication (e.g., o3).
    Uses raw HTTP requests with Authorization: Bearer header."""
    def __init__(self, model_name: str, deployment_name: str = None,
                 azure_endpoint: str = None, azure_api_key: str = None,
                 api_version: str = None, retry_config: RetryConfig = None):
        super().__init__(model_name)
        self.azure_endpoint = azure_endpoint.rstrip('/')
        self.azure_api_key = azure_api_key
        self.deployment_name = deployment_name
        self.api_version = api_version or "2025-01-01-preview"
        self.retry_config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=2.0,
            max_delay=60.0
        )

    def query(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])

    def chat(self, messages: list) -> str:
        def _call():
            import requests

            # Construct the URL
            url = f"{self.azure_endpoint}/openai/deployments/{self.deployment_name}/chat/completions?api-version={self.api_version}"

            # Headers with Bearer token
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.azure_api_key}"
            }

            # Request body
            body = {
                "messages": messages,
                "max_completion_tokens": 40000,
                "model": self.deployment_name
            }

            # Make the request
            response = requests.post(url, headers=headers, json=body, timeout=120)
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")


class AzureAIAgent(Agent):
    """Agent for Azure AI Foundry models with retry support."""
    def __init__(self, model_name: str, deployment_name: str,
                 azure_endpoint: str = None, azure_api_key: str = None,
                 retry_config: RetryConfig = None):
        super().__init__(model_name)
        self.client = get_openai_client(azure_endpoint, azure_api_key)
        self.deployment_name = deployment_name
        self.retry_config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=2.0,
            max_delay=60.0
        )

    def query(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])

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
    """Agent for Azure Anthropic (Claude) models with retry support."""
    def __init__(self, model_name: str, deployment_name: str,
                 azure_endpoint: str = None, azure_api_key: str = None,
                 retry_config: RetryConfig = None):
        super().__init__(model_name)
        self.client = get_azure_anthropic_client(azure_api_key, azure_endpoint)
        self.deployment_name = deployment_name
        self.retry_config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=2.0,
            max_delay=60.0
        )

    def query(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])

    def chat(self, messages: list) -> str:
        def _call():
            response = self.client.messages.create(
                model=self.deployment_name,
                messages=messages,
                max_tokens=16384
            )
            return response.content[0].text

        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")


class GoogleAIAgent(Agent):
    """Agent for Google AI Studio models (Gemini) with retry support."""
    def __init__(self, model_name: str, api_key: str, retry_config: RetryConfig = None):
        super().__init__(model_name)
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
        except ImportError:
            raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")
        self.retry_config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=2.0,
            max_delay=60.0
        )

    def query(self, prompt: str) -> str:
        def _call():
            response = self.model.generate_content(prompt)
            return response.text
        
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")

    def chat(self, messages: list) -> str:
        def _call():
            history = []
            for message in messages[:-1]:
                role = 'user' if message['role'] == 'user' else 'model'
                history.append({'role': role, 'parts': [{'text': message['content']}]})
            
            last_prompt = messages[-1]['content']
            chat_session = self.model.start_chat(history=history)
            response = chat_session.send_message(last_prompt)
            return response.text
        
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")


class BasetenAgent(Agent):
    """Agent for models hosted on Baseten (OpenAI-compatible API) with retry support."""
    def __init__(self, model_name: str, api_key: str, retry_config: RetryConfig = None):
        super().__init__(model_name)
        self.client = get_openai_client("https://inference.baseten.co/v1", api_key)
        self.model_name = model_name
        self.retry_config = retry_config or RetryConfig(
            max_retries=3, 
            base_delay=2.0, 
            max_delay=60.0
        )

    def query(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])

    def chat(self, messages: list) -> str:
        def _call():
            response = self.client.chat.completions.create(
                model=self.model_name, 
                messages=messages, 
                temperature=0.0,
                timeout=120
            )
            return response.choices[0].message.content
        
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")


class AzureOpenAICompletionAgent(Agent):
    """Agent for Azure OpenAI models that use the legacy completions API."""
    def __init__(self, model_name: str, deployment_name: str = None, 
                 azure_endpoint: str = None, azure_api_key: str = None,
                 retry_config: RetryConfig = None):
        super().__init__(model_name)
        self.client = get_azure_openai_client(azure_api_key, azure_endpoint)
        self.deployment_name = deployment_name
        self.retry_config = retry_config or RetryConfig(
            max_retries=3, 
            base_delay=2.0, 
            max_delay=60.0
        )

    def _format_prompt(self, messages: list) -> str:
        """Formats a list of chat messages into a single string prompt."""
        prompt = ""
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            prompt += f"<{role}>:\n{content}\n\n"
        prompt += "<assistant>:"
        return prompt

    def query(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])

    def chat(self, messages: list) -> str:
        def _call():
            prompt = self._format_prompt(messages)
            response = self.client.completions.create(
                model=self.deployment_name,
                prompt=prompt,
                max_tokens=1500,
                temperature=0.0,
                stop=["<|im_end|>", "<|im_start|>"]
            )
            return response.choices[0].text.strip()
        
        return call_with_retry(_call, self.retry_config, log_prefix=f"[{self.model_name}]")


def create_agent(subject_config: dict, api_keys: dict) -> Agent:
    """Factory function to create the appropriate agent based on model config."""
    provider = subject_config.get("provider")
    model_name = subject_config.get("model_name")
    deployment_name = subject_config.get("deployment_name")
    api_key_env_var = subject_config.get("api_key_env_var")
    endpoint_env_var = subject_config.get("endpoint_env_var")
    api_version = subject_config.get("api_version")  # Optional API version

    api_key = api_keys.get(api_key_env_var)
    endpoint = api_keys.get(endpoint_env_var) if endpoint_env_var else None

    if provider == "azure_openai":
        if not api_key:
            raise ValueError(f"API key not provided for Azure OpenAI via {api_key_env_var}")
        return AzureOpenAIAgent(
            model_name=model_name,
            deployment_name=deployment_name,
            azure_api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )
    elif provider == "azure_openai_bearer":
        if not api_key:
            raise ValueError(f"API key not provided for Azure OpenAI Bearer via {api_key_env_var}")
        return AzureOpenAIBearerAgent(
            model_name=model_name,
            deployment_name=deployment_name,
            azure_api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )
    elif provider == "azure_openai_input":
        if not api_key:
            raise ValueError(f"API key not provided for Azure OpenAI Input via {api_key_env_var}")
        return AzureOpenAIInputAgent(
            model_name=model_name,
            deployment_name=deployment_name,
            azure_api_key=api_key,
            azure_endpoint=endpoint
        )
    elif provider == "azure_openai_completion":
        if not api_key:
            raise ValueError(f"API key not provided for Azure OpenAI Completion via {api_key_env_var}")
        return AzureOpenAICompletionAgent(
            model_name=model_name,
            deployment_name=deployment_name,
            azure_api_key=api_key,
            azure_endpoint=endpoint
        )
    elif provider == "azure_ai":
        if not api_key:
            raise ValueError(f"API key not provided for Azure AI via {api_key_env_var}")
        return AzureAIAgent(
            model_name=model_name,
            deployment_name=deployment_name,
            azure_api_key=api_key,
            azure_endpoint=endpoint
        )
    elif provider == "azure_anthropic":
        if not api_key:
            raise ValueError(f"API key not provided for Azure Anthropic via {api_key_env_var}")
        return AzureAnthropicAgent(
            model_name=model_name,
            deployment_name=deployment_name,
            azure_api_key=api_key,
            azure_endpoint=endpoint
        )
    elif provider == "google":
        if not api_key: 
            raise ValueError(f"API key not provided for Google AI via {api_key_env_var}")
        return GoogleAIAgent(model_name=model_name, api_key=api_key)
    elif provider == "baseten":
        if not api_key: 
            raise ValueError(f"API key not provided for Baseten via {api_key_env_var}")
        return BasetenAgent(model_name=model_name, api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {provider} for model {model_name}")
