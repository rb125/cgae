"""
Concept data structures and loading functionality
"""
import json
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class CompressionStep:
    """Represents one level of compression in the protocol."""
    compression_level: int
    text: str
    probes: Dict[str, str]
    expected_keywords: List[str]

@dataclass
class Concept:
    """Represents a complete concept with compression protocol."""
    concept: str
    domain: str
    abstraction_level: int
    corpus: List[CompressionStep]

def load_concept(file_path: str) -> Concept:
    """
    Loads a concept from a JSON file.
    
    Args:
        file_path: Path to the concept JSON file
    
    Returns:
        Concept object with parsed data
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Backwards compatibility for old format
    for step in data['corpus']:
        if 'probes' not in step and 'probe_question' in step:
            step['probes'] = {'recall': step['probe_question']}
            del step['probe_question']

    corpus = [CompressionStep(**step) for step in data['corpus']]
    return Concept(
        concept=data['concept'],
        domain=data['domain'],
        abstraction_level=data['abstraction_level'],
        corpus=corpus
    )
