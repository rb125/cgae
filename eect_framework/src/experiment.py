"""
Defines the EECTExperiment class for running evaluations.
"""
from typing import List, Dict
from src.agent import Agent
from src.scenario import EECTScenario
from src.compression import compress_prompt

class EECTExperiment:
    """Orchestrates running an EECT evaluation for a given model and scenario."""

    def __init__(self, agent: Agent):
        """
        Initializes the experiment with a specific agent. 
        
        Args:
            agent: An instance of a class that inherits from Agent.
        """
        self.agent = agent
        self.results = []

    def run(self, scenario: EECTScenario, compression_levels: List[float]) -> List[Dict]:
        """
        Runs the experiment for a single scenario across multiple compression levels.

        Args:
            scenario: An EECTScenario object.
            compression_levels: A list of floats (0.0 to 1.0) representing the
                              compression levels to test.

        Returns:
            A list of dictionaries, where each dictionary is a result for one
            compression level.
        """
        print(f"\n--- Running Experiment for Model: '{self.agent.model_name}' on Scenario: '{scenario.name}' ---")
        base_prompt_text = scenario.get_prompt_text()

        for level in compression_levels:
            print(f"  Testing compression level: {level}...")
            
            # 1. Generate the compressed prompt for the current level
            compressed_prompt = compress_prompt(base_prompt_text, level)

            # 2. Get the model's response
            messages = [{"role": "user", "content": compressed_prompt}]
            
            try:
                response = self.agent.chat(messages)
                
                # 3. Store the result
                result = {
                    "model_name": self.agent.model_name,
                    "scenario": scenario.name,
                    "compression_level": level,
                    "prompt": compressed_prompt,
                    "response": response,
                    "error": None
                }
                self.results.append(result)
                print(f"    Response received successfully.")

            except Exception as e:
                print(f"    ERROR: API call failed for compression level {level}: {e}")
                result = {
                    "model_name": self.agent.model_name,
                    "scenario": scenario.name,
                    "compression_level": level,
                    "prompt": compressed_prompt,
                    "response": None,
                    "error": str(e)
                }
                self.results.append(result)

        print("--- Experiment Run Complete ---")
        return self.results
