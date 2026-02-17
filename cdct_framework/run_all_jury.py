"""
Batch run jury evaluation on all concepts and all subject models
"""
import os
import glob
import subprocess
import json
from pathlib import Path
import sys # Import sys

# Find all concept files
concepts_dir = "concepts"
concept_files = glob.glob(os.path.join(concepts_dir, "*.json"))

# Import models config
from models_config import SUBJECT_MODELS_CONFIG

# Get all subject models
subject_models = [config["model_name"] for config in SUBJECT_MODELS_CONFIG]

print(f"\n{'='*70}")
print(f"BATCH JURY EVALUATION - ALL MODELS × ALL CONCEPTS")
print(f"{'='*70}\n")

print(f"Found {len(concept_files)} concepts:")
for cf in sorted(concept_files):
    print(f"  • {os.path.basename(cf)}")

print(f"\nFound {len(subject_models)} subject models:")
for model in subject_models:
    print(f"  • {model}")

total_runs = len(concept_files) * len(subject_models)
print(f"\nTotal runs: {total_runs}")
print(f"{'='*70}\n")

# Run all combinations
completed = 0
failed = 0

for concept_file in sorted(concept_files):
    concept_name = os.path.splitext(os.path.basename(concept_file))[0]
    
    for model in subject_models:
        completed += 1
        print(f"\n[{completed}/{total_runs}] Running: {concept_name} × {model}")
        print(f"{'-'*70}")
        
        cmd = [
            sys.executable, "main_jury.py", # Use sys.executable
            "--concept", concept_file,
            "--model", model
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=False)
            print(f"✓ Completed: {concept_name} × {model}")
        except subprocess.CalledProcessError as e:
            failed += 1
            print(f"✗ Failed: {concept_name} × {model}")
            print(f"  Error: {e}")

print(f"\n{'='*70}")
print(f"BATCH RUN COMPLETE")
print(f"{'='*70}")
print(f"Completed: {completed - failed}/{total_runs}")
print(f"Failed: {failed}/{total_runs}")
print(f"\nResults saved to: results_jury/")
print(f"{'='*70}\n")
