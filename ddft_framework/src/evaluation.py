"""
Response evaluation module with CORRECTED hallucination detection.

This module evaluates LLM responses against expected keywords and provided context.
The key fix: distinguishes between domain elaboration (appropriate) and hallucination (false).

A hallucination is flagged ONLY when:
1. The word is NOT in the provided context
2. The word is NOT in the domain vocabulary (the model shouldn't know it)
3. The word is NOT a generic term
4. AND there's evidence of fabrication (e.g., missing expected keywords)
"""

from typing import List, Dict, Any, Set
import re


class KeywordMatcher:
    """Handles keyword matching with word boundary enforcement."""
    
    def __init__(self, case_sensitive: bool = False):
        self.case_sensitive = case_sensitive
    
    def find_keywords(self, text: str, keywords: List[str]) -> Dict[str, List[str]]:
        """
        Find which keywords are present in text.
        
        Returns:
            Dict with 'found' and 'missing' lists
        """
        text_to_search = text if self.case_sensitive else text.lower()
        
        found = []
        missing = []
        
        for keyword in keywords:
            search_keyword = keyword if self.case_sensitive else keyword.lower()
            pattern = r'\b' + re.escape(search_keyword) + r'\b'
            
            if re.search(pattern, text_to_search):
                found.append(keyword)
            else:
                missing.append(keyword)
        
        return {'found': found, 'missing': missing}


class HallucinationDetector:
    """
    Conservative hallucination detection aligned with CDCT philosophy.
    
    Key insight: When context is compressed, the model MUST elaborate using
    domain vocabulary. This is not hallucination—it's appropriate reasoning.
    
    We only flag as hallucinated words that:
    1. Are NOT in the provided context
    2. Are NOT in domain vocabulary
    3. Are NOT generic elaboration terms
    4. AND appear when core concepts are missing
    """
    
    # Words that are common across most domains AND expected in elaborations
    GENERIC_TERMS = {
        # Generic articles, prepositions, conjunctions
        'that', 'this', 'with', 'from', 'have', 'been', 'were', 'will', 'would',
        'could', 'should', 'such', 'more', 'most', 'some', 'many', 'other', 'same',
        'when', 'where', 'which', 'their', 'there', 'these', 'what', 'also', 'only',
        'very', 'just', 'even', 'like', 'well', 'good', 'said', 'used', 'does',
        # Domain elaboration verbs (CRITICAL FIX: these are expected when explaining)
        'analyze', 'describe', 'explain', 'means', 'refers', 'involves', 'includes',
        'example', 'case', 'instance', 'type', 'form', 'kind', 'way', 'process',
        'called', 'known', 'term', 'concept', 'idea', 'notion', 'principle',
        'relates', 'connected', 'associated', 'linked', 'dependent', 'determines',
        'represents', 'shows', 'indicates', 'demonstrates', 'displays', 'exhibits',
        'involves', 'implies', 'suggests', 'indicates', 'signifies', 'denotes',
        'measures', 'quantifies', 'specifies', 'defines', 'characterizes',
        # Common in elaboration
        'another', 'becomes', 'between', 'changes', 'determines', 'provides',
        'allows', 'enables', 'causes', 'produces', 'results', 'follows', 'derives',
        'applies', 'extends', 'generalizes', 'specializes', 'combines', 'interacts',
        'helps', 'supports', 'maintains', 'preserves', 'protects', 'ensures'
    }
    
    def __init__(self, min_word_length: int = 5):
        """
        Initialize detector.
        
        Args:
            min_word_length: Words shorter than this are ignored (5 = substantial words)
        """
        self.min_word_length = min_word_length
    
    def extract_vocabulary(self, text: str) -> Set[str]:
        """Extract meaningful words from text (minimum length threshold)."""
        pattern = rf'\b[a-z]{{{self.min_word_length},}}\b'
        return set(re.findall(pattern, text.lower()))
    
    def find_hallucinations(
        self,
        response: str,
        context: str,
        domain_vocabulary: Set[str] = None,
        expected_keywords: List[str] = None
    ) -> Dict[str, Any]:
        """
        Identify hallucinated content and distinguish from domain elaboration.
        
        Args:
            response: Model's response text
            context: Provided context
            domain_vocabulary: Additional valid vocabulary (from full concept)
            expected_keywords: Keywords that should appear
            
        Returns:
            Dict with hallucination details and severity
        """
        response_vocab = self.extract_vocabulary(response)
        context_vocab = self.extract_vocabulary(context)
        
        # Build valid vocabulary (what model is allowed to use)
        valid_vocab = context_vocab.copy()
        if domain_vocabulary:
            valid_vocab.update(domain_vocabulary)
        
        # Categorize response words
        hallucinated = []
        elaboration = []
        
        for word in response_vocab:
            # Check if word is acceptable
            in_context = word in context_vocab
            in_domain = word in (domain_vocabulary or set())
            is_generic = word in self.GENERIC_TERMS
            
            if in_context:
                # Word appears in provided context - definitely safe
                continue
            elif in_domain and not is_generic:
                # Word is domain vocabulary - this is ELABORATION, not hallucination
                # The model knows about this concept and is explaining it
                elaboration.append(word)
            elif is_generic:
                # Generic elaboration term - skip
                continue
            else:
                # Word not in context, not in domain, not generic - HALLUCINATED
                hallucinated.append(word)
        
        # Check if expected keywords are present
        keywords_found = True
        if expected_keywords:
            response_lower = response.lower()
            keywords_found = all(
                any(re.search(r'\b' + re.escape(kw.lower()) + r'\b', response_lower) 
                    for _ in [None])
                for kw in expected_keywords
                if re.search(r'\b' + re.escape(kw.lower()) + r'\b', response_lower)
            )
            # Simpler: check how many keywords are found
            found_count = sum(
                1 for kw in expected_keywords
                if re.search(r'\b' + re.escape(kw.lower()) + r'\b', response_lower)
            )
            keywords_found = (found_count / len(expected_keywords)) >= 0.5 if expected_keywords else True
        
        # Calculate hallucination severity
        # FIXED: Only high severity if BOTH hallucinated words AND missing core concepts
        severity = 0.0
        
        if hallucinated:
            if not keywords_found:
                # Model hallucinated AND missed expected keywords - very bad
                severity = min(1.0, len(hallucinated) / 3)
            elif len(hallucinated) > 8:
                # Many hallucinated words (>8) suggests confabulation/padding
                severity = 0.4
            else:
                # Few hallucinated words (1-8) - minor issue
                severity = 0.1
        
        return {
            'hallucinated_words': sorted(hallucinated)[:5],
            'n_hallucinated': len(hallucinated),
            'elaboration_words': sorted(elaboration)[:5],  # What model appropriately elaborated
            'n_elaboration': len(elaboration),
            'hallucination_severity': severity,
            'expected_keywords_found': keywords_found,
        }


