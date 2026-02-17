"""
Main entry point for CDCT experiments
Configuration-driven model setup based on DDFT approach
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
from src.experiment import run_experiment, compare_strategies, quick_test
from src.compression_validator import validate_compression_protocol
from src.analysis import analyze_multi_concept
from models_config import SUBJECT_MODELS_CONFIG, JURY_MODELS_CONFIG

def main():
    parser = argparse.ArgumentParser(
        description="Run CDCT experiments with improved evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single experiment
  python main.py --concept concepts/derivative.json --model gpt-4.1 --deployment gpt-4-deployment
  
  # Compare prompt strategies
  python main.py --concept concepts/derivative.json --model gpt-4.1 --deployment gpt-4-deployment --compare-strategies
  
  # Use strict evaluation mode
  python main.py --concept concepts/derivative.json --model gpt-4.1 --deployment gpt-4-deployment --evaluation-mode strict
  
  # Validate compression protocol only
  python main.py --concept concepts/derivative.json --validate-only
        """
    )
    
    parser.add_argument("--concept", type=str, required=True, 
                       help="Path to the concept JSON file")
    parser.add_argument("--model", type=str,
                       help="Name of the model to use (e.g., gpt-5, phi-4, claude-haiku-4-5)")
    
    # Experiment options
    parser.add_argument("--prompt-strategy", type=str, 
                       default="compression_aware",
                       choices=["simple", "compression_aware", "few_shot"],
                       help="Prompting strategy to use")
    parser.add_argument("--evaluation-mode", type=str,
                       default="balanced",
                       choices=["strict", "balanced", "lenient"],
                       help="Evaluation strictness")
    parser.add_argument("--compare-strategies", action="store_true",
                       help="Compare all prompt strategies")
    parser.add_argument("--validate-only", action="store_true",
                       help="Only validate compression protocol, don't run experiment")
    parser.add_argument("--output-dir", type=str, default="results",
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
    
    # Instantiate agent using config-driven approach
    if not args.model:
        print("ERROR: --model is required for running experiments")
        return
    
    try:
        # Find model config
        all_configs = SUBJECT_MODELS_CONFIG + JURY_MODELS_CONFIG
        model_config = None
        for config in all_configs:
            if config["model_name"].lower() == args.model.lower():
                model_config = config
                break
        
        if not model_config:
            print(f"ERROR: Model '{args.model}' not found in configuration")
            return
        
        # Build API keys dictionary from environment
        api_keys = {
            "AZURE_API_KEY": os.getenv("AZURE_API_KEY"),
            "AZURE_OPENAI_API_ENDPOINT": os.getenv("AZURE_OPENAI_API_ENDPOINT"),
            "DDFT_MODELS_ENDPOINT": os.getenv("DDFT_MODELS_ENDPOINT"),
            "AZURE_ANTHROPIC_API_ENDPOINT": os.getenv("AZURE_ANTHROPIC_API_ENDPOINT"),
        }
        
        # Create agent using config
        agent = agent_loader.create_agent(model_config, api_keys)
    except ValueError as e:
        print(f"ERROR: {e}")
        return
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    concept_name = os.path.splitext(os.path.basename(args.concept))[0]
    
    # Run experiments
    if args.compare_strategies:
        print(f"\n{'#'*70}")
        print("COMPARING PROMPT STRATEGIES")
        print(f"{'#'*70}\n")
        
        results = compare_strategies(args.concept, agent)
        
        # Save comparison
        output_path = os.path.join(
            args.output_dir,
            f"comparison_{concept_name}_{args.model.replace('/', '_')}.json"
        )
        
        comparison_summary = {
            "concept": concept_name,
            "model": args.model,
            "strategies": {
                strategy: {
                    "CSI": result["analysis"]["CSI"],
                    "C_h": result["analysis"]["C_h"],
                    "mean_score": result["analysis"]["mean_score"],
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
                f"results_{concept_name}_{args.model.replace('/', '_')}_{strategy}.json"
            )
            with open(full_path, 'w') as f:
                json.dump(result, f, indent=2)
        
        print(f"\nResults saved to {args.output_dir}/")
        
    else:
        # Run single experiment
        results = run_experiment(
            concept_path=args.concept,
            agent=agent,
            prompt_strategy=args.prompt_strategy,
            evaluation_mode=args.evaluation_mode,
            verbose=not args.quiet
        )
        
        # Save results
        output_filename = (
            f"results_{concept_name}_{args.model.replace('/', '_')}_"
            f"{args.prompt_strategy}_{args.evaluation_mode}.json"
        )
        output_path = os.path.join(args.output_dir, output_filename)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to {output_path}")
        
        # Print summary
        if not args.quiet:
            print_summary(results)


def print_summary(results: dict):
    """Print a nice summary of results."""
    analysis = results['analysis']
    
    print(f"\n{'='*70}")
    print("EXPERIMENT SUMMARY")
    print(f"{'='*70}")
    print(f"Concept:      {results['concept']}")
    print(f"Domain:       {results['domain']}")
    print(f"Model:        {results['model']}")
    print(f"Strategy:     {results.get('prompt_strategy', 'N/A')}")
    print(f"Eval Mode:    {results.get('evaluation_mode', 'N/A')}")
    print(f"\nMETRICS:")
    print(f"  CSI:              {analysis['CSI']:.4f}")
    print(f"  C_h:              {analysis['C_h']}")
    print(f"  Mean Score:       {analysis['mean_score']:.3f}")
    print(f"  Score Variance:   {analysis['score_variance']:.3f}")
    print(f"  Decay Direction:  {analysis['decay_direction']}")
    if analysis.get('R_squared'):
        print(f"  R²:               {analysis['R_squared']:.3f}")
    
    # Performance breakdown
    print(f"\nPERFORMANCE BY COMPRESSION LEVEL:")
    print(f"{'Level':<10} {'Score':<10} {'Verdict':<12} {'Response Length'}")
    print("-" * 70)
    for p in results['performance']:
        print(f"{p['compression_level']:<10} "
              f"{p['score']:<10.3f} "
              f"{p.get('verdict', 'N/A'):<12} "
              f"{p.get('response_length', 0)} words")
    
    # Warnings
    if 'warnings' in analysis:
        print(f"\nWARNINGS:")
        for w in analysis['warnings']:
            print(f"  ⚠ {w}")
    
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()