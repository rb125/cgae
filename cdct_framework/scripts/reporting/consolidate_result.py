"""
Consolidates all CDCT experiment results into a single analyzable file.
Generates both a detailed JSON and a summary CSV/markdown table.
"""

import json
import glob
import os
from collections import defaultdict
import csv

def consolidate_results(results_dir: str = "results", output_file: str = "consolidated_results.json"):
    """
    Consolidates all result JSON files into a single structured file.
    
    Args:
        results_dir: Directory containing result JSON files
        output_file: Output file path for consolidated results
    
    Returns:
        Dictionary with consolidated data
    """
    # Find all result files
    result_files = glob.glob(os.path.join(results_dir, "results_*.json"))
    
    if not result_files:
        print(f"No result files found in {results_dir}")
        return None
    
    print(f"Found {len(result_files)} result files")
    
    # Consolidated structure
    consolidated = {
        "metadata": {
            "total_experiments": len(result_files),
            "results_directory": results_dir
        },
        "experiments": [],
        "by_model": defaultdict(list),
        "by_domain": defaultdict(list),
        "by_concept": defaultdict(list)
    }
    
    # Process each file
    for filepath in sorted(result_files):
        filename = os.path.basename(filepath)
        print(f"Processing: {filename}")
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Extract key information
            experiment = {
                "filename": filename,
                "concept": data.get("concept"),
                "domain": data.get("domain"),
                "model": data.get("model"),
                "prompt_strategy": data.get("prompt_strategy", "unknown"),
                "evaluation_mode": data.get("evaluation_mode", "unknown"),
                "analysis": data.get("analysis", {}),
                "performance_summary": {
                    "scores": [p["score"] for p in data.get("performance", [])],
                    "compression_levels": [p["compression_level"] for p in data.get("performance", [])],
                    "verdicts": [p.get("verdict", "unknown") for p in data.get("performance", [])]
                }
            }
            
            # Add to consolidated data
            consolidated["experiments"].append(experiment)
            consolidated["by_model"][data.get("model")].append(experiment)
            consolidated["by_domain"][data.get("domain")].append(experiment)
            consolidated["by_concept"][data.get("concept")].append(experiment)
            
        except Exception as e:
            print(f"  ERROR processing {filename}: {e}")
    
    # Convert defaultdicts to regular dicts for JSON serialization
    consolidated["by_model"] = dict(consolidated["by_model"])
    consolidated["by_domain"] = dict(consolidated["by_domain"])
    consolidated["by_concept"] = dict(consolidated["by_concept"])
    
    # Save consolidated results
    with open(output_file, 'w') as f:
        json.dump(consolidated, f, indent=2)
    
    print(f"\n✓ Consolidated results saved to: {output_file}")
    print(f"  Total experiments: {len(consolidated['experiments'])}")
    print(f"  Models: {len(consolidated['by_model'])}")
    print(f"  Domains: {len(consolidated['by_domain'])}")
    print(f"  Concepts: {len(consolidated['by_concept'])}")
    
    return consolidated


