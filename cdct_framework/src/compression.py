import json
import re
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class CompressionStep:
    compression_level: int
    text: str
    probe_question: str
    expected_keywords: List[str]

@dataclass
class Concept:
    concept: str
    domain: str
    abstraction_level: int
    corpus: List[CompressionStep]

def load_concept(file_path: str) -> Concept:
    """Loads a concept from a JSON file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    corpus = [CompressionStep(**step) for step in data['corpus']]
    return Concept(
        concept=data['concept'],
        domain=data['domain'],
        abstraction_level=data['abstraction_level'],
        corpus=corpus
    )

@dataclass
class CompressionValidation:
    """Results from validating a compression protocol."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, Any]

def validate_compression_protocol(corpus: List[Dict[str, Any]]) -> CompressionValidation:
    """
    Validates a compression protocol against CDCT requirements.
    
    Requirements from paper:
    1. Progressive information reduction (monotonic text length decrease)
    2. Semantic preservation (core concept keywords present at all levels)
    3. Proper level ordering (0 = most compressed, N = least compressed)
    4. Sufficient resolution (at least 3-5 levels recommended)
    
    Args:
        corpus: List of compression steps from a concept JSON
    
    Returns:
        CompressionValidation with errors, warnings, and metrics
    """
    errors = []
    warnings = []
    metrics = {}
    
    if not corpus:
        errors.append("Empty corpus")
        return CompressionValidation(False, errors, warnings, metrics)
    
    # Extract data
    levels = [step["compression_level"] for step in corpus]
    texts = [step["text"] for step in corpus]
    questions = [step["probe_question"] for step in corpus]
    keywords = [step["expected_keywords"] for step in corpus]
    
    # ============================================================
    # 1. Check level ordering
    # ============================================================
    if levels != sorted(levels):
        errors.append(
            f"Compression levels not in ascending order: {levels}. "
            "Should be [0, 1, 2, ...] where 0=most compressed."
        )
    
    if levels[0] != 0:
        warnings.append(f"First level is {levels[0]}, expected 0")
    
    # ============================================================
    # 2. Check monotonic information increase
    # ============================================================
    text_lengths = [len(text.split()) for text in texts]
    metrics["text_lengths"] = text_lengths
    
    non_monotonic = []
    for i in range(1, len(text_lengths)):
        if text_lengths[i] < text_lengths[i-1]:
            non_monotonic.append(i)
    
    if non_monotonic:
        errors.append(
            f"Non-monotonic information: text at levels {non_monotonic} "
            f"is shorter than previous level. Lengths: {text_lengths}"
        )
    
    # ============================================================
    # 3. Check compression ratio
    # ============================================================
    if text_lengths:
        compression_ratio = text_lengths[-1] / text_lengths[0] if text_lengths[0] > 0 else float('inf')
        metrics["compression_ratio"] = compression_ratio
        
        if compression_ratio < 3:
            warnings.append(
                f"Low compression ratio ({compression_ratio:.1f}x). "
                f"Recommended: at least 5-10x between min and max. "
                f"Current: {text_lengths[0]} → {text_lengths[-1]} words"
            )
    
    # ============================================================
    # 4. Check semantic preservation
    # ============================================================
    # Core keywords from most compressed level should appear at all levels
    if keywords:
        core_keywords = set(kw.lower() for kw in keywords[0])
        
        for i, (text, level_keywords) in enumerate(zip(texts, keywords)):
            text_lower = text.lower()
            level_kw_lower = set(kw.lower() for kw in level_keywords)
            
            # Check if core concepts persist
            missing_core = core_keywords - set(
                kw for kw in core_keywords if kw in text_lower
            )
            
            if missing_core and i > 0:  # Allow variation at level 0 (most compressed)
                warnings.append(
                    f"Level {levels[i]}: core keywords {missing_core} "
                    f"from compressed form not found in text"
                )
    
    # ============================================================
    # 5. Check keyword progression
    # ============================================================
    keyword_counts = [len(kws) for kws in keywords]
    metrics["keyword_counts"] = keyword_counts
    
    # Keywords should generally increase with less compression
    if keyword_counts != sorted(keyword_counts):
        warnings.append(
            f"Keyword counts don't increase monotonically: {keyword_counts}. "
            "Expected more keywords at lower compression levels."
        )
    
    # ============================================================
    # 6. Check resolution (number of levels)
    # ============================================================
    n_levels = len(corpus)
    metrics["n_levels"] = n_levels
    
    if n_levels < 3:
        warnings.append(
            f"Only {n_levels} compression levels. Recommended: at least 5 "
            "for reliable CSI estimation."
        )
    
    # ============================================================
    # 7. Check probe question consistency
    # ============================================================
    # Questions should become more specific as compression decreases
    question_lengths = [len(q.split()) for q in questions]
    metrics["question_lengths"] = question_lengths
    
    if all(q == questions[0] for q in questions):
        warnings.append(
            "All probe questions are identical. Consider making them "
            "more specific at lower compression levels."
        )
    
    # ============================================================
    # Final verdict
    # ============================================================
    is_valid = len(errors) == 0
    
    return CompressionValidation(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        metrics=metrics
    )


def generate_compression_report(validation: CompressionValidation) -> str:
    """Formats validation results as a readable report."""
    report = []
    report.append("=" * 60)
    report.append("COMPRESSION PROTOCOL VALIDATION")
    report.append("=" * 60)
    
    # Status
    status = "✓ VALID" if validation.is_valid else "✗ INVALID"
    report.append(f"\nStatus: {status}\n")
    
    # Errors
    if validation.errors:
        report.append("ERRORS:")
        for error in validation.errors:
            report.append(f"  ✗ {error}")
        report.append("")
    
    # Warnings
    if validation.warnings:
        report.append("WARNINGS:")
        for warning in validation.warnings:
            report.append(f"  ⚠ {warning}")
        report.append("")
    
    # Metrics
    if validation.metrics:
        report.append("METRICS:")
        for key, value in validation.metrics.items():
            report.append(f"  • {key}: {value}")
        report.append("")
    
    report.append("=" * 60)
    return "\n".join(report)


# ============================================================
# Usage example
# ============================================================

if __name__ == "__main__":
    # Example: validate the derivative concept
    example_corpus = [
        {
            "compression_level": 0,
            "text": "rate of change",
            "probe_question": "A derivative is a...",
            "expected_keywords": ["rate", "change"]
        },
        {
            "compression_level": 1,
            "text": "slope of the curve",
            "probe_question": "What is a derivative?",
            "expected_keywords": ["slope", "curve"]
        },
        {
            "compression_level": 2,
            "text": "The derivative is the slope of a function's graph.",
            "probe_question": "What does the derivative represent?",
            "expected_keywords": ["slope", "graph", "tangent"]
        }
    ]
    
    validation = validate_compression_protocol(example_corpus)
    print(generate_compression_report(validation))
