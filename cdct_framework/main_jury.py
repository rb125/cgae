"""
Main entry point for CDCT experiments with jury-based evaluation
Runs subject model with consensus evaluation from 3 judges
"""
import argparse
import json
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import agent as agent_loader
from src.experiment_jury import run_experiment_with_jury, compare_jury_strategies
from src.compression_validator import validate_compression_protocol
from models_config import SUBJECT_MODELS_CONFIG, JURY_MODELS_CONFIG


def main():
    parser = argparse.ArgumentParser(
        description="Run CDCT experiments with jury-based evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run jury evaluation
  python main_jury.py --concept concepts/derivative.json --model gpt-4.1
  
  # Compare prompt strategies with jury
  python main_jury.py --concept concepts/derivative.json --model gpt-4.1 --compare-strategies
  
  # Validate compression protocol only
  python main_jury.py --concept concepts/derivative.json --validate-only
        """
    )
    
    parser.add_argument("--concept", type=str, required=True, 
                       help="Path to the concept JSON file")
    parser.add_argument("--model", type=str,
                       help="Name of the subject model to test")
    
    # Experiment options
    parser.add_argument("--prompt-strategy", type=str, 
                       default="compression_aware",
                       choices=["simple", "compression_aware", "few_shot"],
                       help="Prompting strategy to use")
    parser.add_argument("--ablation-type", type=str,
                       choices=["baseline", "no_helpfulness"],
                       default=None,
                       help="Prompt variant for ablation study (RLHF hypothesis)")
    parser.add_argument("--compare-strategies", action="store_true",
                       help="Compare all prompt strategies with jury evaluation")
    parser.add_argument("--validate-only", action="store_true",
                       help="Only validate compression protocol, don't run experiment")
    parser.add_argument("--output-dir", type=str, default="results_jury",
                       help="Directory to save results")
    parser.add_argument("--quiet", action="store_true",
                       help="Suppress verbose output")
    
    args = parser.parse_args()
    
    # Validate compression protocol if requested
    if args.validate_only or not args.model:
        print(f"\n{'='*70}")
        print("VALIDATING COMPRESSION PROTOCOL")
        print(f"{'='*70}\n")
        
        with open(args.concept, 'r') as f:
            data = json.load(f)
        
        validation = validate_compression_protocol(data['corpus'])
        
        print(f"Status: {'✓ VALID' if validation['valid'] else '✗ INVALID'}")
        print(f"\nText lengths: {validation['text_lengths']}")
        if validation.get('compression_ratio'):
            print(f"Compression ratio: {validation['compression_ratio']:.1f}x")
        
        if validation['errors']:
            print("\nERRORS:")
            for error in validation['errors']:
                print(f"  ✗ {error}")
        
        if validation['warnings']:
            print("\nWARNINGS:")
            for warning in validation['warnings']:
                print(f"  ⚠ {warning}")
        
        if args.validate_only:
            return
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Build API keys dictionary from environment
    api_keys = {
        "AZURE_API_KEY": os.getenv("AZURE_API_KEY"),
        "AZURE_OPENAI_API_ENDPOINT": os.getenv("AZURE_OPENAI_API_ENDPOINT"),
        "DDFT_MODELS_ENDPOINT": os.getenv("DDFT_MODELS_ENDPOINT"),
        "AZURE_ANTHROPIC_API_ENDPOINT": os.getenv("AZURE_ANTHROPIC_API_ENDPOINT"),
    }
    
    # Initialize subject model
    if not args.model:
        print("ERROR: --model is required for running experiments")
        return
    
    try:
        # Find subject model config
        subject_config = None
        for config in SUBJECT_MODELS_CONFIG:
            if config["model_name"].lower() == args.model.lower():
                subject_config = config
                break
        
        if not subject_config:
            print(f"ERROR: Subject model '{args.model}' not found in SUBJECT_MODELS_CONFIG")
            return
        
        # Create subject agent
        subject_agent = agent_loader.create_agent(subject_config, api_keys)
        
        # Initialize jury members
        print(f"\n{'='*70}")
        print("INITIALIZING JURY MEMBERS")
        print(f"{'='*70}\n")
        
        jury_agents = {}
        jury_models = ["claude-opus-4-1-2", "gpt-5.1", "deepseek-v3.1"]
        
        for jury_model in jury_models:
            # Find jury model config
            jury_config = None
            for config in JURY_MODELS_CONFIG:
                if config["model_name"].lower() == jury_model.lower():
                    jury_config = config
                    break
            
            if not jury_config:
                print(f"⚠ WARNING: Jury model '{jury_model}' not found in JURY_MODELS_CONFIG")
                continue
            
            try:
                jury_agent = agent_loader.create_agent(jury_config, api_keys)
                jury_agents[jury_model] = jury_agent
                print(f"✓ Initialized {jury_model}")
            except Exception as e:
                print(f"✗ Failed to initialize {jury_model}: {e}")
        
        if not jury_agents or len(jury_agents) < 2:
            print("ERROR: Need at least 2 jury members. Check JURY_MODELS_CONFIG and API credentials.")
            return
        
        print(f"\nJury ready: {list(jury_agents.keys())}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    concept_name = os.path.splitext(os.path.basename(args.concept))[0]
    
    # Run experiments
    if args.compare_strategies:
        print(f"\n{'#'*70}")
        print("COMPARING PROMPT STRATEGIES WITH JURY EVALUATION")
        print(f"{'#'*70}\n")
        
        results = compare_jury_strategies(args.concept, subject_agent, jury_agents)
        
        # Save comparison
        output_path = os.path.join(
            args.output_dir,
            f"jury_comparison_{concept_name}_{args.model.replace('/', '_')}.json"
        )
        
        comparison_summary = {
            "concept": concept_name,
            "subject_model": args.model,
            "jury_models": list(jury_agents.keys()),
            "evaluation_system": "jury",
            "strategies": {
                strategy: {
                    "CSI": result["analysis"]["CSI"],
                    "mean_score": result["analysis"]["mean_score"],
                    "mean_agreement": result["analysis"]["mean_agreement"],
                    "decay_direction": result["analysis"]["decay_direction"]
                }
                for strategy, result in results.items()
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(comparison_summary, f, indent=2)
        
        # Save full results
        for strategy, result in results.items():
            full_path = os.path.join(
                args.output_dir,
                f"jury_results_{concept_name}_{args.model.replace('/', '_')}_{strategy}.json"
            )
            with open(full_path, 'w') as f:
                json.dump(result, f, indent=2)
        
        print(f"\nResults saved to {args.output_dir}/")
        
    else:
        # Run single experiment with jury
        ablation_suffix = ""
        if args.ablation_type == "no_helpfulness":
            ablation_suffix = "_no_helpfulness"
        
        results = run_experiment_with_jury(
            concept_path=args.concept,
            subject_agent=subject_agent,
            jury_agents=jury_agents,
            prompt_strategy=args.prompt_strategy,
            ablation_type=args.ablation_type if args.ablation_type != "baseline" else None,
            verbose=not args.quiet
        )
        
        # Save results
        output_filename = (
            f"jury_results_{concept_name}_{args.model.replace('/', '_')}_"
            f"{args.prompt_strategy}{ablation_suffix}.json"
        )
        output_path = os.path.join(args.output_dir, output_filename)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
