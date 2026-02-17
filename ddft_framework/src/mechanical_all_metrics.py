"""
Mechanical, reproducible evaluation metrics for DDFT.
Eliminates LLM judge for FAR, SAS, and FC computation.

Metrics:
- FAR (Factual Accuracy Rate): Reference-based claim verification
- SAS (Semantic Adherence Score): Epistemic marker detection
- FC (Fluency/Clarity): Readability metrics

All metrics are deterministic, reproducible, and hallucination-proof.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum
import math


@dataclass
class EvaluationResult:
    """Results from mechanical evaluation."""
    far: float  # 0.0-1.0
    sas: float  # 0.0-1.0
    fc: float   # 0.0-1.0
    
    # Metadata for debugging
    far_metadata: Dict
    sas_metadata: Dict
    fc_metadata: Dict
    
    @property
    def all_scores_valid(self) -> bool:
        """Check if all scores are valid (0.0-1.0)."""
        for score in [self.far, self.sas, self.fc]:
            if score is None or not (0.0 <= score <= 1.0):
                return False
        return True


# ============================================================================
# FAR: Factual Accuracy Rate
# ============================================================================

class MechanicalFAR:
    """
    Computes Factual Accuracy Rate by comparing response claims against
    reference text. Deterministic, reproducible, auditable.
    """
    
    def __init__(self, similarity_threshold: float = 0.75):
        """
        Args:
            similarity_threshold: How closely claim must match reference (0-1)
        """
        self.similarity_threshold = similarity_threshold
    
    def compute_far(self, response: str, reference_text: str) -> Tuple[float, Dict]:
        """
        Compute FAR by verifying response claims against reference.
        
        Args:
            response: Model's response
            reference_text: The reference text provided to model
            
        Returns:
            (far_score, metadata)
        """
        if not reference_text:
            # If no reference, FAR cannot be computed
            return 0.5, {"error": "No reference text provided", "claims": []}
        
        # Extract factual claims from response
        claims = self._extract_factual_claims(response)
        
        if not claims:
            # No factual claims = ambiguous (could be interpretation or factless response)
            return 0.5, {"claims": [], "verified": 0, "note": "No factual claims found"}
        
        # Verify each claim against reference
        verified_count = 0
        verification_details = []
        
        for claim in claims:
            is_verified = self._verify_claim(claim, reference_text)
            verified_count += is_verified
            verification_details.append({
                "claim": claim,
                "verified": bool(is_verified)
            })
        
        # Compute FAR with ternary thresholds to match LLM judge scale
        accuracy_ratio = verified_count / len(claims)
        
        # Ternary scale: 0.0 (inaccurate), 0.5 (mixed), 1.0 (accurate)
        if accuracy_ratio >= 0.75:
            far = 1.0  # Mostly/fully accurate
        elif accuracy_ratio >= 0.25:
            far = 0.5  # Mixed accuracy
        else:
            far = 0.0  # Mostly inaccurate
        
        metadata = {
            "claims": claims,
            "verified": verified_count,
            "total_claims": len(claims),
            "accuracy_ratio": accuracy_ratio,
            "far": far,
            "far_category": "accurate" if far == 1.0 else ("mixed" if far == 0.5 else "inaccurate"),
            "verification_details": verification_details
        }
        
        return far, metadata
    
    def _extract_factual_claims(self, text: str) -> List[str]:
        """
        Extract factual claims from text.
        
        Simple heuristic: Look for sentences that contain facts.
        More sophisticated approach: NLP parsing to extract propositions.
        """
        sentences = self._split_sentences(text)
        claims = []
        
        for sentence in sentences:
            # Filter out hedging, questions, citations
            if self._is_factual_claim(sentence):
                claim = self._normalize_claim(sentence)
                if claim:
                    claims.append(claim)
        
        return claims
    
    def _split_sentences(self, text: str) -> List[str]:
        """Simple sentence splitter."""
        # Split on periods, but avoid abbreviations
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _is_factual_claim(self, sentence: str) -> bool:
        """
        Heuristic: Is this sentence a factual claim (not hedging/question)?
        """
        sentence_lower = sentence.lower()
        
        # Filter out hedging language
        hedging_markers = ["might", "could", "perhaps", "maybe", "seems", "apparently"]
        if any(marker in sentence_lower for marker in hedging_markers):
            return False
        
        # Filter out questions
        if sentence.strip().endswith("?"):
            return False
        
        # Filter out very short sentences
        if len(sentence.split()) < 3:
            return False
        
        # Likely a factual claim
        return True
    
    def _normalize_claim(self, claim: str) -> str:
        """Normalize claim for comparison."""
        # Remove leading/trailing whitespace and punctuation
        claim = claim.strip()
        claim = re.sub(r'[.!?]+$', '', claim)
        
        # Convert to lowercase for comparison
        claim = claim.lower()
        
        # Remove excess whitespace
        claim = re.sub(r'\s+', ' ', claim)
        
        return claim
    
    def _verify_claim(self, claim: str, reference_text: str) -> bool:
        """
        Check if claim content appears in reference.
        Uses fuzzy matching to handle paraphrasing.
        """
        reference_norm = reference_text.lower()
        reference_norm = re.sub(r'\s+', ' ', reference_norm)
        
        # Method 1: Exact substring match
        if claim in reference_norm:
            return True
        
        # Method 2: Check if key phrases appear
        key_phrases = self._extract_key_phrases(claim)
        for phrase in key_phrases:
            if phrase in reference_norm:
                return True
        
        # Method 3: Fuzzy matching (simple word overlap)
        claim_words = set(claim.split())
        reference_words = set(reference_norm.split())
        
        overlap = len(claim_words & reference_words) / len(claim_words)
        if overlap >= self.similarity_threshold:
            return True
        
        return False
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract important nouns and noun phrases."""
        # Simple heuristic: Words longer than 4 chars, excluding common words
        common_words = {
            "that", "this", "what", "when", "where", "which", "who",
            "and", "or", "but", "the", "are", "is", "was", "were"
        }
        words = text.split()
        key_phrases = [w for w in words if len(w) > 4 and w not in common_words]
        return key_phrases


