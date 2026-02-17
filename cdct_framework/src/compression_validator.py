"""
Compression protocol validation utilities
"""
from typing import List, Dict, Any

def validate_compression_protocol(corpus: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates compression protocol meets CDCT requirements.
    
    Args:
        corpus: List of compression steps from a concept JSON
    
    Returns:
        Dict with validation results (valid, errors, warnings, metrics)
    """
    if not corpus:
        return {"valid": False, "errors": ["Empty corpus"], "warnings": [], "text_lengths": []}
    
    errors = []
    warnings = []
    
    # Check ordering
    levels = [s['compression_level'] for s in corpus]
    if levels != sorted(levels):
        errors.append(f"Levels not ordered: {levels}")
    
    # Check monotonic information increase
    text_lengths = [len(s['text'].split()) for s in corpus]
    for i in range(1, len(text_lengths)):
        if text_lengths[i] < text_lengths[i-1]:
            errors.append(f"Non-monotonic at level {levels[i]}: {text_lengths}")
            break
    
    # Check compression ratio
    if text_lengths[0] > 0:
        ratio = text_lengths[-1] / text_lengths[0]
        if ratio < 5:
            warnings.append(f"Low compression ratio: {ratio:.1f}x (recommend 5-10x)")
    
    # Check resolution
    if len(corpus) < 5:
        warnings.append(f"Only {len(corpus)} levels (recommend 5+)")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "text_lengths": text_lengths,
        "compression_ratio": text_lengths[-1] / text_lengths[0] if text_lengths[0] > 0 else None
    }
