"""
Smart batch run jury evaluation - skips already completed experiments
Supports ablation studies with --ablation-type flag
"""
import os
import glob
import subprocess
import json
import sys
import argparse
from pathlib import Path

# Parse command line arguments
parser = argparse.ArgumentParser(description="Smart batch jury evaluation with ablation support")
parser.add_argument("--ablation-type", type=str, 
                   choices=["baseline", "no_helpfulness"],
                   default=None,
                   help="Ablation type: baseline for standard, no_helpfulness for RLHF ablation")
parser.add_argument("--output-dir", type=str, default="results_jury",
                   help="Output directory for results")
args = parser.parse_args()

# Find all concept files
concepts_dir = "concepts"
concept_files = glob.glob(os.path.join(concepts_dir, "*.json"))

# Import models config
from models_config import SUBJECT_MODELS_CONFIG

# Get all subject models
subject_models = [config["model_name"] for config in SUBJECT_MODELS_CONFIG]

# Load existing results to check what's done
results_dir = Path(args.output_dir)
existing_results = set()
if results_dir.exists():
    for result_file in results_dir.glob("*.json"):
        # Parse filename: jury_results_{concept}_{model}_compression_aware.json
        # or jury_results_{concept}_{model}_compression_aware_no_helpfulness.json
        existing_results.add(result_file.name)

print(f"\n{'='*70}")
print(f"SMART BATCH JURY EVALUATION - Skip existing, run missing")
if args.ablation_type:
    print(f"ABLATION TYPE: {args.ablation_type}")
print(f"{'='*70}\n")

print(f"Found {len(concept_files)} concepts")
print(f"Found {len(subject_models)} subject models")
print(f"Found {len(existing_results)} existing results")
if args.ablation_type:
    print(f"Output directory: {args.output_dir}\n")
else:
    print()

# Determine what to run
to_run = []
for concept_file in sorted(concept_files):
    concept_name = os.path.splitext(os.path.basename(concept_file))[0]
    
    for model in subject_models:
        # Build expected filename based on ablation type
        if args.ablation_type == "no_helpfulness":
            expected_filename = f"jury_results_{concept_name}_{model.replace('/', '_')}_compression_aware_no_helpfulness.json"
        else:
            expected_filename = f"jury_results_{concept_name}_{model.replace('/', '_')}_compression_aware.json"
        
        if expected_filename not in existing_results:
            to_run.append((concept_file, concept_name, model))

print(f"Total combinations: {len(concept_files) * len(subject_models)}")
print(f"Already completed: {len(existing_results)}")
print(f"Need to run: {len(to_run)}\n")

if not to_run:
    print("✓ All experiments already completed!")
    print(f"{'='*70}\n")
else:
    print(f"Running {len(to_run)} missing experiments:")
    print(f"{'='*70}\n")
    
    completed = 0
    failed = 0
    
    for concept_file, concept_name, model in to_run:
        completed += 1
        print(f"\n[{completed}/{len(to_run)}] Running: {concept_name} × {model}")
        print(f"{'-'*70}")
        
        cmd = [
            sys.executable, "main_jury.py",
            "--concept", concept_file,
            "--model", model,
            "--output-dir", args.output_dir
        ]
        
        # Add ablation flag if specified
        if args.ablation_type:
            cmd.extend(["--ablation-type", args.ablation_type])
        
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
    print(f"Newly completed: {completed - failed}/{len(to_run)}")
    print(f"Failed: {failed}/{len(to_run)}")
    print(f"Total in results_jury: {len(existing_results) + (completed - failed)}")
    print(f"{'='*70}\n")
