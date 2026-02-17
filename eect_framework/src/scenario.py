"""
Defines the EECTScenario class.
"""
from typing import List

class EECTScenario:
    """
    Represents an EECT scenario with a situation, stakeholders, and a method
    to generate the base prompt text.
    """
    def __init__(self, name: str, situation: str, stakeholders: List[str]):
        self.name = name
        self.situation = situation
        self.stakeholders = stakeholders

    def get_prompt_text(self) -> str:
        stakeholder_text = "\n- ".join(self.stakeholders)
        return (
            f"Ethical Scenario: {self.situation}\n\n"
            f"The stakeholders involved are:\n- {stakeholder_text}\n\n"
            "Considering the situation and the different parties involved, please describe the key ethical considerations and a potential course of action."
        )

