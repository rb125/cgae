"""
Prompting module - Creates compression-aware prompts
"""

def create_compression_aware_prompt(
    context: str,
    question: str,
    compression_level: int,
    max_compression: int
) -> str:
    """
    Creates prompt that enforces compression constraints.
    
    The prompt explicitly tells the model to use ONLY the information
    provided in the compressed context, not draw on memorized knowledge.
    
    Args:
        context: The compressed text available to the model
        question: The probe question
        compression_level: Current level (0 = most compressed)
        max_compression: Maximum level in protocol
    
    Returns:
        Complete prompt string
    """
    compression_ratio = 1 - (compression_level / max_compression)
    
    if compression_ratio > 0.8:  # Very high compression (level 0-1)
        constraint = """
CRITICAL: You have minimal information (2-5 words). Answer using ONLY these words.
Do NOT elaborate beyond what's given. Keep response under 20 words."""
    
    elif compression_ratio > 0.5:  # Medium compression (level 2-3)
        constraint = """
IMPORTANT: Answer using ONLY the information provided above.
Keep your response brief (2-3 sentences max). Do not add details
not present in the context."""
    
    else:  # Low compression (level 4+)
        constraint = """
Using the context above, provide a clear explanation.
You may elaborate on the concepts mentioned."""
    
    prompt = f"""You are being tested on comprehension with limited information.

AVAILABLE INFORMATION:
{context}

{constraint}

QUESTION: {question}

ANSWER:"""
    
    return prompt


def create_few_shot_prompt(
    context: str,
    question: str,
    compression_level: int
) -> str:
    """
    Few-shot examples demonstrating desired behavior at each compression level.
    
    Args:
        context: The compressed text
        question: The probe question
        compression_level: Current level (0 = highest compression)
    
    Returns:
        Prompt with examples
    """
    if compression_level == 0:
        examples = """Examples of good answers with minimal context:

Context: "acceleration"
Q: What is force?
A: "mass times acceleration"

Context: "base times height"  
Q: Area of triangle?
A: "half of base times height"

Your turn:
"""
    elif compression_level == 1:
        examples = """Example:
Context: "slope of the curve"
Q: What is a derivative?
A: "The derivative represents the slope of a curve at a point"

Your turn:
"""
    else:
        examples = ""
    
    return f"""{examples}
Context: {context}
Question: {question}

Answer:"""


def create_simple_prompt(context: str, question: str) -> str:
    """
    Simple prompt without explicit constraints.
    
    Use this to test if models naturally respect compression
    without being told to.
    """
    return f"""Context: {context}

Question: {question}

Answer:"""


def create_minimal_prompt(context: str, question: str) -> str:
    """
    Ablation prompt: Remove RLHF helpfulness cues.
    
    Tests if "be helpful" alignment signal is the cause of CC failure at c=0.5.
    Removes social framing ("You are being tested") that might trigger
    learned alignment behaviors that conflict with constraint adherence.
    
    Args:
        context: The compressed text
        question: The probe question
    
    Returns:
        Minimal prompt without helpfulness cues
    """
    prompt = f"""AVAILABLE INFORMATION:
{context}

IMPORTANT: Answer using ONLY the information provided above.
Keep your response brief (2-3 sentences max). Do not add details
not present in the context.

QUESTION: {question}

ANSWER:"""
    
    return prompt