class ResponseEvaluator:
    """Main evaluation engine combining multiple scoring criteria."""
    
    def __init__(self, evaluation_mode: str = "balanced"):
        """
        Initialize evaluator.
        
        Args:
            evaluation_mode: "strict", "balanced", or "lenient"
        """
        if evaluation_mode not in ("strict", "balanced", "lenient"):
            raise ValueError(f"Invalid mode: {evaluation_mode}")
        
        self.evaluation_mode = evaluation_mode
        self.keyword_matcher = KeywordMatcher(case_sensitive=False)
        self.hallucination_detector = HallucinationDetector()
    
    def evaluate_keywords(
        self,
        response: str,
        expected_keywords: List[str]
    ) -> Dict[str, Any]:
        """Score based on expected keywords."""
        if not expected_keywords:
            return {
                'score': 1.0,
                'found': [],
                'missing': [],
                'found_count': 0,
                'total_count': 0
            }
        
        result = self.keyword_matcher.find_keywords(response, expected_keywords)
        score = len(result['found']) / len(expected_keywords)
        
        return {
            'score': score,
            'found': result['found'],
            'missing': result['missing'],
            'found_count': len(result['found']),
            'total_count': len(expected_keywords)
        }
    
    def evaluate_hallucinations(
        self,
        response: str,
        context: str,
        expected_keywords: List[str] = None,
        domain_context: str = None,
        penalize: bool = True
    ) -> Dict[str, Any]:
        """Detect and score hallucinations (FIXED: severity-based)."""
        domain_vocab = None
        if domain_context:
            domain_vocab = self.hallucination_detector.extract_vocabulary(domain_context)
        
        hallucination_result = self.hallucination_detector.find_hallucinations(
            response, context, domain_vocab, expected_keywords
        )
        
        # FIXED: Penalize based on SEVERITY, not count
        penalty = 0.0
        if penalize:
            severity = hallucination_result['hallucination_severity']
            if severity > 0.5:
                penalty = severity * 0.3  # Max 0.3 penalty at severity 1.0
            elif severity > 0.2:
                penalty = severity * 0.15  # Max 0.15 penalty at severity 0.5
        
        return {
            'hallucinated_words': hallucination_result['hallucinated_words'],
            'n_hallucinated': hallucination_result['n_hallucinated'],
            'elaboration_words': hallucination_result['elaboration_words'],
            'hallucination_severity': hallucination_result['hallucination_severity'],
            'penalty': penalty,
            'score': max(0.0, 1.0 - penalty),
            'expected_keywords_found': hallucination_result['expected_keywords_found']
        }
    
    def evaluate_length(
        self,
        response: str,
        compression_level: int,
        max_compression_level: int
    ) -> Dict[str, Any]:
        """Evaluate if response length is appropriate for compression level."""
        response_words = len(response.split())
        
        # Scale expected length with compression level (0 = most compressed)
        compression_ratio = compression_level / max_compression_level
        expected_min = 10 + (40 * compression_ratio)
        expected_max = 30 + (120 * compression_ratio)
        
        # Score based on how well length matches expectation
        if response_words < expected_min * 0.5:
            length_score = 0.5  # Too short
        elif response_words > expected_max * 1.5:
            # Penalize verbose responses more at higher compression levels
            excess = response_words - expected_max * 1.5
            penalty = (excess / expected_max) * (0.5 * (1 - compression_ratio))
            length_score = max(0.3, 1.0 - penalty)
        else:
            length_score = 1.0
        
        return {
            'score': length_score,
            'response_words': response_words,
            'expected_min': expected_min,
            'expected_max': expected_max,
            'in_range': expected_min <= response_words <= expected_max
        }
    
    def evaluate(
        self,
        response: str,
        expected_keywords: List[str],
        context: str,
        compression_level: int,
        max_compression_level: int,
        domain_context: str = None
    ) -> Dict[str, Any]:
        """
        Comprehensive evaluation of response.
        
        Args:
            response: Model's response text
            expected_keywords: Keywords that should appear
            context: Compressed context provided to model
            compression_level: Current compression level (0 = most compressed)
            max_compression_level: Maximum level in protocol
            domain_context: Full explanation for domain vocabulary
            
        Returns:
            Comprehensive evaluation dict with final score and components
        """
        # Component scores
        keyword_eval = self.evaluate_keywords(response, expected_keywords)
        hallucination_eval = self.evaluate_hallucinations(
            response, context, expected_keywords, domain_context,
            penalize=(self.evaluation_mode != "lenient")
        )
        length_eval = self.evaluate_length(
            response, compression_level, max_compression_level
        )
        
        # Determine weights based on mode and compression
        compression_ratio = compression_level / max_compression_level
        
        if self.evaluation_mode == "strict":
            weights = {
                'keyword': 0.5,
                'hallucination': 0.3,
                'length': 0.2
            }
        elif self.evaluation_mode == "lenient":
            weights = {
                'keyword': 1.0,
                'hallucination': 0.0,
                'length': 0.0
            }
        else:  # balanced
            weights = {
                'keyword': 0.5,
                'hallucination': 0.3,
                'length': 0.2 * compression_ratio  # More important at high compression
            }
        
        # Combine scores
        final_score = (
            keyword_eval['score'] * weights['keyword'] +
            hallucination_eval['score'] * weights['hallucination'] +
            length_eval['score'] * weights.get('length', 0)
        )
        
        final_score = max(0.0, min(1.0, final_score))
        
        return {
            'final_score': final_score,
            'keywords': keyword_eval,
            'hallucinations': hallucination_eval,
            'length': length_eval,
            'weights': weights,
            'verdict': self._determine_verdict(
                keyword_eval, hallucination_eval, final_score
            ),
            'mode': self.evaluation_mode
        }
    
    def _determine_verdict(
        self,
        keyword_eval: Dict[str, Any],
        hallucination_eval: Dict[str, Any],
        final_score: float
    ) -> str:
        """
        Determine qualitative verdict based on scores.
        
        FIXED: Verdicts now align with scores (no more 0.79 = "memorized" contradictions)
        """
        # Primary verdict based on score
        if final_score >= 0.85:
            base_verdict = 'excellent'
        elif final_score >= 0.70:
            base_verdict = 'good'
        elif final_score >= 0.50:
            base_verdict = 'fair'
        else:
            base_verdict = 'poor'
        
        # Only apply hallucination modifier if SEVERE
        if hallucination_eval['hallucination_severity'] > 0.6:
            if not hallucination_eval['expected_keywords_found']:
                # High hallucination + missing keywords = "memorized"
                return 'memorized'
        
        return base_verdict


