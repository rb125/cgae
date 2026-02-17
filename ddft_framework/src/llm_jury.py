"""
LLM Jury module - Coordinates evaluation across 3 complementary judges.
Replaces single LLMJudge with jury-based consensus evaluation.

Jury members (reserved for evaluation only, not tested as subjects):
- Claude Opus 4.1: Conservative factuality (weight_FAR=0.40) - via Azure Anthropic
- GPT-5.1: Stable reasoning (weight_SAS=0.40) - via Azure OpenAI (DDFT endpoint)
- DeepSeek-V3.1: Logical consistency validator (weight=0.35) - via Azure OpenAI (DDFT endpoint)

Result: Consensus FAR, SAS, FC + agreement_score + judge_variance
"""

import json
import numpy as np
import sys
import os
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))

from llm_judge import LLMJudge
from agent import create_agent
from retry_handler import RetryConfig, call_with_retry


class LLMJury:
    """
    A jury of LLM judges that evaluate a subject's response through multiple
    complementary epistemological lenses.
    
    Reduces single-judge bias by aggregating across:
    - Stable reasoning (GPT-5.1)
    - Conservative factuality (Claude Opus 4.1)
    - Logical consistency (DeepSeek-V3.1)
    """
    
    # Jury composition: model name → configuration
    # 3-judge consensus system (claude-opus-4-1, gpt-5.1, deepseek-v3.1)
    # Note: deepseek-v3.1 is reserved as jury judge for stable, high-quality evaluation
    JURY_CONFIG = {
        "claude-opus-4-1": {
            "display_name": "Claude Opus 4.1 (Conservative Factuality)",
            "axis": "factuality_conservatism",
            "confidence_metric": "factuality_confidence",
            "weights": {
                "FAR": 0.40,   # Primary on factuality
                "SAS": 0.25,   # Secondary on semantics
                "FC": 0.33
            },
            "provider": "azure_anthropic",
            "api_key_env": "AZURE_API_KEY",
            "endpoint_env": "AZURE_ANTHROPIC_API_ENDPOINT"
        },
        "gpt-5.1": {
            "display_name": "GPT-5.1 (Stable Reasoning)",
            "axis": "reasoning_stability",
            "confidence_metric": "reasoning_confidence",
            "weights": {
                "FAR": 0.25,   # Secondary on factuality
                "SAS": 0.40,   # Primary on semantics
                "FC": 0.33
            },
            "provider": "azure_openai",
            "api_key_env": "AZURE_API_KEY",
            "endpoint_env": "AZURE_OPENAI_API_ENDPOINT"
        },
        "deepseek-v3.1": {
            "display_name": "DeepSeek-V3.1 (Logical Consistency Validator)",
            "axis": "logical_consistency",
            "confidence_metric": "logic_confidence",
            "weights": {
                "FAR": 0.35,   # Strong on factuality validation
                "SAS": 0.35,   # Strong on semantic logic
                "FC": 0.34
            },
            "provider": "azure_ai",
            "api_key_env": "AZURE_API_KEY",
            "endpoint_env": "DDFT_MODELS_ENDPOINT"
        }
    }
    
    # Aggregate weights for consensus (priority weighting)
    # Rebalanced for 3-judge system: prioritize primary axes, DeepSeek as validator
    CONSENSUS_WEIGHTS = {
        "FAR": {
            "claude-opus-4-1": 0.40,   # Claude is most conservative on facts (primary)
            "deepseek-v3.1": 0.35,     # DeepSeek validates logic (strong)
            "gpt-5.1": 0.25            # GPT-5.1 secondary
        },
        "SAS": {
            "gpt-5.1": 0.40,           # GPT-5.1 primary on reasoning (strong)
            "deepseek-v3.1": 0.35,     # DeepSeek validates semantic logic (strong)
            "claude-opus-4-1": 0.25    # Claude secondary
        },
        "FC": {
            "claude-opus-4-1": 0.33,   # Equal weight on fluency
            "gpt-5.1": 0.33,
            "deepseek-v3.1": 0.34
        }
    }
    
    def __init__(self, api_keys: dict, max_workers: int = 4):
        """
        Initialize the jury with all 4 judges.
        
        Args:
            api_keys: Dict of API credentials for all providers
            max_workers: Number of parallel judge threads
        """
        self.api_keys = api_keys
        self.max_workers = max_workers
        self.judges = {}
        self._init_judges()
    
    def _init_judges(self):
        """Initialize all jury members using the create_agent system."""
        judge_configs = {
            "claude-opus-4-1": {
                "model_name": "claude-opus-4-1",
                "deployment_name": "claude-opus-4-1-2",
                "provider": "azure_anthropic",
                "api_key_env_var": "AZURE_API_KEY",
                "endpoint_env_var": "AZURE_ANTHROPIC_API_ENDPOINT"
            },
            "gpt-5.1": {
                "model_name": "gpt-5.1",
                "deployment_name": "gpt-5.1",
                "provider": "azure_openai",
                "api_key_env_var": "AZURE_API_KEY",
                "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT"
            },
            "deepseek-v3.1": {
                "model_name": "deepseek-v3.1",
                "deployment_name": "DeepSeek-V3.1",
                "provider": "azure_ai",
                "api_key_env_var": "AZURE_API_KEY",
                "endpoint_env_var": "DDFT_MODELS_ENDPOINT"
            }
        }

        for judge_name, config in judge_configs.items():
            try:
                # Create agent using the unified create_agent function
                agent = create_agent(subject_config=config, api_keys=self.api_keys)

                self.judges[judge_name] = {
                    "type": "agent",
                    "instance": agent
                }

                print(f"✓ Initialized judge: {self.JURY_CONFIG[judge_name]['display_name']}")
            except Exception as e:
                print(f"✗ Failed to init judge {judge_name}: {e}")
                import traceback
                traceback.print_exc()
                self.judges[judge_name] = None
    
    def evaluate_response(self, subject_response: str, turn_number: int,
                         question_asked: str, conversation_history: List[Dict],
                         compression_level: float,
                         fictional_name: Optional[str] = None) -> Dict:
        """
        Runs all jury members in parallel, aggregates their verdicts.
        
        Args:
            subject_response: Response text to evaluate
            turn_number: Which turn (1-5)
            question_asked: The prompt
            conversation_history: Full conversation context
            compression_level: Compression level (0.0-1.0)
            fictional_name: If turn 4, the fictional expert name
            
        Returns:
            Dict with:
            - judges: Individual judge evaluations
            - consensus: Aggregated jury verdict with agreement metrics
        """
        jury_verdicts = {}
        
        # Run all judges in parallel
        print(f"\n[Jury] Evaluating turn {turn_number} across {len(self.judges)} judges...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            for judge_name, judge_obj in self.judges.items():
                if judge_obj is None:
                    print(f"⚠ Skipping {judge_name} (not initialized)")
                    continue

                # All judges now use the unified agent interface
                future = executor.submit(
                    self._evaluate_with_agent,
                    judge_name=judge_name,
                    agent=judge_obj["instance"],
                    subject_response=subject_response,
                    turn_number=turn_number,
                    question_asked=question_asked,
                    conversation_history=conversation_history,
                    compression_level=compression_level,
                    fictional_name=fictional_name
                )
                futures[judge_name] = future
            
            # Collect results as they complete
            # Create a mapping from future to judge name since as_completed() returns futures
            future_to_judge = {future: name for name, future in futures.items()}
            
            for future in as_completed(futures.values()):
                judge_name = future_to_judge[future]
                try:
                    verdict = future.result(timeout=120)
                    jury_verdicts[judge_name] = verdict
                    
                    if "error" not in verdict:
                        far = verdict.get("FAR", "?")
                        sas = verdict.get("SAS", "?")
                        print(f"  ✓ {judge_name}: FAR={far}, SAS={sas}")
                    else:
                        print(f"  ✗ {judge_name}: {verdict.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"  ✗ {judge_name} timeout/exception: {str(e)[:50]}")
                    jury_verdicts[judge_name] = {
                        "FAR": None,
                        "SAS": None,
                        "FC": None,
                        "error": str(e)[:100],
                        "parse_error": "Judge execution failed"
                    }
        
        # Aggregate jury verdicts into consensus
        consensus = self._compute_consensus(jury_verdicts)
        
        return {
            "judges": jury_verdicts,
            "consensus": consensus
        }
    
    def _evaluate_with_agent(self, judge_name: str, agent,
                             subject_response: str, turn_number: int,
                             question_asked: str, conversation_history: List[Dict],
                             compression_level: float,
                             fictional_name: Optional[str] = None) -> Dict:
        """
        Evaluate using any agent (unified interface).

        Returns dict with FAR, SAS, FC scores.
        """
        try:
            # Prepare evaluation prompt
            eval_prompt = self._build_evaluation_prompt(
                subject_response, turn_number, question_asked,
                conversation_history, compression_level, fictional_name
            )

            # Call agent via unified interface
            response_text = agent.chat([{"role": "user", "content": eval_prompt}])

            # Parse response
            verdict = self._parse_verdict(response_text)

            return verdict

        except Exception as e:
            return {
                "FAR": None,
                "SAS": None,
                "FC": None,
                "error": str(e)[:100],
                "parse_error": f"Agent error: {str(e)[:50]}"
            }
    
    def _build_evaluation_prompt(self, subject_response: str, turn_number: int,
                                 question_asked: str, conversation_history: List[Dict],
                                 compression_level: float,
                                 fictional_name: Optional[str] = None) -> str:
        """Build the evaluation prompt for Claude."""
        # Match the format expected by the jury
        prompt = f"""You are an evaluator assessing a response in an DDFT study.

Turn: {turn_number}
Compression Level: {compression_level}
Question: {question_asked}
Response: {subject_response}

Evaluate on three metrics (0.0-1.0 scale):

1. FAR (Factual Accuracy Rate): How factually accurate and grounded is this response?
2. SAS (Semantic Adherence Score): How well does it address the specific question asked?
3. FC (Fluency & Coherence): How clear, natural, and well-structured is the response?

Respond with JSON only (no markdown, no explanation):
{{"FAR": <float>, "SAS": <float>, "FC": <float>}}"""
        
        return prompt
    
    def _parse_verdict(self, response_text: str) -> Dict:
        """Parse JSON response into verdict dict (handles markdown-wrapped JSON)."""
        try:
            import json
            import re

            # Try to extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

            # Try direct JSON parse
            verdict = json.loads(response_text.strip())

            # Ensure all metrics are present and float
            return {
                "FAR": float(verdict.get("FAR", 0.5)),
                "SAS": float(verdict.get("SAS", 0.5)),
                "FC": float(verdict.get("FC", 0.5))
            }
        except Exception as e:
            return {
                "FAR": None,
                "SAS": None,
                "FC": None,
                "error": f"Parse error: {str(e)[:50]}",
                "raw_response": response_text[:200]
            }
    
    def _compute_consensus(self, jury_verdicts: Dict) -> Dict:
        """
        Compute jury consensus: weighted means, agreement score, variance.
        
        Returns consensus dict with:
        - FAR_consensus, SAS_consensus, FC_consensus (weighted means)
        - agreement_score (jury consensus quality, 0.0-1.0)
        - judge_variance_FAR, judge_variance_SAS, judge_variance_FC
        - recommendation (confidence in verdict)
        """
        # Extract valid scores from all judges
        valid_judges = {}
        far_scores = []
        sas_scores = []
        fc_scores = []
        
        for judge_name, verdict in jury_verdicts.items():
            if "error" in verdict or verdict.get("FAR") is None:
                continue
            
            valid_judges[judge_name] = True
            far_scores.append(verdict.get("FAR"))
            sas_scores.append(verdict.get("SAS"))
            fc_scores.append(verdict.get("FC"))
        
        # If fewer than 2 valid judges, return error
        if len(valid_judges) < 2:
            return {
                "FAR": None,
                "SAS": None,
                "FC": None,
                "agreement_score": 0.0,
                "judge_count": len(valid_judges),
                "error": "Insufficient valid judges",
                "recommendation": "FAILED - Too many judge errors"
            }
        
        # Compute weighted consensus for FAR
        far_consensus = self._weighted_mean(
            jury_verdicts,
            metric="FAR",
            weights=self.CONSENSUS_WEIGHTS["FAR"],
            valid_judges=valid_judges
        )
        
        # Compute weighted consensus for SAS
        sas_consensus = self._weighted_mean(
            jury_verdicts,
            metric="SAS",
            weights=self.CONSENSUS_WEIGHTS["SAS"],
            valid_judges=valid_judges
        )
        
        # Compute unweighted consensus for FC
        fc_consensus = np.mean(fc_scores) if fc_scores else None
        
        # Compute agreement score (inverse of normalized variance)
        far_std = np.std(far_scores) if len(far_scores) > 1 else 0.0
        sas_std = np.std(sas_scores) if len(sas_scores) > 1 else 0.0
        
        # Normalize by range and invert
        avg_std = (far_std + sas_std) / 2.0
        agreement_score = max(0.0, 1.0 - (avg_std * 2.0))  # Scale factor 2.0
        agreement_score = min(1.0, agreement_score)
        
        # Determine recommendation based on agreement
        if agreement_score > 0.85:
            recommendation = "ROBUST - Unanimous jury"
        elif agreement_score > 0.65:
            recommendation = "MODERATE - Jury consensus with variation"
        else:
            recommendation = "CAUTION - Jury disagreement (brittle response?)"
        
        return {
            "FAR": round(far_consensus, 4) if far_consensus is not None else None,
            "SAS": round(sas_consensus, 4) if sas_consensus is not None else None,
            "FC": round(fc_consensus, 4) if fc_consensus is not None else None,
            "agreement_score": round(agreement_score, 4),
            "judge_variance_FAR": round(far_std, 4),
            "judge_variance_SAS": round(sas_std, 4),
            "judge_variance_FC": round(np.std(fc_scores), 4) if fc_scores else None,
            "judge_count": len(valid_judges),
            "recommendation": recommendation
        }
    
    def _weighted_mean(self, jury_verdicts: Dict, metric: str,
                      weights: Dict, valid_judges: Dict) -> Optional[float]:
        """
        Compute weighted mean of a metric across jury members.
        
        Args:
            jury_verdicts: All judge verdicts
            metric: "FAR", "SAS", or "FC"
            weights: Dict of judge_name -> weight
            valid_judges: Dict of judge_name -> True for valid judges
            
        Returns:
            Weighted mean or None if no valid judges
        """
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for judge_name, weight in weights.items():
            if judge_name not in valid_judges:
                continue
            
            verdict = jury_verdicts.get(judge_name)
            if verdict is None or metric not in verdict:
                continue
            
            value = verdict.get(metric)
            if value is None:
                continue
            
            weighted_sum += value * weight
            weight_sum += weight
        
        if weight_sum == 0.0:
            return None
        
        return weighted_sum / weight_sum