def generate_summary_table(consolidated_data: dict, output_csv: str = "summary_table.csv",
                          output_md: str = "summary_table.md"):
    """
    Generates a summary table (CSV and Markdown) from consolidated data.
    
    Format: One row per experiment with key metrics.
    """
    if not consolidated_data:
        print("No data to summarize")
        return
    
    experiments = consolidated_data["experiments"]
    
    # CSV output
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            "Model", "Concept", "Domain", "Strategy", "Eval_Mode",
            "CSI", "C_h", "Mean_Score", "Min_Score", "Max_Score",
            "Decay_Direction", "R_squared", "Has_Warnings"
        ])
        
        # Data rows
        for exp in experiments:
            analysis = exp["analysis"]
            writer.writerow([
                exp["model"],
                exp["concept"],
                exp["domain"],
                exp["prompt_strategy"],
                exp["evaluation_mode"],
                f"{analysis.get('CSI', 0):.4f}" if analysis.get('CSI') is not None else "N/A",
                analysis.get('C_h', 'N/A'),
                f"{analysis.get('mean_score', 0):.3f}" if analysis.get('mean_score') is not None else "N/A",
                f"{analysis.get('min_score', 0):.3f}" if analysis.get('min_score') is not None else "N/A",
                f"{analysis.get('max_score', 0):.3f}" if analysis.get('max_score') is not None else "N/A",
                analysis.get('decay_direction', 'N/A'),
                f"{analysis.get('R_squared', 0):.3f}" if analysis.get('R_squared') is not None else "N/A",
                "Yes" if analysis.get('warnings') else "No"
            ])
    
    print(f"✓ Summary CSV saved to: {output_csv}")
    
    # Markdown table output
    with open(output_md, 'w') as f:
        f.write("# CDCT Experiment Summary\n\n")
        f.write(f"Total Experiments: {len(experiments)}\n\n")
        
        # Per-model summary
        f.write("## Summary by Model\n\n")
        f.write("| Model | N | Mean CSI | Std CSI | Mean Score | Domains |\n")
        f.write("|-------|---|----------|---------|------------|----------|\n")
        
        for model, exps in sorted(consolidated_data["by_model"].items()):
            csi_values = [e["analysis"].get("CSI") for e in exps if e["analysis"].get("CSI") is not None]
            scores = [e["analysis"].get("mean_score") for e in exps if e["analysis"].get("mean_score") is not None]
            domains = set(e["domain"] for e in exps)
            
            if csi_values:
                import statistics
                mean_csi = statistics.mean(csi_values)
                std_csi = statistics.stdev(csi_values) if len(csi_values) > 1 else 0
                mean_score = statistics.mean(scores) if scores else 0
                
                f.write(f"| {model} | {len(exps)} | {mean_csi:.4f} | {std_csi:.4f} | {mean_score:.3f} | {len(domains)} |\n")
        
        # Per-domain summary
        f.write("\n## Summary by Domain\n\n")
        f.write("| Domain | N | Mean CSI | Std CSI | Models |\n")
        f.write("|--------|---|----------|---------|--------|\n")
        
        for domain, exps in sorted(consolidated_data["by_domain"].items()):
            csi_values = [e["analysis"].get("CSI") for e in exps if e["analysis"].get("CSI") is not None]
            models = set(e["model"] for e in exps)
            
            if csi_values:
                import statistics
                mean_csi = statistics.mean(csi_values)
                std_csi = statistics.stdev(csi_values) if len(csi_values) > 1 else 0
                
                f.write(f"| {domain} | {len(exps)} | {mean_csi:.4f} | {std_csi:.4f} | {len(models)} |\n")
        
        # Full detailed table
        f.write("\n## Detailed Results\n\n")
        f.write("| Model | Concept | Domain | CSI | C_h | Mean Score | Direction |\n")
        f.write("|-------|---------|--------|-----|-----|------------|------------|\n")
        
        for exp in sorted(experiments, key=lambda x: (x["model"], x["domain"], x["concept"])):
            analysis = exp["analysis"]
            csi = f"{analysis.get('CSI', 0):.4f}" if analysis.get('CSI') is not None else "N/A"
            c_h = analysis.get('C_h', 'N/A')
            mean_score = f"{analysis.get('mean_score', 0):.3f}" if analysis.get('mean_score') is not None else "N/A"
            direction = analysis.get('decay_direction', 'N/A')
            
            f.write(f"| {exp['model']} | {exp['concept']} | {exp['domain']} | {csi} | {c_h} | {mean_score} | {direction} |\n")
    
    print(f"✓ Summary Markdown saved to: {output_md}")


