"""
Cognitive Profiler - High-level API for DDFT evaluations as shown in paper.

Provides the streamlined interface demonstrated in the paper's Quick Start section:

    from ddft import CognitiveProfiler

    profiler = CognitiveProfiler(model="your-model")
    profile = profiler.run_complete_assessment(
        concepts=["Natural Selection", "Recursion"],
        compression_levels=[0.0, 0.25, 0.5, 0.75, 1.0]
    )

    print(f"CI Score: {profile.ci_score}")
    print(f"Phenotype: {profile.phenotype}")
    print(f"Danger Zone Rate: {profile.danger_zone_pct}%")
"""

import os
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
import glob

from agent import create_agent
from interviewer import InterviewerAgent, FabricationTrapGenerator
from compression import ConceptLoader
from llm_jury import LLMJury
from analyze_results import (
    calculate_highest_operable_compression,
    calculate_factual_consistency_gradient,
    calculate_decay_smoothness,
    calculate_model_calibration_accuracy,
    calculate_comprehension_integrity,
    classify_phenotype
)
import pandas as pd


@dataclass
class CognitiveProfile:
    """
    Results from a complete DDFT assessment.

    Attributes:
        model_name: Name of the model tested
        ci_score: Comprehension Integrity index (0.0-1.0)
        phenotype: Classification (Robust, Competent, Brittle)
        hoc: Hallucination Onset Compression
        fg: Fabrication Gradient
        decay_smoothness: Decay smoothness (R²)
        mca: Meta-Cognitive Awareness
        danger_zone_pct: Percentage of responses in danger zone
        num_evaluations: Total number of turn evaluations
        concepts_tested: List of concepts evaluated
        detailed_results: Full results dataframe
    """
    model_name: str
    ci_score: float
    phenotype: str
    hoc: float
    fg: float
    decay_smoothness: float
    mca: float
    danger_zone_pct: float
    num_evaluations: int
    concepts_tested: List[str]
    detailed_results: Optional[pd.DataFrame] = None


