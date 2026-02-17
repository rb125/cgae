import os
import json

def convert_old_to_raw_format():
    """
    Convert old *_eect_results.json files (with placeholder scores)
    to new *_raw_responses.json format (raw dialogues only).
    """
    old_dir = "results/old_placeholder_scores"
    new_dir = "results/raw_responses"
    os.makedirs(new_dir, exist_ok=True)
    
    converted_count = 0
    
    for filename in os.listdir(old_dir):
        if not filename.endswith("_eect_results.json"):
            continue
        
        # Extract model name
        model_name = filename.replace("_eect_results.json", "")
        
        print(f"\n→ Converting {model_name}...")
        
        # Load old format
        old_path = os.path.join(old_dir, filename)
        with open(old_path, "r") as f:
            old_data = json.load(f)
        
        # Convert to new format
        new_data = []
        
        for dilemma_result in old_data:
            dilemma_id = dilemma_result.get("dilemma_id")
            
            # Extract domain from dilemma_id
            if "medical" in dilemma_id:
                domain = "Medical Ethics"
            elif "business" in dilemma_id:
                domain = "Business Ethics"
            elif "legal" in dilemma_id:
                domain = "Legal Ethics"
            elif "environmental" in dilemma_id:
                domain = "Environmental Ethics"
            elif "ai_tech" in dilemma_id:
                domain = "AI/Tech Ethics"
            else:
                domain = "Unknown"
            
            dilemma_responses = {
                "dilemma_id": dilemma_id,
                "domain": domain,
                "compression_responses": []
            }
            
            # Extract raw dialogue from each compression level
            raw_dialogue_results = dilemma_result.get("raw_dialogue_results", [])
            
            for comp_result in raw_dialogue_results:
                comp_level = comp_result.get("compression_level")
                dialogue_results = comp_result.get("dialogue_results", [])
                
                # Extract raw turns (prompts and responses only, ignore scores)
                turns = []
                for turn_data in dialogue_results:
                    turns.append({
                        "turn": turn_data.get("turn"),
                        "prompt": turn_data.get("prompt"),
                        "response": turn_data.get("response")
                    })
                
                dilemma_responses["compression_responses"].append({
                    "compression_level": comp_level,
                    "dialogue": turns
                })
            
            new_data.append(dilemma_responses)
        
        # Check if we got valid data
        if len(new_data) == 0:
            print(f"  ⚠ No valid data found in {filename}, skipping")
            continue
        
        # Check completeness
        complete = True
        for d in new_data:
            if len(d.get("compression_responses", [])) != 5:
                complete = False
                break
        
        if not complete:
            print(f"  ⚠ Incomplete data (expected 5 compression levels per dilemma)")
        
        # Save to new format
        new_filename = f"{model_name}_raw_responses.json"
        new_path = os.path.join(new_dir, new_filename)
        
        with open(new_path, "w") as f:
            json.dump(new_data, f, indent=2)
        
        print(f"  ✓ Converted {len(new_data)} dilemmas → {new_filename}")
        converted_count += 1
    
    print(f"\n{'='*80}")
    print(f"✓ Conversion complete: {converted_count} models converted")
    print(f"{'='*80}")
    print("\nNext step: Run jury_evaluation.py to score these responses")

if __name__ == "__main__":
    convert_old_to_raw_format()
