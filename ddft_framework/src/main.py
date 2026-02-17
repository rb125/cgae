
import argparse
from analyze_results import main as analyze

def main():
    parser = argparse.ArgumentParser(description="DDFT Analysis Framework CLI")
    parser.add_argument(
        '--run-analysis',
        action='store_true',
        help="Run the main DDFT analysis and generate model rankings."
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results",
        help="Directory containing the DDFT result files.",
    )
    # Add other commands here as needed, e.g., for data generation
    
    args = parser.parse_args()
    
    if args.run_analysis:
        print("CLI: Initiating DDFT analysis...")
        analyze(args.results_dir)
        print("CLI: Analysis complete.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