def generate_compact_summary(consolidated_data: dict, output_file: str = "compact_summary.txt"):
    """
    Generates a very compact summary for easy sharing/review.
    """
    if not consolidated_data:
        return
    
    experiments = consolidated_data["experiments"]
    
    with open(output_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("CDCT BENCHMARK RESULTS - COMPACT SUMMARY\n")
        f.write("="*80 + "\n\n")
        
        # Overall stats
        f.write(f"Total Experiments: {len(experiments)}\n")
        f.write(f"Models: {len(consolidated_data['by_model'])}\n")
        f.write(f"Domains: {len(consolidated_data['by_domain'])}\n")
        f.write(f"Concepts: {len(consolidated_data['by_concept'])}\n\n")
        
        # Model rankings by mean CSI
        f.write("-"*80 + "\n")
        f.write("MODEL RANKINGS (by Mean CSI - lower is better)\n")
        f.write("-"*80 + "\n\n")
        
        model_stats = []
        for model, exps in consolidated_data["by_model"].items():
            csi_values = [e["analysis"].get("CSI") for e in exps if e["analysis"].get("CSI") is not None]
            if csi_values:
                import statistics
                mean_csi = statistics.mean(csi_values)
                std_csi = statistics.stdev(csi_values) if len(csi_values) > 1 else 0
                model_stats.append((model, mean_csi, std_csi, len(exps)))
        
        model_stats.sort(key=lambda x: x[1])  # Sort by mean CSI
        
        f.write(f"{'Rank':<6} {'Model':<30} {'Mean CSI':<12} {'Std':<10} {'N':<5}\n")
        f.write("-"*80 + "\n")
        
        for rank, (model, mean_csi, std_csi, n) in enumerate(model_stats, 1):
            f.write(f"{rank:<6} {model:<30} {mean_csi:<12.4f} {std_csi:<10.4f} {n:<5}\n")
        
        # Domain difficulty
        f.write("\n" + "-"*80 + "\n")
        f.write("DOMAIN DIFFICULTY (by Mean CSI - higher = harder to compress)\n")
        f.write("-"*80 + "\n\n")
        
        domain_stats = []
        for domain, exps in consolidated_data["by_domain"].items():
            csi_values = [e["analysis"].get("CSI") for e in exps if e["analysis"].get("CSI") is not None]
            if csi_values:
                import statistics
                mean_csi = statistics.mean(csi_values)
                std_csi = statistics.stdev(csi_values) if len(csi_values) > 1 else 0
                domain_stats.append((domain, mean_csi, std_csi, len(exps)))
        
        domain_stats.sort(key=lambda x: x[1], reverse=True)  # Sort by difficulty
        
        f.write(f"{'Domain':<25} {'Mean CSI':<12} {'Std':<10} {'N':<5}\n")
        f.write("-"*80 + "\n")
        
        for domain, mean_csi, std_csi, n in domain_stats:
            f.write(f"{domain:<25} {mean_csi:<12.4f} {std_csi:<10.4f} {n:<5}\n")
        
        f.write("\n" + "="*80 + "\n")
    
    print(f"✓ Compact summary saved to: {output_file}")


def main():
    """Main consolidation workflow."""
    print("\n" + "="*80)
    print("CDCT RESULTS CONSOLIDATION")
    print("="*80 + "\n")
    
    # Step 1: Consolidate all results
    consolidated = consolidate_results(
        results_dir="results",
        output_file="consolidated_results.json"
    )
    
    if not consolidated:
        print("ERROR: No results to consolidate")
        return
    
    print("\n" + "-"*80 + "\n")
    
    # Step 2: Generate summary tables
    generate_summary_table(
        consolidated,
        output_csv="summary_table.csv",
        output_md="summary_table.md"
    )
    
    print("\n" + "-"*80 + "\n")
    
    # Step 3: Generate compact summary
    generate_compact_summary(
        consolidated,
        output_file="compact_summary.txt"
    )
    
    print("\n" + "="*80)
    print("CONSOLIDATION COMPLETE!")
    print("="*80)
    print("\nGenerated files:")
    print("  1. consolidated_results.json  - Full detailed data")
    print("  2. summary_table.csv          - Spreadsheet format")
    print("  3. summary_table.md           - Markdown tables")
    print("  4. compact_summary.txt        - Quick overview")
    print("\nTo share with me, send 'compact_summary.txt' first!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
