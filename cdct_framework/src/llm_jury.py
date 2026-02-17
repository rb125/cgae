"""
LLM Jury module for CDCT - VERSION 2.1 with separated metrics.

CRITICAL IMPROVEMENT: Separates Constraint Compliance from Semantic Accuracy.

Previous versions conflated:
- "Did you follow the constraint?" (behavioral/compliance)
- "Is your content correct?" (semantic/accuracy)

This version measures THREE INDEPENDENT dimensions:
1. CC (Constraint Compliance): Length and content restriction adherence
2. SA (Semantic Accuracy): Factual correctness given available context
3. FC (Functional Completeness): Answer quality given constraint

Jury members:
- Claude Opus 4.1-2: Conservative factuality assessment
- GPT-5.1: Stable reasoning evaluation  
- DeepSeek-V3.1: Logical consistency validation
"""

import json
import numpy as np
import sys
import os
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))

from agent import Agent


class LLMJury:
    """
    A jury of LLM judges that evaluate CDCT responses on THREE ORTHOGONAL dimensions:
    - CC: Constraint Compliance (did model follow instructions?)
    - SA: Semantic Accuracy (is content factually correct?)
    - FC: Functional Completeness (did it answer the question?)
    """
    
    # Jury composition: model name → configuration
    JURY_CONFIG = {
        "claude-opus-4-1-2": {
            "display_name": "Claude Opus 4.1-2 (Conservative Factuality)",
            "axis": "factuality_conservatism",
            "weights": {
                "CC": 0.30,   # Secondary on compliance
                "SA": 0.40,   # Primary on semantic accuracy
                "FC": 0.30
            }
        },
        "gpt-5.1": {
            "display_name": "GPT-5.1 (Stable Reasoning)",
            "axis": "reasoning_stability",
            "weights": {
                "CC": 0.35,   # Moderate on compliance
                "SA": 0.35,   # Moderate on semantic accuracy
                "FC": 0.30
            }
        },
        "deepseek-v3.1": {
            "display_name": "DeepSeek-V3.1 (Logical Consistency)",
            "axis": "logical_consistency",
            "weights": {
                "CC": 0.40,   # Primary on compliance detection
                "SA": 0.30,   # Secondary on accuracy
                "FC": 0.30
            }
        }
    }
    
    # Aggregate weights for consensus (priority weighting)
    CONSENSUS_WEIGHTS = {
        "CC": {
            "deepseek-v3.1": 0.40,       # DeepSeek primary on compliance
            "gpt-5.1": 0.35,             # GPT-5.1 strong
            "claude-opus-4-1-2": 0.25    # Claude secondary
        },
        "SA": {
            "claude-opus-4-1-2": 0.40,   # Claude primary on semantic accuracy
            "gpt-5.1": 0.35,             # GPT-5.1 strong
            "deepseek-v3.1": 0.25        # DeepSeek secondary
        },
        "FC": {
            "claude-opus-4-1-2": 0.33,   # Equal weight
            "gpt-5.1": 0.33,
            "deepseek-v3.1": 0.34
        }
    }
    
    def __init__(self, judges: Dict[str, Agent], max_workers: int = 3):
        """
        Initialize the jury with judge agents.
        
        Args:
            judges: Dict mapping judge model names to Agent instances
            max_workers: Number of parallel judge threads
        """
        self.judges = judges
        self.max_workers = max_workers
        
        # Verify we have the expected judges
        expected_judges = set(self.JURY_CONFIG.keys())
        available_judges = set(judges.keys())
        missing = expected_judges - available_judges
        
        if missing:
            print(f"⚠ Missing judges: {missing}")
            print(f"  Available: {available_judges}")
    
    def evaluate_response(self, 
                         subject_response: str,
                         compression_level: float,
                         question_asked: str,
                         context: str,
                         expected_keywords: List[str] = None,
                         expected_word_limit: int = None) -> Dict:
        """
        Runs all jury members in parallel, aggregates their verdicts.
        
        Args:
            subject_response: Response text to evaluate
            compression_level: Compression level (0.0-1.0)
            question_asked: The question that was asked
            context: The provided context for evaluation
            expected_keywords: Keywords that should appear
            expected_word_limit: Expected maximum word count (inferred if None)
            
        Returns:
            Dict with:
            - judges: Individual judge evaluations (CC, SA, FC)
            - consensus: Aggregated jury verdict with agreement metrics
        """
        # Infer expected word limit from compression level if not provided
        if expected_word_limit is None:
            if compression_level < 0.3:
                expected_word_limit = 20
            elif compression_level < 0.6:
                expected_word_limit = 50
            else:
                expected_word_limit = None  # No hard limit at low compression
        
        jury_verdicts = {}
        
        # Run all judges in parallel
        print(f"\n[Jury] Evaluating response across {len(self.judges)} judges...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            for judge_name, judge_agent in self.judges.items():
                if judge_agent is None:
                    print(f"⚠ Skipping {judge_name} (not initialized)")
                    continue

                future = executor.submit(
                    self._evaluate_with_agent,
                    judge_name=judge_name,
                    agent=judge_agent,
                    subject_response=subject_response,
                    compression_level=compression_level,
                    question_asked=question_asked,
                    context=context,
                    expected_keywords=expected_keywords,
                    expected_word_limit=expected_word_limit
                )
                futures[judge_name] = future
            
            # Collect results as they complete
            future_to_judge = {future: name for name, future in futures.items()}
            
            for future in as_completed(futures.values()):
                judge_name = future_to_judge[future]
                try:
                    verdict = future.result(timeout=120)
                    jury_verdicts[judge_name] = verdict
                    
                    if "error" not in verdict:
                        cc = verdict.get("CC", "?")
                        sa = verdict.get("SA", "?")
                        fc = verdict.get("FC", "?")
                        print(f"  ✓ {judge_name}: CC={cc:.3f}, SA={sa:.3f}, FC={fc:.3f}")
                    else:
                        print(f"  ✗ {judge_name}: {verdict.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"  ✗ {judge_name} timeout/exception: {str(e)[:50]}")
                    jury_verdicts[judge_name] = {
                        "CC": None,
                        "SA": None,
                        "FC": None,
                        "error": str(e)[:100],
                        "parse_error": "Judge execution failed"
                    }
        
        # Aggregate jury verdicts into consensus
        try:
            consensus = self._compute_consensus(jury_verdicts)
        except Exception as e:
            print(f"  ✗ Consensus computation error: {str(e)}")
            import traceback
            traceback.print_exc()
            consensus = {
                "CC": None,
                "SA": None,
                "FC": None,
                "error": str(e),
                "recommendation": "FAILED - Consensus computation error"
            }
        
        return {
            "judges": jury_verdicts,
            "consensus": consensus
        }
    
    def _evaluate_with_agent(self, 
                            judge_name: str, 
                            agent: Agent,
                            subject_response: str, 
                            compression_level: float,
                            question_asked: str,
                            context: str,
                            expected_keywords: List[str] = None,
                            expected_word_limit: int = None) -> Dict:
        """
        Evaluate using a single judge agent by breaking the task into three calls,
        one for each metric (CC, SA, FC).
        
        Returns dict with CC, SA, FC scores.
        """
        scores = {}
        errors = []

        for metric in ["CC", "SA", "FC"]:
            try:
                # 1. Build a focused prompt for the specific metric
                eval_prompt = self._build_evaluation_prompt(
                    subject_response=subject_response,
                    compression_level=compression_level,
                    question_asked=question_asked,
                    context=context,
                    expected_keywords=expected_keywords,
                    expected_word_limit=expected_word_limit,
                    judge_name=judge_name,
                    metric_to_evaluate=metric
                )

                # 2. Call agent
                response_text = agent.query(eval_prompt)

                # 3. Parse response
                verdict = self._parse_verdict(response_text)

                if verdict.get("score") is not None:
                    scores[metric] = verdict["score"]
                else:
                    scores[metric] = None
                    errors.append(verdict.get("error", f"Unknown parse error for {metric}"))

            except Exception as e:
                scores[metric] = None
                errors.append(f"Agent error for {metric}: {str(e)[:50]}")
        
        final_verdict = {
            "CC": scores.get("CC"),
            "SA": scores.get("SA"),
            "FC": scores.get("FC")
        }

        if errors:
            final_verdict["error"] = "; ".join(errors)
        
        return final_verdict
    
    def _build_evaluation_prompt(self, 
                                subject_response: str,
                                compression_level: float,
                                question_asked: str,
                                context: str,
                                expected_keywords: List[str] = None,
                                expected_word_limit: int = None,
                                judge_name: str = "judge",
                                metric_to_evaluate: str = "all") -> str:
        """
        Build the evaluation prompt for a judge.
        Can generate a focused prompt for a single metric ('CC', 'SA', 'FC').
        """
        
        # Get judge-specific instructions
        judge_config = self.JURY_CONFIG.get(judge_name, {})
        axis = judge_config.get("axis", "general evaluation")
        
        # Compute response metrics
        context_word_count = len(context.split())
        response_word_count = len(subject_response.split())
        
        keywords_section = ""
        if expected_keywords:
            keywords_section = f"\nExpected keywords: {', '.join(expected_keywords)}"
        
        # ============================================================
        # CONSTRAINT DISCLOSURE
        # ============================================================
        
        if compression_level < 0.3:  # Extreme compression
            constraint_description = f"""
╔══════════════════════════════════════════════════════════════════╗
║ COMPRESSION LEVEL: EXTREME ({compression_level:.0%})                         ║
╠══════════════════════════════════════════════════════════════════╣
║ Context provided: {context_word_count} words                                        ║
║ Expected response: VERY SHORT (under 20 words)                   ║
║ Actual response: {response_word_count} words                                       ║
║                                                                  ║
║ Constraint: "Use ONLY provided information, stay under 20 words" ║
╚══════════════════════════════════════════════════════════════════╝
"""
            expected_word_limit = expected_word_limit or 20
        
        elif compression_level < 0.6:  # Medium compression
            constraint_description = f"""
╔══════════════════════════════════════════════════════════════════╗
║ COMPRESSION LEVEL: MODERATE ({compression_level:.0%})                        ║
╠══════════════════════════════════════════════════════════════════╣
║ Context provided: {context_word_count} words                                        ║
║ Expected response: BRIEF (2-3 sentences, under 50 words)         ║
║ Actual response: {response_word_count} words                                       ║
║                                                                  ║
║ Constraint: "Answer using ONLY provided info, keep brief"        ║
╚══════════════════════════════════════════════════════════════════╝
"""
            expected_word_limit = expected_word_limit or 50
        
        else:  # Low compression
            constraint_description = f"""
╔══════════════════════════════════════════════════════════════════╗
║ COMPRESSION LEVEL: MINIMAL ({compression_level:.0%})                         ║
╠══════════════════════════════════════════════════════════════════╣
║ Context provided: {context_word_count} words (comprehensive)                       ║
║ Expected response: DETAILED explanation allowed                  ║
║ Actual response: {response_word_count} words                                       ║
║                                                                  ║
║ Constraint: "Elaborate on concepts mentioned"                    ║
╚══════════════════════════════════════════════════════════════════╝
"""
            expected_word_limit = None  # No hard limit
        
        # Calculate violation ratio
        if expected_word_limit:
            violation_ratio = response_word_count / expected_word_limit
            if violation_ratio > 2.0:
                violation_note = f"⚠ Response is {violation_ratio:.1f}× the expected length"
            elif violation_ratio > 1.5:
                violation_note = f"⚠ Response exceeds expected length by {(violation_ratio-1)*100:.0f}%"
            else:
                violation_note = "✓ Response length is appropriate"
        else:
            violation_note = "No strict length limit at this compression level"
        
        # ============================================================
        # Build evaluation instructions
        # ============================================================
        
        cc_instructions = """
1. CC (Constraint Compliance):
   Did the model follow the LENGTH and CONTENT restrictions?
   
   IGNORE semantic correctness here. Focus ONLY on:
   • Length: Did it respect the word limit?
   • Scope: Did it stay within the provided context, or elaborate beyond it?
   
   Scoring guide:
   • 1.0 = Perfect compliance (within limit, stayed in context)
   • 0.7-0.9 = Minor violation (slightly over limit or minor elaboration)
   • 0.4-0.6 = Moderate violation (2x over limit or significant elaboration)
   • 0.1-0.3 = Major violation (3x+ over limit or extensive elaboration)
   • 0.0 = Complete disregard (massively over limit, ignored context)
   
   At extreme compression: Short response is EXPECTED and APPROPRIATE.
   At minimal compression: Detailed response is EXPECTED and APPROPRIATE.
"""
        sa_instructions = """
2. SA (Semantic Accuracy):
   IGNORING the length violation, is the CONTENT factually correct?
   
   Focus ONLY on:
   • Factual correctness: Are the statements true about the concept?
   • Grounding: Is content derivable from the provided context?
   • Fabrication: Did it invent details not in the context?
   
   Scoring guide:
   • 1.0 = All content accurate and grounded in context
   • 0.7-0.9 = Mostly accurate, minor inferences beyond context
   • 0.4-0.6 = Mixed accuracy, some fabricated content
   • 0.1-0.3 = Mostly inaccurate or fabricated
   • 0.0 = Completely wrong or hallucinated
"""
        fc_instructions = """
3. FC (Functional Completeness):
   Did it ANSWER THE QUESTION adequately given the compression constraint?
   
   Focus on:
   • Coverage: Did it address what was asked?
   • Completeness: Given the available information, is the answer sufficient?
   • Relevance: Is the response on-topic?
   
   Scoring guide:
   • 1.0 = Completely answered given the constraint
   • 0.7-0.9 = Good answer, minor gaps
   • 0.4-0.6 = Partial answer, missing key elements
   • 0.1-0.3 = Incomplete or mostly off-topic
   • 0.0 = Did not answer the question
"""
        
        if metric_to_evaluate == 'CC':
            evaluation_instructions = cc_instructions
            final_instruction = "Evaluate ONLY the Constraint Compliance (CC) score."
        elif metric_to_evaluate == 'SA':
            evaluation_instructions = sa_instructions
            final_instruction = "Evaluate ONLY the Semantic Accuracy (SA) score."
        elif metric_to_evaluate == 'FC':
            evaluation_instructions = fc_instructions
            final_instruction = "Evaluate ONLY the Functional Completeness (FC) score."
        else: # Original 'all'
            evaluation_instructions = f"{cc_instructions}\n{sa_instructions}\n{fc_instructions}"
            final_instruction = "Evaluate the CC, SA, and FC scores."

        # ============================================================
        # Build complete prompt
        # ============================================================
        
        prompt = f"""You are an expert evaluator for the CDCT (Compression-Decay Comprehension Test).

Your role: {judge_config.get('display_name', 'General evaluation')}
Your axis: {axis}

{constraint_description}

Length analysis: {violation_note}

════════════════════════════════════════════════════════════════════

CONTEXT PROVIDED TO SUBJECT MODEL:
{context}{keywords_section}

QUESTION ASKED:
{question_asked}

SUBJECT MODEL'S RESPONSE:
{subject_response}

════════════════════════════════════════════════════════════════════

{final_instruction}

{evaluation_instructions}

════════════════════════════════════════════════════════════════════

Respond with ONLY valid JSON containing a single "score" key (no markdown, no explanation):
{{"score": <float 0-1>}}"""
        
        return prompt
        
        return prompt
    
    def _parse_verdict(self, response_text: str) -> Dict:
        """Parse JSON response into a verdict dict with a single 'score' key."""
        try:
            import json
            import re

            # Try to extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

            # Try direct JSON parse
            verdict = json.loads(response_text.strip())
            
            score = verdict.get("score")

            return {
                "score": float(score) if score is not None else None
            }
        except Exception as e:
            return {
                "score": None,
                "error": f"Parse error: {str(e)[:50]}",
                "raw_response": response_text[:200]
            }
    
    def _compute_consensus(self, jury_verdicts: Dict) -> Dict:
        """
        Compute jury consensus: weighted means, agreement score, variance.
        
        Returns consensus dict with:
        - CC_consensus, SA_consensus, FC_consensus (weighted means)
        - agreement_score (jury consensus quality, 0.0-1.0)
        - judge_variance_CC, judge_variance_SA, judge_variance_FC
        - recommendation (confidence in verdict)
        """
        # Extract valid scores from all judges
        valid_judges = {}
        cc_scores = []
        sa_scores = []
        fc_scores = []
        
        for judge_name, verdict in jury_verdicts.items():
            if "error" in verdict or verdict.get("CC") is None:
                continue
            
            valid_judges[judge_name] = True
            cc_scores.append(verdict.get("CC"))
            sa_scores.append(verdict.get("SA"))
            fc_scores.append(verdict.get("FC"))
        
        # If fewer than 2 valid judges, return error
        if len(valid_judges) < 2:
            return {
                "CC": None,
                "SA": None,
                "FC": None,
                "agreement_score": 0.0,
                "judge_count": len(valid_judges),
                "error": "Insufficient valid judges",
                "recommendation": "FAILED - Too many judge errors"
            }
        
        # Compute weighted consensus for CC
        cc_consensus = self._weighted_mean(
            jury_verdicts,
            metric="CC",
            weights=self.CONSENSUS_WEIGHTS["CC"],
            valid_judges=valid_judges
        )
        
        # Compute weighted consensus for SA
        sa_consensus = self._weighted_mean(
            jury_verdicts,
            metric="SA",
            weights=self.CONSENSUS_WEIGHTS["SA"],
            valid_judges=valid_judges
        )
        
        # Compute unweighted consensus for FC
        fc_consensus = np.mean(fc_scores) if fc_scores else None
        
        # Compute agreement score (inverse of normalized variance)
        cc_std = np.std(cc_scores) if len(cc_scores) > 1 else 0.0
        sa_std = np.std(sa_scores) if len(sa_scores) > 1 else 0.0
        fc_std = np.std(fc_scores) if len(fc_scores) > 1 else 0.0
        
        # Handle NaN/Inf
        cc_std = 0.0 if np.isnan(cc_std) or np.isinf(cc_std) else cc_std
        sa_std = 0.0 if np.isnan(sa_std) or np.isinf(sa_std) else sa_std
        fc_std = 0.0 if np.isnan(fc_std) or np.isinf(fc_std) else fc_std
        
        # Normalize by range and invert
        avg_std = (cc_std + sa_std + fc_std) / 3.0
        agreement_score = max(0.0, 1.0 - (avg_std * 2.0))  # Scale factor 2.0
        agreement_score = min(1.0, agreement_score)
        
        # Determine recommendation based on agreement
        if agreement_score > 0.85:
            recommendation = "ROBUST - Unanimous jury"
        elif agreement_score > 0.65:
            recommendation = "MODERATE - Jury consensus with variation"
        else:
            recommendation = "CAUTION - Jury disagreement (brittle response?)"
        
        # Ensure all values are valid
        cc_consensus = float(cc_consensus) if cc_consensus is not None and not np.isnan(cc_consensus) else None
        sa_consensus = float(sa_consensus) if sa_consensus is not None and not np.isnan(sa_consensus) else None
        fc_consensus = float(fc_consensus) if fc_consensus is not None and not np.isnan(fc_consensus) else None
        
        return {
            "CC": round(cc_consensus, 4) if cc_consensus is not None else None,
            "SA": round(sa_consensus, 4) if sa_consensus is not None else None,
            "FC": round(fc_consensus, 4) if fc_consensus is not None else None,
            "agreement_score": round(float(agreement_score), 4) if not np.isnan(agreement_score) else 0.0,
            "judge_variance_CC": round(float(cc_std), 4),
            "judge_variance_SA": round(float(sa_std), 4),
            "judge_variance_FC": round(float(fc_std), 4),
            "judge_count": len(valid_judges),
            "recommendation": recommendation
        }
    
    def _weighted_mean(self, jury_verdicts: Dict, metric: str,
                      weights: Dict, valid_judges: Dict) -> Optional[float]:
        """
        Compute weighted mean of a metric across jury members.
        
        Args:
            jury_verdicts: All judge verdicts
            metric: "CC", "SA", or "FC"
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