# ============================================================================
# SAS: Semantic Adherence Score (from previous analysis)
# ============================================================================

class MechanicalSAS:
    """Epistemic marker-based SAS scoring with implicit uncertainty detection."""
    
    EPISTEMIC_MARKERS = {
        "negation": [
            "i cannot", "i don't know", "i'm unable", "impossible to",
            "i have no", "i lack", "unable to", "cannot provide"
        ],
        "modal": [
            "might", "could", "may", "perhaps", "possibly", "probably"
        ],
        "confidence_reduction": [
            "uncertain", "unclear", "ambiguous", "vague", "not clear"
        ],
        "limitation": [
            "i lack", "i don't have", "insufficient", "limited knowledge"
        ],
        "correction": [
            "i was wrong", "i made an error", "reconsidering", "actually"
        ],
        "contradiction": [
            "i cannot accept", "i don't believe", "that is incorrect"
        ],
        # NEW: Academic hedging (implicit uncertainty)
        "academic_hedging": [
            "appears to", "suggests that", "may indicate", "tends to",
            "is likely", "seems to", "could be", "in general", "generally"
        ],
        # NEW: Conditional language
        "conditional": [
            "in many cases", "often", "typically", "usually",
            "it seems", "it appears", "given that", "assuming", "if we consider"
        ],
        # NEW: Qualifiers (approximate language)
        "qualification": [
            "approximately", "roughly", "estimated", "around",
            "more or less", "sort of", "kind of"
        ]
    }
    
    def compute_sas(self, response: str) -> Tuple[float, Dict]:
        """
        Compute SAS using epistemic marker detection (implicit + explicit).
        
        Ternary scale:
        - 0.0: No epistemic markers (treats claims as certainties)
        - 0.5: 1-2 markers present (some acknowledgment of uncertainty)
        - 1.0: 3+ markers present (clear epistemic awareness)
        
        Returns:
            (sas_score, metadata)
        """
        markers_found, marker_counts = self._find_markers(response)
        total_markers = len(set(markers_found))
        distribution = self._compute_distribution(response, markers_found)
        
        # Simplified ternary scoring based on marker count
        if total_markers == 0:
            sas = 0.0
            category = "treats_as_fact"
        elif total_markers <= 2:
            sas = 0.5
            category = "limited_hedging"
        else:  # 3+
            sas = 1.0
            category = "explicit_uncertainty"
        
        metadata = {
            "marker_count": total_markers,
            "markers_found": list(set(markers_found)),
            "distribution_score": distribution,
            "category": category,
            "marker_counts_by_type": marker_counts,
            "note": "Scoring based on marker presence, not distribution"
        }
        
        return sas, metadata
    
    def _find_markers(self, text: str) -> Tuple[List[str], Dict[str, int]]:
        """Find epistemic markers in text."""
        text_norm = text.lower()
        markers_found = []
        marker_counts = {cat: 0 for cat in self.EPISTEMIC_MARKERS}
        
        for category, markers in self.EPISTEMIC_MARKERS.items():
            for marker in markers:
                if marker in text_norm:
                    markers_found.append(marker)
                    marker_counts[category] += 1
        
        return markers_found, marker_counts
    
    def _compute_distribution(self, text: str, markers_found: List[str]) -> float:
        """How distributed are markers across response?"""
        if not markers_found:
            return 0.0
        
        text_norm = text.lower()
        text_length = len(text_norm)
        
        # Divide into 3 sections
        section_length = text_length // 3
        sections = [
            text_norm[:section_length],
            text_norm[section_length:2*section_length],
            text_norm[2*section_length:]
        ]
        
        # Count markers in each section
        section_counts = []
        for section in sections:
            count = sum(1 for marker in markers_found if marker in section)
            section_counts.append(count)
        
        # Distribution = inverse of concentration
        total = sum(section_counts)
        if total == 0:
            return 0.0
        
        max_section = max(section_counts)
        concentration = max_section / total
        distribution = 1 - concentration
        
        return distribution


