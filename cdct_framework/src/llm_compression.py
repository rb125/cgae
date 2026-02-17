"""
LLM-Powered Compression Protocol Generator

Creates CDCT-compliant compression protocols by progressively distilling
concepts from full explanations down to minimal representations.
"""
from typing import List, Dict, Any, Tuple
import json
from dataclasses import dataclass, asdict


@dataclass
class CompressionLevel:
    """Represents one level in the compression protocol."""
    compression_level: float
    text: str
    probe_question: str
    expected_keywords: List[str]
    word_count: int


class LLMCompressionGenerator:
    """
    Generates compression protocols using an LLM to progressively distill concepts.
    """
    
    def __init__(self, agent):
        """
        Args:
            agent: An Agent instance (e.g., AzureOpenAIAgent) for making LLM calls
        """
        self.agent = agent
    
    def generate_compression_protocol(
        self,
        concept: str,
        domain: str,
        full_explanation: str,
        num_levels: int = 5,
        abstraction_level: int = 3
    ) -> Dict[str, Any]:
        """
        Generate a complete compression protocol for a concept.
        
        Args:
            concept: The concept name (e.g., "derivative")
            domain: The domain (e.g., "mathematics")
            full_explanation: Full, detailed explanation of the concept
            num_levels: Number of compression levels (default: 5)
            abstraction_level: Concept abstraction level 1-5 (default: 3)
        
        Returns:
            Complete concept JSON ready to save
        """
        print(f"\n{'='*70}")
        print(f"Generating Compression Protocol for: {concept}")
        print(f"Domain: {domain}")
        print(f"{'='*70}\n")
        
        # Generate all compression levels
        levels = []
        
        # Level 0: Single keyword/phrase (most compressed)
        level_0 = self._generate_level_0(concept, domain, full_explanation)
        levels.append(level_0)
        print(f"✓ Level 0: {level_0.word_count} words")
        
        # Level 1: Short phrase (2-5 words)
        level_1 = self._generate_level_1(concept, domain, full_explanation, level_0)
        levels.append(level_1)
        print(f"✓ Level 1: {level_1.word_count} words")
        
        # Level 2: Brief explanation (15-30 words)
        level_2 = self._generate_level_2(concept, domain, full_explanation, level_1)
        levels.append(level_2)
        print(f"✓ Level 2: {level_2.word_count} words")
        
        # Level 3: Medium explanation (40-80 words)
        level_3 = self._generate_level_3(concept, domain, full_explanation, level_2)
        levels.append(level_3)
        print(f"✓ Level 3: {level_3.word_count} words")
        
        # Level 4: Full explanation (original or expanded)
        level_4 = self._generate_level_4(concept, domain, full_explanation)
        levels.append(level_4)
        print(f"✓ Level 4: {level_4.word_count} words")
        
        # Validate monotonicity
        self._validate_protocol(levels)
        
        # Build concept JSON
        concept_json = {
            "concept": concept,
            "domain": domain,
            "abstraction_level": abstraction_level,
            "corpus": [
                {
                    "compression_level": level.compression_level,
                    "text": level.text,
                    "probe_question": level.probe_question,
                    "expected_keywords": level.expected_keywords
                }
                for level in levels
            ]
        }
        
        print(f"\n{'='*70}")
        print("Compression Protocol Generated Successfully!")
        print(f"Compression Ratio: {level_4.word_count / level_0.word_count:.1f}x")
        print(f"{'='*70}\n")
        
        return concept_json
    
    def _generate_level_0(self, concept: str, domain: str, full_text: str) -> CompressionLevel:
        """Generate most compressed form (1-3 words)."""
        
        prompt = f"""You are creating a compression protocol for testing AI comprehension.

Concept: {concept}
Domain: {domain}

Task: Extract the ABSOLUTE MINIMUM representation - just 1-3 words that capture the core essence.

Full explanation:
{full_text}

Provide ONLY the minimal phrase (1-3 words), nothing else.

Example formats:
- For "photosynthesis": "light energy conversion"
- For "recursion": "self-reference"
- For "derivative": "rate of change"

Your 1-3 word phrase:"""

        response = self.agent.query(prompt).strip()
        keywords = self._extract_keywords(response, max_keywords=3)
        
        return CompressionLevel(
            compression_level=0.0,
            text=response,
            probe_question=f"What is {concept}?",
            expected_keywords=keywords,
            word_count=len(response.split())
        )
    
    def _generate_level_1(self, concept: str, domain: str, full_text: str, 
                         level_0: CompressionLevel) -> CompressionLevel:
        """Generate short phrase (3-6 words)."""
        
        prompt = f"""You are creating a compression protocol for testing AI comprehension.

Concept: {concept}
Domain: {domain}

Previous compression (Level 0): {level_0.text}

Task: Expand slightly to a 3-6 word phrase that adds ONE key detail.

Rules:
- Must be 3-6 words only
- Should naturally expand on: {level_0.text}
- Add exactly ONE new piece of information
- Keep it concrete and specific

Example progressions:
- "rate of change" → "instantaneous rate of change"
- "self-reference" → "function calls itself"
- "light energy" → "light energy to chemical"

Your 3-6 word phrase:"""

        response = self.agent.query(prompt).strip()
        keywords = self._extract_keywords(response, max_keywords=4)
        
        return CompressionLevel(
            compression_level=0.25,
            text=response,
            probe_question=f"Describe {concept} briefly",
            expected_keywords=keywords,
            word_count=len(response.split())
        )
    
    def _generate_level_2(self, concept: str, domain: str, full_text: str,
                         level_1: CompressionLevel) -> CompressionLevel:
        """Generate brief explanation (15-30 words)."""
        
        prompt = f"""You are creating a compression protocol for testing AI comprehension.

Concept: {concept}
Domain: {domain}

Previous compression (Level 1): {level_1.text}

Task: Expand to a 15-30 word explanation that adds context and relationships.

Rules:
- Must be 15-30 words (strict)
- Should be ONE or TWO sentences
- Builds on: {level_1.text}
- Add WHY it matters or HOW it works
- Keep language simple and direct

Your 15-30 word explanation:"""

        response = self.agent.query(prompt).strip()
        # Enforce word count
        words = response.split()
        if len(words) > 35:
            response = ' '.join(words[:30])
        
        keywords = self._extract_keywords(response, max_keywords=6)
        
        return CompressionLevel(
            compression_level=0.5,
            text=response,
            probe_question=f"Explain {concept}",
            expected_keywords=keywords,
            word_count=len(response.split())
        )
    
    def _generate_level_3(self, concept: str, domain: str, full_text: str,
                         level_2: CompressionLevel) -> CompressionLevel:
        """Generate medium explanation (40-80 words)."""
        
        prompt = f"""You are creating a compression protocol for testing AI comprehension.

Concept: {concept}
Domain: {domain}

Previous compression (Level 2): {level_2.text}

Task: Expand to a 40-80 word explanation with details and examples.

Rules:
- Must be 40-80 words (strict)
- Should be 2-4 sentences
- Builds on: {level_2.text}
- Add details, examples, or applications
- Include key terminology from the field
- Maintain clarity and precision

Your 40-80 word explanation:"""

        response = self.agent.query(prompt).strip()
        # Enforce word count
        words = response.split()
        if len(words) > 90:
            response = ' '.join(words[:80])
        elif len(words) < 35:
            # Too short, try to expand
            response = self._expand_text(concept, response, target_words=50)
        
        keywords = self._extract_keywords(response, max_keywords=8)
        
        return CompressionLevel(
            compression_level=0.75,
            text=response,
            probe_question=f"Provide a detailed explanation of {concept}",
            expected_keywords=keywords,
            word_count=len(response.split())
        )
    
    def _generate_level_4(self, concept: str, domain: str, full_text: str) -> CompressionLevel:
        """Generate full explanation (100+ words)."""
        
        # Use original full text if it's good, or enhance it
        word_count = len(full_text.split())
        
        if word_count >= 100:
            response = full_text
        else:
            # Expand to full explanation
            prompt = f"""You are creating a compression protocol for testing AI comprehension.

Concept: {concept}
Domain: {domain}

Starting point:
{full_text}

Task: Create a comprehensive, textbook-quality explanation (100-150 words).

Requirements:
- 100-150 words (strict)
- Include: definition, explanation, examples, applications
- Use proper terminology
- Maintain technical accuracy
- Make it self-contained and complete

Your comprehensive explanation:"""
            
            response = self.agent.query(prompt).strip()
        
        keywords = self._extract_keywords(response, max_keywords=12)
        
        return CompressionLevel(
            compression_level=1.0,
            text=response,
            probe_question=f"Provide a comprehensive explanation of {concept}",
            expected_keywords=keywords,
            word_count=len(response.split())
        )
    
    def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """Extract key terms from text using LLM."""
        
        prompt = f"""Extract the {max_keywords} most important keywords from this text.

Text: {text}

Rules:
- Extract ONLY {max_keywords} keywords
- Use single words or short phrases (2-3 words max)
- Focus on core concepts, not common words
- Output as comma-separated list ONLY

Keywords:"""

        response = self.agent.query(prompt).strip()
        keywords = [kw.strip().lower() for kw in response.split(',')]
        return keywords[:max_keywords]
    
    def _expand_text(self, concept: str, text: str, target_words: int) -> str:
        """Expand text to reach target word count."""
        
        prompt = f"""Expand this explanation to approximately {target_words} words while maintaining accuracy.

Concept: {concept}
Current text: {text}

Expanded version ({target_words} words):"""

        return self.agent.query(prompt).strip()
    
    def _validate_protocol(self, levels: List[CompressionLevel]):
        """Validate that compression protocol is monotonic."""
        
        word_counts = [level.word_count for level in levels]
        
        for i in range(1, len(word_counts)):
            if word_counts[i] <= word_counts[i-1]:
                print(f"⚠ WARNING: Non-monotonic word counts at level {i}")
                print(f"  Level {i-1}: {word_counts[i-1]} words")
                print(f"  Level {i}: {word_counts[i]} words")
        
        ratio = word_counts[-1] / word_counts[0] if word_counts[0] > 0 else 0
        if ratio < 5:
            print(f"⚠ WARNING: Low compression ratio ({ratio:.1f}x)")


