"""
Batch runner for CDCT experiments using configuration-driven model setup.
Iterates over all concept JSON files and runs experiments for each subject model.
Skips already processed concepts.
"""

import os
import subprocess
import argparse
from pathlib import Path
from dotenv import load_dotenv
import sys # Import sys

# Load environment variables
load_dotenv()

# Import models config
from models_config import SUBJECT_MODELS_CONFIG, JURY_MODELS_CONFIG

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run CDCT experiments for all concepts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all.py --model gpt-5
  python run_all.py --model phi-4 --results-dir results_new
  python run_all.py --models-list subject  # Run all subject models sequentially
        """
    )
    parser.add_argument("--model", type=str,
                        help="Single model name to run (e.g., gpt-5, phi-4)")
    parser.add_argument("--model-name", type=str, dest="model_name",
                        help="Alias for --model")
    parser.add_argument("--concepts-dir", type=str, default="concepts",
                        help="Directory containing concept JSON files")
    parser.add_argument("--results-dir", type=str, default="results",
                        help="Directory to store experiment results")
    parser.add_argument("--prompt-strategy", type=str, default="compression_aware",
                        help="Prompting strategy to use")
    parser.add_argument("--evaluation-mode", type=str, default="balanced",
                        help="Evaluation mode (strict | balanced | lenient)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose output from main.py")
    parser.add_argument("--models-list", type=str, choices=["subject", "jury", "all"],
                        help="Run all models from specified list")
    return parser.parse_args()

def already_done(concept_name: str, model: str, results_dir: Path) -> bool:
    """Check if results already exist for a given concept + model."""
    pattern = f"results_{concept_name}_{model.replace('/', '_')}_"
    for file in results_dir.iterdir():
        if file.name.startswith(pattern) and file.name.endswith(".json"):
            return True
    return False

def get_model_config(model_name: str) -> dict:
    """Get configuration dict for a model by name."""
    all_configs = SUBJECT_MODELS_CONFIG + JURY_MODELS_CONFIG
    for config in all_configs:
        if config["model_name"].lower() == model_name.lower():
            return config
    raise ValueError(f"Model not found in config: {model_name}")

def run_concept(concept_path: Path, model_name: str, args):
    """Run main.py for a single concept with config-driven approach."""
    concept_name = concept_path.stem
    
    # Clean model name for file naming
    clean_model_name = model_name.replace('/', '_').replace(' ', '_').lower()
    
    if already_done(concept_name, clean_model_name, Path(args.results_dir)):
        print(f"✅ Skipping {concept_name} / {model_name} — already has results.")
        return
    
    print(f"\n🚀 Running experiment for: {concept_name} with {model_name}")
    cmd = [
        sys.executable, "main.py", # Use sys.executable instead of "python"
        "--concept", str(concept_path),
        "--model", model_name,
        "--prompt-strategy", args.prompt_strategy,
        "--evaluation-mode", args.evaluation_mode,
        "--output-dir", args.results_dir,
    ]
    if args.quiet:
        cmd.append("--quiet")

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Completed: {concept_name} / {model_name}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running {concept_name} with {model_name}: {e}")

def main():
    args = parse_args()
    
    # Determine which model(s) to run
    if args.models_list:
        # Run all models from a list
        if args.models_list == "subject":
            models = [config["model_name"] for config in SUBJECT_MODELS_CONFIG]
        elif args.models_list == "jury":
            models = [config["model_name"] for config in JURY_MODELS_CONFIG]
        else:  # all
            models = [config["model_name"] for config in SUBJECT_MODELS_CONFIG + JURY_MODELS_CONFIG]
        
        # Batch run all concepts for each model
        for model_name in models:
            print(f"\n{'='*70}")
            print(f"Running all concepts for model: {model_name}")
            print(f"{'='*70}")
            
            concepts_dir = Path(args.concepts_dir)
            results_dir = Path(args.results_dir)
            results_dir.mkdir(exist_ok=True)
            
            concept_files = sorted(concepts_dir.glob("*.json"))
            if not concept_files:
                print("No concept files found.")
                return
            
            for concept_path in concept_files:
                run_concept(concept_path, model_name, args)
    
    elif args.model or args.model_name:
        # Run a single model
        model_name = args.model or args.model_name
        
        # Validate model exists in config
        try:
            config = get_model_config(model_name)
            print(f"\nModel config found: {model_name}")
            print(f"  Provider: {config['provider']}")
            print(f"  Deployment: {config['deployment_name']}")
        except ValueError as e:
            print(f"ERROR: {e}")
            return
        
        concepts_dir = Path(args.concepts_dir)
        results_dir = Path(args.results_dir)
        results_dir.mkdir(exist_ok=True)

        concept_files = sorted(concepts_dir.glob("*.json"))
        if not concept_files:
            print("No concept files found.")
            return

        print(f"\nFound {len(concept_files)} concept files.")
        print(f"Model: {model_name}")
        print("=" * 70)

        for concept_path in concept_files:
            run_concept(concept_path, model_name, args)
    
    else:
        print("ERROR: Specify either --model <name> or --models-list <subject|jury|all>")
        print("Example: python run_all.py --model gpt-5")
        print("Example: python run_all.py --models-list subject")
        return

    print("\n🎉 All experiments complete!")

if __name__ == "__main__":
    main()