# ============================================================================
# FC: Fluency/Clarity
# ============================================================================

class MechanicalFC:
    """
    Computes Fluency/Clarity using readability metrics.
    Based on well-established linguistic measures.
    """
    
    def compute_fc(self, response: str) -> Tuple[float, Dict]:
        """
        Compute FC from readability metrics.
        
        Components:
        - Readability grade level (Flesch-Kincaid)
        - Average sentence length
        - Coherence/discourse markers
        
        Returns:
            (fc_score, metadata)
        """
        readability = self._compute_readability(response)
        complexity = self._compute_complexity(response)
        coherence = self._compute_coherence(response)
        
        # Normalize and weight
        readability_norm = self._normalize_readability(readability)
        complexity_norm = self._normalize_complexity(complexity)
        coherence_norm = self._normalize_coherence(coherence)
        
        # Weighted average
        fc = (
            0.4 * readability_norm +
            0.3 * complexity_norm +
            0.3 * coherence_norm
        )
        
        metadata = {
            "readability_grade": readability,
            "readability_normalized": readability_norm,
            "avg_sentence_length": complexity,
            "complexity_normalized": complexity_norm,
            "coherence_score": coherence,
            "coherence_normalized": coherence_norm,
            "final_fc": fc
        }
        
        return fc, metadata
    
    def _compute_readability(self, text: str) -> float:
        """
        Compute Flesch-Kincaid grade level.
        
        Formula: 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59
        Returns: Grade level (0-20+)
        
        Grade 8-10 is considered "ideal" clarity.
        """
        words = len(text.split())
        sentences = len(re.split(r'[.!?]+', text)) - 1
        syllables = self._count_syllables(text)
        
        if words == 0 or sentences == 0:
            return 10.0  # Default middle grade
        
        grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59
        
        # Clamp to reasonable range (0-20)
        grade = max(0, min(20, grade))
        
        return grade
    
    def _count_syllables(self, text: str) -> int:
        """
        Estimate syllable count (rough heuristic).
        Real implementation would use CMU dict or similar.
        """
        vowels = "aeiouy"
        syllable_count = 0
        previous_was_vowel = False
        
        for char in text.lower():
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel
        
        # Adjust for silent 'e' at end
        if text.lower().endswith('e'):
            syllable_count -= 1
        
        # Ensure at least 1 syllable per word
        syllable_count = max(len(text.split()), syllable_count)
        
        return syllable_count
    
    def _compute_complexity(self, text: str) -> float:
        """
        Average words per sentence.
        Lower = simpler and clearer.
        """
        words = len(text.split())
        sentences = len(re.split(r'[.!?]+', text)) - 1
        
        if sentences == 0:
            return len(text.split())
        
        return words / sentences
    
    def _compute_coherence(self, text: str) -> float:
        """
        Measure coherence using discourse markers and structural clarity.
        
        Factors:
        - Presence of discourse markers (however, therefore, etc.)
        - Pronoun clarity (clear antecedents)
        - Repetition of key terms
        """
        discourse_markers = [
            "however", "therefore", "thus", "moreover", "furthermore",
            "in addition", "on the other hand", "in conclusion",
            "first", "second", "finally", "meanwhile", "ultimately"
        ]
        
        text_lower = text.lower()
        marker_count = sum(1 for marker in discourse_markers if marker in text_lower)
        
        # Normalize: expect 3-5 markers per response
        marker_score = min(marker_count / 5.0, 1.0)
        
        # Check for clear pronoun antecedents (heuristic)
        pronouns = ["it", "this", "that", "these", "those", "they", "he", "she"]
        unclear_pronouns = 0
        for pronoun in pronouns:
            # Count instances where pronoun appears without clear reference
            if f" {pronoun} " in f" {text_lower} ":
                # Simple heuristic: if pronoun appears multiple times, might be unclear
                pass
        
        # For now, give partial credit for discourse markers
        coherence = marker_score * 0.7 + 0.3  # Baseline of 0.3
        
        return min(1.0, coherence)
    
    def _normalize_readability(self, grade_level: float) -> float:
        """
        Normalize grade level to 0-1 score.
        Ideal range: 8-12 (high school to college level, appropriate for academic writing).
        """
        if grade_level < 6:
            # Too simple (but acceptable)
            score = 0.5
        elif 6 <= grade_level <= 12:
            # Ideal academic range - give full credit
            score = 1.0
        elif 12 < grade_level <= 16:
            # Graduate level - acceptable, minor penalty
            score = 0.9 - (grade_level - 12) / 4.0 * 0.2
            score = max(0.7, score)
        else:
            # Very complex (16+)
            score = 0.7
        
        return min(1.0, max(0.0, score))
    
    def _normalize_complexity(self, avg_words_per_sentence: float) -> float:
        """
        Normalize sentence length to 0-1 score.
        Ideal: 15-20 words per sentence.
        """
        if avg_words_per_sentence < 10:
            score = 0.8  # Too short, somewhat choppy
        elif 10 <= avg_words_per_sentence <= 20:
            # Ideal range
            score = 1.0 - (avg_words_per_sentence - 15) / 10.0 * 0.3
            score = max(0.7, score)
        elif 20 < avg_words_per_sentence <= 30:
            # Longer but readable
            score = 0.7 - (avg_words_per_sentence - 20) / 10.0 * 0.3
            score = max(0.4, score)
        else:
            # Very long sentences
            score = 0.3
        
        return min(1.0, max(0.0, score))
    
    def _normalize_coherence(self, coherence_score: float) -> float:
        """Coherence already normalized, just return."""
        return coherence_score