def generate_concept_from_scratch(
    concept: str,
    domain: str,
    agent,
    output_path: str = None,
    abstraction_level: int = 3  # ADD THIS LINE
) -> Dict[str, Any]:
    """
    Generate a complete compression protocol starting from just concept name.
    
    Args:
        concept: Concept name (e.g., "photosynthesis")
        domain: Domain (e.g., "biology")
        agent: LLM agent for generation
        output_path: Optional path to save JSON
        abstraction_level: Concept abstraction level 1-5 (default: 3)  # ADD THIS
    
    Returns:
        Complete concept JSON
    """
    # First, generate a full explanation
    prompt = f"""Provide a comprehensive, textbook-quality explanation of {concept} in the domain of {domain}.

Requirements:
- 100-150 words
- Include definition, key principles, and applications
- Use proper terminology
- Be technically accurate

Explanation:"""
    
    full_explanation = agent.query(prompt).strip()
    
    # Now generate compression protocol
    generator = LLMCompressionGenerator(agent)
    concept_json = generator.generate_compression_protocol(
        concept=concept,
        domain=domain,
        full_explanation=full_explanation,
        num_levels=5,
        abstraction_level=abstraction_level  # ADD THIS LINE
    )
    
    # Save if path provided
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(concept_json, f, indent=2)
        print(f"✓ Saved to: {output_path}")
    
    return concept_json

# ============================================================
# CLI Interface
# ============================================================

if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    
    from agent import create_agent
    
    print("CDCT LLM-Powered Compression Generator")
    print("="*70)
    
    # Example usage
    concept = input("Concept name: ")
    domain = input("Domain: ")
    model = input("Model (e.g., gpt-4.1): ")
    deployment = input("Deployment name: ")
    
    agent = create_agent(model, deployment)
    
    output_path = f"concepts/{domain}_{concept}.json"
    
    concept_json = generate_concept_from_scratch(
        concept=concept,
        domain=domain,
        agent=agent,
        output_path=output_path
    )
    
    print("\n✓ Compression protocol generated!")
    print(f"✓ Saved to: {output_path}")
