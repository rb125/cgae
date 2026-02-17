#!/usr/bin/env python3
"""
Generate all 8 CDCT-1.0 concepts using LLM-based compression.
This replaces your manually created concepts with properly compressed versions.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import shutil

# Add src to path
import sys
import os
sys.path.insert(0, 'src')

# Explicitly import from the absolute path
import importlib.util
spec = importlib.util.spec_from_file_location("llm_compression", "/home/rahul/arXiv/CDCT/cdct_framework/src/llm_compression.py")
llm_compression = importlib.util.module_from_spec(spec)
spec.loader.exec_module(llm_compression)

from agent import create_agent

# Define the 8 concepts from paper
CONCEPTS = [
    {"concept": "derivative", "domain": "mathematics", "abstraction": 4},
    {"concept": "f_equals_ma", "domain": "physics", "abstraction": 4},
    {"concept": "harm_principle", "domain": "ethics", "abstraction": 3},
    {"concept": "modus_ponens", "domain": "logic", "abstraction": 5},
    {"concept": "impressionism", "domain": "art_history", "abstraction": 2},
    {"concept": "phoneme", "domain": "linguistics", "abstraction": 4},
    {"concept": "natural_selection", "domain": "biology", "abstraction": 3},
    {"concept": "recursion", "domain": "computer_science", "abstraction": 4},
]

def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║       CDCT-1.0: LLM-Based Concept Generation                  ║")
    print("║       Generates 8 concepts with proper compression            ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    # Configuration
    MODEL = "gpt-4.1"
    DEPLOYMENT = "gpt-4.1"
    
    print("Configuration:")
    print(f"  Model:      {MODEL}")
    print(f"  Deployment: {DEPLOYMENT}")
    print(f"  Concepts:   {len(CONCEPTS)}")
    print()
    
    # Backup existing concepts
    concepts_dir = Path("concepts")
    if concepts_dir.exists() and any(concepts_dir.glob("*.json")):
        backup_dir = f"concepts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"📦 Backing up existing concepts to: {backup_dir}/")
        shutil.copytree("concepts", backup_dir)
        print("✓ Backup complete")
        print()
    
    # Ensure concepts directory exists
    concepts_dir.mkdir(exist_ok=True)
    
    # Create agent
    print("🔌 Connecting to Azure...")
    try:
        agent = create_agent(MODEL, DEPLOYMENT)
        print("✓ Connection established")
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        return 1
    
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Starting generation...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    
    # Generate each concept
    total = len(CONCEPTS)
    generated = 0
    failed = []
    
    for i, spec in enumerate(CONCEPTS, 1):
        concept = spec["concept"]
        domain = spec["domain"]
        abstraction = spec["abstraction"]
        
        output_file = f"ddft_eval/concepts/{domain}_{concept}.json"
        
        print(f"[{i}/{total}] {concept} (domain: {domain})")
        print(f"        Abstraction Level: {abstraction}")
        print(f"        Output (relative): {output_file}")
        print(f"        Output (absolute): {os.path.abspath(output_file)}")
        
        try:
            concept_json = llm_compression.generate_concept_from_scratch(
                concept=concept,
                domain=domain,
                agent=agent,
                output_path=output_file,
                abstraction_level=abstraction
            )
            
            # Verify file was created
            if Path(output_file).exists():
                print(f"        ✅ Generated successfully")
                generated += 1
            else:
                print(f"        ❌ File not created")
                failed.append((domain, concept, "File not created"))
        
        except Exception as e:
            print(f"        ❌ Error: {e}")
            failed.append((domain, concept, str(e)))
        
        print()
        
        # Rate limiting (avoid Azure throttling)
        if i < total:
            import time
            print("        ⏳ Waiting 3 seconds...")
            time.sleep(3)
            print()
    
    # Summary
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                  GENERATION COMPLETE                           ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Total concepts:  {total}")
    print(f"Generated:       {generated}")
    print(f"Failed:          {len(failed)}")
    print()
    
    if failed:
        print("Failed concepts:")
        for domain, concept, error in failed:
            print(f"  • {domain}/{concept}: {error}")
        print()
    
    if generated == total:
        print("✅ All concepts generated successfully!")
        print()
        print("Next steps:")
        print("  1. Validate concepts:")
        print("     python -c \"from src.compression_validator import *; ...\"")
        print()
        print("  2. Run a test experiment:")
        print("     python main.py --concept concepts/physics_f_equals_ma.json \\")
        print("                    --model gpt-4.1 --deployment '4.1'")
        print()
        print("  3. Run full benchmark:")
        print("     bash run_benchmark.sh")
        return 0
    else:
        print("⚠️  Some concepts failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