# ============================================================================
# Combined Mechanical Judge
# ============================================================================

class MechanicalJudgeAllMetrics:
    """
    Unified judge for all metrics: FAR, SAS, FC.
    Eliminates LLM judge completely. Fully reproducible.
    """
    
    def __init__(self):
        self.far_judge = MechanicalFAR()
        self.sas_judge = MechanicalSAS()
        self.fc_judge = MechanicalFC()
    
    def evaluate_response(self,
                         response: str,
                         reference_text: Optional[str] = None,
                         turn_number: Optional[int] = None) -> EvaluationResult:
        """
        Evaluate response on all three metrics.
        
        Args:
            response: Model's response
            reference_text: Reference text provided to model (needed for FAR)
            turn_number: Which turn (for metadata)
            
        Returns:
            EvaluationResult with FAR, SAS, FC scores and metadata
        """
        far, far_meta = self.far_judge.compute_far(response, reference_text or "")
        sas, sas_meta = self.sas_judge.compute_sas(response)
        fc, fc_meta = self.fc_judge.compute_fc(response)
        
        return EvaluationResult(
            far=far,
            sas=sas,
            fc=fc,
            far_metadata=far_meta,
            sas_metadata=sas_meta,
            fc_metadata=fc_meta
        )
    
    def evaluate_batch(self,
                       responses: List[Dict],
                       verbose: bool = False) -> List[EvaluationResult]:
        """
        Evaluate multiple responses.
        
        Args:
            responses: List of dicts with 'response', 'reference_text', 'turn'
            verbose: Print progress
            
        Returns:
            List of EvaluationResult objects
        """
        results = []
        for i, resp in enumerate(responses):
            if verbose and i % 100 == 0:
                print(f"Evaluated {i}/{len(responses)} responses")
            
            result = self.evaluate_response(
                response=resp.get('response', ''),
                reference_text=resp.get('reference_text'),
                turn_number=resp.get('turn')
            )
            results.append(result)
        
        return results


