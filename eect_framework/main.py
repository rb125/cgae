import os
import json
from dotenv import load_dotenv
from src.models_config import SUBJECT_MODELS_CONFIG
from src.agent import create_agent
from src.evaluation import EECTEvaluator

def get_completed_models(results_dir="results/raw_responses"):
    """Check which models already have complete raw responses."""
    if not os.path.exists(results_dir):
        return set()
    
    completed = set()
    for filename in os.listdir(results_dir):
        if filename.endswith("_raw_responses.json"):
            model_name = filename.replace("_raw_responses.json", "")
            filepath = os.path.join(results_dir, filename)
            
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    # Check if we have responses for all 10 dilemmas × 5 compression levels
                    if isinstance(data, list) and len(data) == 10:
                        # Check each dilemma has 5 compression levels
                        all_complete = all(
                            len(d.get("compression_responses", [])) == 5 
                            for d in data
                        )
                        if all_complete:
                            completed.add(model_name)
                            print(f"  ✓ Found complete responses for {model_name}")
                        else:
                            print(f"  ⚠ Incomplete responses for {model_name} - will re-run")
                    else:
                        print(f"  ⚠ Incomplete responses for {model_name} - will re-run")
            except (json.JSONDecodeError, FileNotFoundError):
                print(f"  ⚠ Corrupted responses file for {model_name} - will re-run")
    
    return completed

def main():
    """
    Phase 1: Collect raw subject model responses.
    No jury scoring - that happens in Phase 2.
    """
    load_dotenv()

    print("="*80)
    print("PHASE 1: COLLECTING SUBJECT MODEL RESPONSES")
    print("="*80)
    
    # Check for existing results
    results_dir = "results/raw_responses"
    os.makedirs(results_dir, exist_ok=True)
    
    completed_models = get_completed_models(results_dir)
    
    if completed_models:
        print(f"\n✓ Resuming - skipping {len(completed_models)} completed models")
    else:
        print("\n→ Starting fresh - no completed models found")

    # Load dilemmas
    with open("dilemmas.json", "r") as f:
        dilemmas = json.load(f)

    print(f"\n→ Loaded {len(dilemmas)} dilemmas")

    compression_levels = ["c1.0", "c0.75", "c0.5", "c0.25", "c0.0"]

    # Iterate through all subject models
    for model_config in SUBJECT_MODELS_CONFIG:
        model_name = model_config.get("model_name")
        
        # Skip if already completed
        if model_name in completed_models:
            print(f"\n⏭  SKIPPING {model_name} - already completed")
            continue
        
        all_model_responses = []

        print(f"\n{'='*80}")
        print(f"▶ Collecting responses from: {model_name}")
        print(f"{'='*80}")

        try:
            agent = create_agent(model_config)
            print(f"✓ Successfully created agent for '{agent.model_name}'")
        except (ValueError, ImportError) as e:
            print(f"✗ Error creating agent for {model_name}: {e}")
            continue
        
        # Collect responses for each dilemma
        for idx, dilemma in enumerate(dilemmas, 1):
            print(f"\n  ┌─ Dilemma {idx}/{len(dilemmas)}: {dilemma['id']} ─┐")
            
            dilemma_responses = {
                "dilemma_id": dilemma["id"],
                "domain": dilemma.get("domain", "Unknown"),
                "compression_responses": []
            }
            
            for comp_level in compression_levels:
                print(f"  │   → Compression: {comp_level}")
                try:
                    evaluator = EECTEvaluator(agent)
                    # Only collect raw dialogue, no scoring
                    dialogue = evaluator.run_socratic_dialogue_raw(dilemma, comp_level)
                    
                    dilemma_responses["compression_responses"].append({
                        "compression_level": comp_level,
                        "dialogue": dialogue  # Raw turns, no scores
                    })
                    
                except Exception as e:
                    print(f"  │   ✗ ERROR at {comp_level}: {e}")
                    # Save partial results
                    if all_model_responses:
                        output_path = os.path.join(results_dir, f"{model_name}_raw_responses_PARTIAL.json")
                        with open(output_path, "w") as f:
                            json.dump(all_model_responses, f, indent=2)
                        print(f"  │   → Partial responses saved to {output_path}")
                    raise

            all_model_responses.append(dilemma_responses)
            print(f"  └─ Completed {dilemma['id']} ─┘")
        
        # Save complete raw responses
        output_path = os.path.join(results_dir, f"{model_name}_raw_responses.json")
        with open(output_path, "w") as f:
            json.dump(all_model_responses, f, indent=2)
        print(f"\n{'='*80}")
        print(f"✓ Raw responses for {model_name} saved to {output_path}")
        print(f"{'='*80}")

    print("\n" + "="*80)
    print("✓ PHASE 1 COMPLETE - All subject responses collected")
    print("="*80)
    print("\nNext step: Run jury_evaluation.py to score these responses")

if __name__ == "__main__":
    main()