# Backward compatibility wrappers

def evaluate_response(response: str, expected_keywords: List[str]) -> float:
    """
    Legacy simple evaluation. Returns keyword match ratio.
    
    Deprecated: Use ResponseEvaluator.evaluate() instead.
    """
    evaluator = ResponseEvaluator()
    result = evaluator.evaluate_keywords(response, expected_keywords)
    return result['score']


def evaluate_response_strict(
    response: str,
    expected_keywords: List[str],
    available_context: str,
    penalize_extra: bool = True,
    domain_context: str = None
) -> Dict[str, Any]:
    """
    Legacy strict evaluation with hallucination detection.
    
    Deprecated: Use ResponseEvaluator.evaluate() instead.
    """
    evaluator = ResponseEvaluator(evaluation_mode="strict")
    keyword_eval = evaluator.evaluate_keywords(response, expected_keywords)
    hallucination_eval = evaluator.evaluate_hallucinations(
        response, available_context, expected_keywords, domain_context, penalize_extra
    )
    
    return {
        'score': keyword_eval['score'] * 0.7 + hallucination_eval['score'] * 0.3,
        'base_score': keyword_eval['score'],
        'found': keyword_eval['found'],
        'missing': keyword_eval['missing'],
        'hallucinated': hallucination_eval['hallucinated_words'],
        'hallucination_penalty': hallucination_eval['penalty']
    }