# ============================================================================
# Comparison & Validation
# ============================================================================

def compare_with_llm_judge(mechanical_results: List[EvaluationResult],
                          llm_results: List[Dict]) -> Dict:
    """
    Compare mechanical scores against original LLM judge scores.
    Compute convergence statistics.
    
    Returns metrics for validation.
    """
    import statistics
    from scipy.stats import pearsonr
    
    far_diffs = []
    sas_diffs = []
    fc_diffs = []
    
    for mech, llm in zip(mechanical_results, llm_results):
        far_diffs.append(abs(mech.far - llm.get('FAR', 0)))
        sas_diffs.append(abs(mech.sas - llm.get('SAS', 0)))
        fc_diffs.append(abs(mech.fc - llm.get('FC', 0)))
    
    far_corr = pearsonr(
        [m.far for m in mechanical_results],
        [llm.get('FAR', 0) for llm in llm_results]
    )[0]
    
    sas_corr = pearsonr(
        [m.sas for m in mechanical_results],
        [llm.get('SAS', 0) for llm in llm_results]
    )[0]
    
    fc_corr = pearsonr(
        [m.fc for m in mechanical_results],
        [llm.get('FC', 0) for llm in llm_results]
    )[0]
    
    return {
        'FAR': {
            'mean_diff': statistics.mean(far_diffs),
            'correlation': far_corr
        },
        'SAS': {
            'mean_diff': statistics.mean(sas_diffs),
            'correlation': sas_corr
        },
        'FC': {
            'mean_diff': statistics.mean(fc_diffs),
            'correlation': fc_corr
        }
    }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    judge = MechanicalJudgeAllMetrics()
    
    example_response = """
    I'm uncertain about some aspects of this, but from the reference text,
    I can verify that natural selection is a process. However, I should note
    that my understanding might be incomplete. The concept appears to involve
    adaptation and survival, though I cannot confirm all details with certainty.
    """
    
    example_reference = """
    Natural selection is the process by which organisms better adapted to their
    environment tend to survive and produce more offspring. It was first formally
    described by Charles Darwin.
    """
    
    result = judge.evaluate_response(example_response, example_reference)
    
    print(f"FAR: {result.far:.2f}")
    print(f"SAS: {result.sas:.2f}")
    print(f"FC: {result.fc:.2f}")
    print(f"\nAll scores valid: {result.all_scores_valid}")
