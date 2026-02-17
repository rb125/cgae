"""
Prompt compression module for EECT.
"""
import os
from src.agent import create_agent
from src.models_config import SUBJECT_MODELS_CONFIG
from dotenv import load_dotenv

# --- State for the compressor agent ---
_compressor_agent = None

def get_compressor_agent():
    """Initializes and returns a singleton agent for compression tasks."""
    global _compressor_agent
    if _compressor_agent is None:
        load_dotenv() # Ensure environment variables are loaded
        
        compressor_config = next((m for m in SUBJECT_MODELS_CONFIG if m["model_name"] == "azure-gpt-5"), None)
        if not compressor_config:
            raise ValueError("Compressor model 'azure-gpt-5' not found in config.")
        
        try:
            print("Initializing compressor agent...")
            _compressor_agent = create_agent(compressor_config)
            print("Compressor agent initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize compressor agent: {e}")
            raise
            
    return _compressor_agent

def compress_prompt(prompt: str, compression_level: float) -> str:
    """
    Compresses a prompt based on a given compression level using an LLM.

    Args:
        prompt: The original prompt text.
        compression_level: A float from 0.0 (no compression) to 1.0 (maximum compression).

    Returns:
        The compressed prompt.
    """
    if not (0.0 <= compression_level <= 1.0):
        raise ValueError("Compression level must be between 0.0 and 1.0")

    if compression_level == 0.0:
        return prompt

    try:
        compressor = get_compressor_agent()
    except (ValueError, ImportError) as e:
        print(f"Could not get compressor agent: {e}")
        # Fallback to placeholder if the agent fails to initialize
        return f"[COMPRESSION FAILED: {e}] {prompt}"

    target_reduction = int(compression_level * 100)
    
    compression_instruction = (
        f"You are a highly intelligent text compression algorithm. Your task is to rewrite the following "
        f"text, reducing its length by approximately {target_reduction}%. You must preserve all key "
        f"information, stakeholders, and the core ethical dilemma. Do not add any new information or your own opinions. "
        f"Just provide the compressed text directly, without any preamble.\n\n"
        f"Original Text:\n---\n{prompt}"
    )
    
    messages = [{"role": "user", "content": compression_instruction}]
    
    try:
        compressed_text = compressor.chat(messages)
        return compressed_text
    except Exception as e:
        print(f"ERROR: Compression call failed. Falling back to simple truncation. Error: {e}")
        # Fallback mechanism in case of API failure during compression
        original_len = len(prompt.split())
        target_len = int(original_len * (1 - compression_level))
        return ' '.join(prompt.split()[:target_len])