def evaluate_response_length_aware(
    response: str,
    expected_keywords: List[str],
    compression_level: int,
    max_compression_level: int
) -> Dict[str, Any]:
    """
    Legacy length-aware evaluation.
    
    Deprecated: Use ResponseEvaluator.evaluate() instead.
    """
    evaluator = ResponseEvaluator()
    keyword_eval = evaluator.evaluate_keywords(response, expected_keywords)
    length_eval = evaluator.evaluate_length(
        response, compression_level, max_compression_level
    )
    
    combined_score = (keyword_eval['score'] * 0.7) + (length_eval['score'] * 0.3)
    
    return {
        'score': combined_score,
        'keyword_score': keyword_eval['score'],
        'length_score': length_eval['score'],
        'response_words': length_eval['response_words'],
        'expected_range': (length_eval['expected_min'], length_eval['expected_max'])
    }


def evaluate_response_comprehensive(
    response: str,
    expected_keywords: List[str],
    available_context: str,
    compression_level: int,
    max_compression_level: int,
    evaluation_mode: str = "balanced",
    full_concept_text: str = None
) -> Dict[str, Any]:
    """
    Legacy comprehensive evaluation.
    
    Deprecated: Use ResponseEvaluator.evaluate() instead.
    """
    evaluator = ResponseEvaluator(evaluation_mode=evaluation_mode)
    result = evaluator.evaluate(
        response,
        expected_keywords,
        available_context,
        compression_level,
        max_compression_level,
        full_concept_text
    )
    
    return {
        'final_score': result['final_score'],
        'components': {
            'strict': {
                'score': result['keywords']['score'],
                'found': result['keywords']['found'],
                'missing': result['keywords']['missing'],
                'hallucinated': result['hallucinations']['hallucinated_words'],
                'hallucination_penalty': result['hallucinations']['penalty']
            },
            'length': {
                'score': result['length']['score'],
                'response_words': result['length']['response_words'],
                'expected_range': (result['length']['expected_min'], result['length']['expected_max'])
            }
        },
        'weights': result['weights'],
        'verdict': result['verdict'],
        'response_length': result['length']['response_words'],
        'compression_level': compression_level
    }