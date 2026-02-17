"""
Debug utilities for printing formatted output.
"""

def print_debug_panel(subject_model: str, turn: str, compression: float, question: str, response: str, evaluation: dict):
    """
    Prints a formatted debug panel to the console.
    """
    panel_width = 100
    separator = "=" * panel_width

    print(f"\n{separator}")
    print(f"DEBUG PANEL - {subject_model} - {turn} (c={compression})".center(panel_width))
    print(separator)
    print(f"QUESTION:\n{question}\n")
    print(f"RESPONSE:\n{response}\n")
    print(f"EVALUATION: {evaluation}")
    print(separator)
