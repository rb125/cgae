"""
Context Compression Module - Implements semantic compression for DDFT protocol.

The compression algorithm uses character-level truncation as specified in the paper:
For text with W characters, compression level c provides the first W × (1 - c) characters.

Compression levels:
- c = 0.0: No compression (full text)
- c = 0.25: 25% compressed (first 75% of text)
- c = 0.5: 50% compressed (first 50% of text)
- c = 0.75: 75% compressed (first 25% of text)
- c = 1.0: Full compression (no text provided)

This tests the Epistemic Verifier's resilience under cognitive load.
"""

from typing import Dict, List
import json


class ContextCompressor:
    """
    Compresses reference text to simulate information loss and cognitive load.

    Follows the paper's specification: text[0:W×(1-c)] where W = full text length.
    """

    def __init__(self):
        """Initialize compressor."""
        pass

    def compress(self, full_text: str, compression_level: float) -> str:
        """
        Compress text using character-level truncation.

        Args:
            full_text: Complete reference text
            compression_level: Compression level (0.0 = no compression, 1.0 = full compression)

        Returns:
            Compressed text string

        Raises:
            ValueError: If compression_level not in [0.0, 1.0]
        """
        if not 0.0 <= compression_level <= 1.0:
            raise ValueError(f"Compression level must be in [0.0, 1.0], got {compression_level}")

        # Full compression = no text
        if compression_level == 1.0:
            return ""

        # No compression = full text
        if compression_level == 0.0:
            return full_text

        # Partial compression: keep first (1 - c) fraction of characters
        total_chars = len(full_text)
        chars_to_keep = int(total_chars * (1 - compression_level))

        # Ensure we keep at least some text for partial compression
        chars_to_keep = max(1, chars_to_keep)

        return full_text[:chars_to_keep]

    def compress_to_levels(
        self,
        full_text: str,
        levels: List[float] = None
    ) -> Dict[float, str]:
        """
        Compress text to multiple levels at once.

        Args:
            full_text: Complete reference text
            levels: List of compression levels (defaults to standard 5 levels)

        Returns:
            Dict mapping compression_level -> compressed_text
        """
        if levels is None:
            levels = [0.0, 0.25, 0.5, 0.75, 1.0]

        return {
            level: self.compress(full_text, level)
            for level in levels
        }

    def get_compression_stats(self, full_text: str, compressed_text: str) -> Dict:
        """
        Get statistics about compression.

        Args:
            full_text: Original text
            compressed_text: Compressed text

        Returns:
            Dict with character counts, compression ratio, etc.
        """
        original_chars = len(full_text)
        compressed_chars = len(compressed_text)
        chars_removed = original_chars - compressed_chars

        compression_ratio = (
            compressed_chars / original_chars if original_chars > 0 else 0.0
        )

        return {
            "original_chars": original_chars,
            "compressed_chars": compressed_chars,
            "chars_removed": chars_removed,
            "compression_ratio": compression_ratio,
            "effective_compression_level": 1.0 - compression_ratio
        }


class ConceptLoader:
    """
    Loads concept definitions from JSON files and provides compression.

    Concepts are stored in the concepts/ directory with full text and metadata.
    """

    def __init__(self, concepts_dir: str = "concepts"):
        """
        Initialize concept loader.

        Args:
            concepts_dir: Directory containing concept JSON files
        """
        self.concepts_dir = concepts_dir
        self.compressor = ContextCompressor()

    def load_concept(self, concept_file: str) -> Dict:
        """
        Load a concept definition from JSON file.

        Args:
            concept_file: Path to concept JSON file

        Returns:
            Dict with concept metadata and full text
        """
        with open(concept_file, 'r') as f:
            concept_data = json.load(f)

        return concept_data

    def get_full_text(self, concept_data: Dict) -> str:
        """
        Extract the full reference text from concept data.

        Args:
            concept_data: Concept dict loaded from JSON

        Returns:
            Full reference text (from c=1.0 in corpus, or last entry)
        """
        # Find the entry with compression_level = 1.0 (full text)
        corpus = concept_data.get("corpus", [])

        for entry in corpus:
            if entry.get("compression_level") == 1.0:
                return entry.get("text", "")

        # Fallback: return last entry's text
        if corpus:
            return corpus[-1].get("text", "")

        return ""

    def get_compressed_context(
        self,
        concept_data: Dict,
        compression_level: float
    ) -> str:
        """
        Get compressed context for a concept at specified compression level.

        Args:
            concept_data: Concept dict loaded from JSON
            compression_level: Desired compression level (0.0-1.0)

        Returns:
            Compressed context text
        """
        full_text = self.get_full_text(concept_data)
        return self.compressor.compress(full_text, compression_level)

    def prepare_concept_for_ddft(
        self,
        concept_file: str,
        compression_levels: List[float] = None
    ) -> Dict:
        """
        Prepare a concept for DDFT evaluation across multiple compression levels.

        Args:
            concept_file: Path to concept JSON file
            compression_levels: List of compression levels to generate

        Returns:
            Dict with concept metadata and compressed versions
        """
        if compression_levels is None:
            compression_levels = [0.0, 0.25, 0.5, 0.75, 1.0]

        concept_data = self.load_concept(concept_file)
        full_text = self.get_full_text(concept_data)

        compressed_versions = self.compressor.compress_to_levels(
            full_text,
            compression_levels
        )

        return {
            "concept": concept_data.get("concept"),
            "domain": concept_data.get("domain"),
            "full_text": full_text,
            "compressed_versions": compressed_versions,
            "abstraction_level": concept_data.get("abstraction_level"),
            "original_corpus": concept_data.get("corpus", [])
        }