class CognitiveProfiler:
    """
    High-level API for conducting DDFT evaluations and generating cognitive profiles.

    This class orchestrates the complete DDFT pipeline:
    1. Load concepts and compress context
    2. Conduct five-turn interviews via interviewer agent
    3. Evaluate responses via three-judge jury
    4. Calculate metrics (HOC, FG, Decay, MCA, CI)
    5. Generate cognitive profile with phenotype classification
    """

    def __init__(
        self,
        model: str,
        api_keys: Optional[Dict] = None,
        interviewer_model: str = "gpt-5.1",
        concepts_dir: str = "concepts",
        results_dir: str = "results"
    ):
        """
        Initialize the Cognitive Profiler.

        Args:
            model: Subject model to evaluate (model name or config dict)
            api_keys: API credentials dict (uses env vars if None)
            interviewer_model: Model to use as interviewer (default: gpt-5.1)
            concepts_dir: Directory containing concept JSON files
            results_dir: Directory to save evaluation results
        """
        self.model_name = model if isinstance(model, str) else model.get("model_name")
        self.concepts_dir = concepts_dir
        self.results_dir = results_dir

        # Load API keys from environment if not provided
        if api_keys is None:
            api_keys = {
                "AZURE_API_KEY": os.getenv("AZURE_API_KEY"),
                "AZURE_OPENAI_API_ENDPOINT": os.getenv("AZURE_OPENAI_API_ENDPOINT"),
                "AZURE_ANTHROPIC_API_ENDPOINT": os.getenv("AZURE_ANTHROPIC_API_ENDPOINT"),
                "DDFT_MODELS_ENDPOINT": os.getenv("DDFT_MODELS_ENDPOINT")
            }

        self.api_keys = api_keys

        # Create results directory if it doesn't exist
        os.makedirs(results_dir, exist_ok=True)

        # Initialize components
        self.concept_loader = ConceptLoader(concepts_dir)

        # Create subject agent
        if isinstance(model, dict):
            subject_api_key_env_var = model.get("api_key_env_var", "AZURE_API_KEY")
            subject_endpoint_env_var = model.get("endpoint_env_var")
            subject_api_key = self.api_keys.get(subject_api_key_env_var)
            subject_endpoint = self.api_keys.get(subject_endpoint_env_var) if subject_endpoint_env_var else None

            self.subject_agent = create_agent(
                subject_config=model,
                api_keys=api_keys, # Still pass the dict for other lookups if needed
                resolved_api_key=subject_api_key,
                resolved_endpoint=subject_endpoint
            )
        else:
            # Simple model name - create default config
            self.subject_agent = self._create_agent_from_name(model, api_keys)

        # Create interviewer agent
        interviewer_config = {
            "model_name": interviewer_model,
            "deployment_name": interviewer_model,
            "provider": "azure_openai",
            "api_key_env_var": "AZURE_API_KEY",
            "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT"
        }
        interviewer_api_key = self.api_keys.get(interviewer_config["api_key_env_var"])
        interviewer_endpoint = self.api_keys.get(interviewer_config["endpoint_env_var"])
        interviewer_agent = create_agent(
            subject_config=interviewer_config,
            api_keys=api_keys,
            resolved_api_key=interviewer_api_key,
            resolved_endpoint=interviewer_endpoint
        )
        self.interviewer = InterviewerAgent(interviewer_agent)

        # Create jury
        self.jury = LLMJury(api_keys=api_keys, max_workers=4)

    def _create_agent_from_name(self, model_name: str, api_keys: Dict):
        """Create agent from simple model name."""
        # Default configuration - adjust based on model name
        config = {
            "model_name": model_name,
            "deployment_name": model_name,
            "provider": "azure_openai",  # Default provider
            "api_key_env_var": "AZURE_API_KEY",
            "endpoint_env_var": "AZURE_OPENAI_API_ENDPOINT"
        }
        # Resolve api_key and endpoint using the provided api_keys dict
        resolved_api_key = api_keys.get(config["api_key_env_var"])
        resolved_endpoint = api_keys.get(config["endpoint_env_var"])

        return create_agent(
            subject_config=config,
            api_keys=api_keys, # Still pass the dict for other lookups if needed
            resolved_api_key=resolved_api_key,
            resolved_endpoint=resolved_endpoint
        )

    def run_complete_assessment(
        self,
        concepts: List[str] = None,
        compression_levels: List[float] = None,
        save_results: bool = True
    ) -> CognitiveProfile:
        """
        Run complete DDFT assessment across concepts and compression levels.

        Args:
            concepts: List of concept names to test (uses all if None)
            compression_levels: Compression levels to test (uses standard 5 if None)
            save_results: Whether to save detailed results to JSON

        Returns:
            CognitiveProfile with CI score, phenotype, and detailed metrics
        """
        if compression_levels is None:
            compression_levels = [0.0, 0.25, 0.5, 0.75, 1.0]

        # Load concept files
        concept_files = self._get_concept_files(concepts)

        if not concept_files:
            raise ValueError(f"No concept files found in {self.concepts_dir}")

        print(f"\n{'='*70}")
        print(f"DDFT Cognitive Profiling: {self.model_name}")
        print(f"{'='*70}")
        print(f"Concepts: {len(concept_files)}")
        print(f"Compression levels: {compression_levels}")
        print(f"Total evaluations: {len(concept_files) * len(compression_levels) * 5} turns")
        print(f"{'='*70}\n")

        # Run evaluations
        all_results = []

        for concept_file in concept_files:
            concept_data = self.concept_loader.load_concept(concept_file)
            concept_name = concept_data["concept"]
            domain = concept_data["domain"]

            print(f"\nEvaluating concept: {concept_name} ({domain})")

            for compression_level in compression_levels:
                print(f"  Compression level: {compression_level:.2f}...", end=" ", flush=True)

                # Get compressed context
                compressed_context = self.concept_loader.get_compressed_context(
                    concept_data,
                    compression_level
                )

                # Conduct interview
                conversation_log, metadata = self.interviewer.conduct_interview(
                    subject_agent=self.subject_agent,
                    concept_name=concept_name,
                    domain=domain,
                    compressed_context=compressed_context,
                    compression_level=compression_level
                )

                # Evaluate each turn with jury
                evaluated_conversation = []
                for i, msg in enumerate(conversation_log):
                    if msg["role"] == "assistant":
                        turn_number = (len(evaluated_conversation) + 1) // 2
                        question_asked = conversation_log[i - 1]["content"]

                        # Determine if this is Turn 4 (fabrication trap)
                        fictional_name = None
                        if turn_number == 4:
                            fictional_name = metadata["fabrication_trap"]["expert_name"]

                        # Jury evaluation
                        jury_result = self.jury.evaluate_response(
                            subject_response=msg["content"],
                            turn_number=turn_number,
                            question_asked=question_asked,
                            conversation_history=evaluated_conversation,
                            compression_level=compression_level,
                            fictional_name=fictional_name
                        )

                        msg["evaluation"] = jury_result
                        evaluated_conversation.append(msg)
                    else:
                        evaluated_conversation.append(msg)

                # Save result
                result = {
                    "subject_model": self.model_name,
                    "interviewer_model": "gpt-5.1",
                    "concept": concept_name,
                    "compression_level": compression_level,
                    "conversation_log": evaluated_conversation,
                    "metadata": metadata
                }

                all_results.append(result)

                if save_results:
                    # Save to JSON file
                    filename = f"ddft_{self.model_name}_{concept_name}_c{int(compression_level*100):02d}.json"
                    filepath = os.path.join(self.results_dir, filename)
                    with open(filepath, 'w') as f:
                        json.dump(result, f, indent=2)

                print("✓")

        # Calculate metrics from results
        print(f"\n{'='*70}")
        print("Calculating metrics...")
        print(f"{'='*70}")

        profile = self._calculate_profile(all_results)

        print(f"\nCI Score: {profile.ci_score:.3f}")
        print(f"Phenotype: {profile.phenotype}")
        print(f"Danger Zone Rate: {profile.danger_zone_pct:.1f}%\n")

        return profile

    def _get_concept_files(self, concepts: Optional[List[str]]) -> List[str]:
        """Get list of concept JSON files to evaluate."""
        if concepts is None:
            # Use all concept files
            return sorted(glob.glob(os.path.join(self.concepts_dir, "*.json")))
        else:
            # Map concept names to files
            concept_files = []
            for concept in concepts:
                # Try different naming patterns
                patterns = [
                    f"{concept}.json",
                    f"*{concept}*.json",
                    f"{concept.lower().replace(' ', '_')}.json"
                ]
                for pattern in patterns:
                    matches = glob.glob(os.path.join(self.concepts_dir, pattern))
                    if matches:
                        concept_files.extend(matches)
                        break

            return sorted(list(set(concept_files)))

    def _calculate_profile(self, results: List[Dict]) -> CognitiveProfile:
        """Calculate cognitive profile from evaluation results."""
        # Convert results to dataframe format expected by analysis functions
        data = []
        for result in results:
            model = result["subject_model"]
            concept = result["concept"]
            compression = result["compression_level"]

            for msg in result["conversation_log"]:
                if msg["role"] == "assistant" and "evaluation" in msg:
                    consensus = msg["evaluation"]["consensus"]
                    data.append({
                        "model": model,
                        "concept": concept,
                        "compression": compression,
                        "FAR": consensus.get("FAR"),
                        "SAS": consensus.get("SAS")
                    })

        df = pd.DataFrame(data)

        # Calculate component metrics
        hoc_df = calculate_highest_operable_compression(df, threshold=0.70)
        fg_df = calculate_factual_consistency_gradient(df)
        decay_df = calculate_decay_smoothness(df)
        mca_df = calculate_model_calibration_accuracy(df)

        # Calculate CI
        ci_df = calculate_comprehension_integrity(hoc_df, fg_df, decay_df, mca_df)

        # Aggregate by model
        summary = ci_df.groupby("model").agg({
            "CI": "mean",
            "HOC": "mean",
            "FG": "mean",
            "Decay": "mean",
            "MCA": "mean"
        })

        # Get model's scores
        model_scores = summary.loc[self.model_name]

        # Calculate danger zone percentage
        danger_zone_pct = self._calculate_danger_zone_rate(df)

        # Create profile
        profile = CognitiveProfile(
            model_name=self.model_name,
            ci_score=model_scores["CI"],
            phenotype=classify_phenotype(model_scores["CI"]),
            hoc=model_scores["HOC"],
            fg=model_scores["FG"],
            decay_smoothness=model_scores["Decay"],
            mca=model_scores["MCA"],
            danger_zone_pct=danger_zone_pct,
            num_evaluations=len(data),
            concepts_tested=df["concept"].unique().tolist(),
            detailed_results=df
        )

        return profile

    def _calculate_danger_zone_rate(self, df: pd.DataFrame) -> float:
        """
        Calculate percentage of responses in the danger zone (high SAS, low FAR).

        Danger zone: SAS > 0.7 and FAR < 0.5 (fluent hallucination)
        """
        danger_zone = df[(df["SAS"] > 0.7) & (df["FAR"] < 0.5)]
        total_responses = len(df)

        if total_responses == 0:
            return 0.0

        return (len(danger_zone) / total_responses) * 100.0
