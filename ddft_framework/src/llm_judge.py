"""
LLM Judge module - Uses a powerful LLM to evaluate the subject's responses.
Evaluates responses on three metrics: FAR (Factual Accuracy), SAS (Semantic Adherence), FC (Fluency/Clarity)
"""
import json
import re
import sys
import os
from typing import Dict, List, Optional

# Add src directory to path to allow sibling imports
sys.path.insert(0, os.path.dirname(__file__))

from agent import create_agent
from prompts import get_judge_system_prompt, get_judge_user_prompt
from retry_handler import RetryConfig, call_with_retry


def print_debug_panel(subject_model: str, turn: str, compression: float, question: str, 
                      response: str, evaluation: Dict = None):
    """
    Simple debug panel printer for evaluation results.
    """
    print(f"\n{'='*80}")
    print(f"Model: {subject_model:30} | {turn}")
    print(f"Compression: {compression:.2f}")
    print(f"Question: {question[:60]}...")
    print(f"Response: {response[:80]}...")
    if evaluation:
        print(f"Scores: FAR={evaluation.get('FAR')}, SAS={evaluation.get('SAS')}, FC={evaluation.get('FC')}")
    print(f"{'='*80}\n")


class LLMJudge:
    """
    A class to represent the LLM Judge that evaluates a subject's response.
    
    Metrics:
    - FAR (Factual Accuracy Rate): 0.0-1.0, higher is better
    - SAS (Semantic Adherence Score): 0.0-1.0, higher is better  
    - FC (Fluency/Clarity): 0.0-1.0, higher is better
    """
    def __init__(self, judge_model_name: str, judge_deployment_name: str, api_keys: dict):
        """
        Initialize the LLM Judge.
        
        Args:
            judge_model_name: Name of the judge model (e.g., 'gpt-4.1')
            judge_deployment_name: Deployment name (usually same as model_name for Azure)
            api_keys: Dict of API credentials
        """
        # The judge model is always gpt-4.1, which is an Azure OpenAI model
        judge_config = {
            "model_name": judge_model_name,
            "deployment_name": judge_deployment_name,
            "provider": "azure_openai",
            "api_key_env_var": "AZURE_API_KEY",
            "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT"
        }
        self.judge_agent = create_agent(
            subject_config=judge_config,
            api_keys=api_keys
        )
        self.judge_model_name = judge_model_name

    def _parse_judge_response(self, response_text: str) -> Dict:
        """
        Parses the JSON response from the judge LLM.
        Handles cases where the response is embedded in a code block.
        
        Expected JSON format:
        {
            "FAR": 0.0-1.0,
            "SAS": 0.0-1.0,
            "FC": 0.0-1.0
        }
        """
        print(f"DEBUG: Parsing judge response: {response_text[:200]}...")
        try:
            # Regex to find JSON within ```json ... ```
            match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
                parsed = json.loads(json_str)
                print(f"DEBUG: Parsed JSON: {parsed}")
                return parsed
            else:
                # Fallback for responses that might just be the JSON string
                return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"ERROR: Could not decode JSON from judge response: {e}")
            print(f"Raw response was: {response_text}")
            return {"error": "JSON_DECODE_ERROR", "raw_response": response_text}
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during parsing: {e}")
            return {"error": "UNEXPECTED_PARSING_ERROR", "raw_response": response_text}

    def evaluate_response(self, subject_response: str, turn_number: int, question_asked: str,
                          conversation_history: List[Dict], compression_level: float,
                          fictional_name: Optional[str] = None) -> Dict:
        """
        Uses the judge LLM to evaluate the subject's response and returns the scores.
        
        Args:
            subject_response: The response text from the subject model
            turn_number: Which turn of DDFT (1-5)
            question_asked: The question that prompted this response
            conversation_history: Full conversation up to this point
            compression_level: Compression level (0.0-1.0)
            fictional_name: If this is Turn 4, the fictional expert name
            
        Returns:
            Dict with FAR, SAS, FC scores (0.0-1.0) and metadata
        """
        system_prompt = get_judge_system_prompt()
        user_prompt = get_judge_user_prompt(
            subject_response=subject_response,
            turn_number=turn_number,
            question_asked=question_asked,
            conversation_history=conversation_history,
            fictional_name=fictional_name,
            compression_level=compression_level
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        raw_judge_response = self.judge_agent.chat(messages)
        print(f"DEBUG: Judge raw response: {raw_judge_response[:200] if raw_judge_response else 'None'}...")

        if raw_judge_response is None:
            return {
                "FAR": None, "SAS": None, "FC": None,
                "raw_judge_response": "API_ERROR",
                "parse_error": "Judge agent failed to respond."
            }

        parsed_response = self._parse_judge_response(raw_judge_response)

        if "error" in parsed_response:
            return {
                "FAR": None, "SAS": None, "FC": None,
                "raw_judge_response": parsed_response.get("raw_response"),
                "parse_error": parsed_response.get("error")
            }

        far_score = parsed_response.get("FAR")
        sas_score = parsed_response.get("SAS")
        fc_score = parsed_response.get("FC")
        
        print(f"DEBUG: Extracted scores - FAR: {far_score}, SAS: {sas_score}, FC: {fc_score}")

        print_debug_panel(
            subject_model=self.judge_model_name,
            turn=f"Judge Eval of Turn {turn_number}",
            compression=compression_level,
            question=question_asked,
            response=subject_response,
            evaluation={
                "FAR": far_score,
                "SAS": sas_score,
                "FC": fc_score
            }
        )
        
        print(f"✓ Turn {turn_number}: FAR={far_score}, SAS={sas_score}, FC={fc_score}")

        return {
            "FAR": far_score,
            "SAS": sas_score,
            "FC": fc_score,
            "raw_judge_response": raw_judge_response
        }