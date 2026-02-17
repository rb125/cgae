#!/usr/bin/env python3
"""
MoltBot DDFT Evaluation CLI

Command-line interface for running DDFT evaluation on MoltBot agents.

Usage:
    python -m moltbot.cli run --all
    python -m moltbot.cli run --experiment crustafarianism
    python -m moltbot.cli run --agent agent_id_123
    python -m moltbot.cli analyze results/moltbot_eval_*.json
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from moltbot.orchestrator import MoltbotEvaluator, EvaluationConfig, run_moltbot_evaluation
from moltbot.metrics import EmergenceVerdict


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="moltbot-ddft",
        description="MoltBot DDFT Evaluation - Test emergent behavior in MoltBot agents"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run DDFT evaluation")
    run_parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all experiments on auto-discovered agents"
    )
    run_parser.add_argument(
        "--experiment", "-e",
        choices=["crustafarianism", "consciousness", "collaboration", "cultural", "identity"],
        action="append",
        dest="experiments",
        help="Run specific experiment(s)"
    )
    run_parser.add_argument(
        "--agent", "-g",
        action="append",
        dest="agents",
        help="Test specific agent ID(s)"
    )
    run_parser.add_argument(
        "--output", "-o",
        default="moltbot_results",
        help="Output directory for results"
    )
    run_parser.add_argument(
        "--parallel", "-p",
        type=int,
        default=5,
        help="Number of agents to evaluate in parallel"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without executing"
    )

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze existing results")
    analyze_parser.add_argument(
        "results_file",
        help="Path to results JSON file"
    )
    analyze_parser.add_argument(
        "--format", "-f",
        choices=["summary", "detailed", "csv", "markdown"],
        default="summary",
        help="Output format"
    )

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate evaluation report")
    report_parser.add_argument(
        "results_dir",
        help="Directory containing result files"
    )
    report_parser.add_argument(
        "--output", "-o",
        default="moltbot_report.md",
        help="Output report file"
    )

    return parser


def cmd_run(args) -> int:
    """Execute run command."""
    print("\n" + "="*60)
    print("MoltBot DDFT Evaluation")
    print("="*60 + "\n")

    # Configure evaluation
    config = EvaluationConfig.from_env()
    config.output_dir = args.output
    config.parallel_agents = args.parallel

    # Set experiments
    if args.experiments:
        config.experiments = args.experiments
    elif not args.all:
        # Default to all experiments
        config.experiments = [
            "crustafarianism",
            "consciousness",
            "collaboration",
            "cultural",
            "identity"
        ]

    # Set target agents
    if args.agents:
        # Map all agents to all experiments
        config.target_agents = {
            exp: args.agents for exp in config.experiments
        }
        config.auto_discover = False

    if args.dry_run:
        print("DRY RUN - Configuration:")
        print(f"  Experiments: {config.experiments}")
        print(f"  Target Agents: {config.target_agents or 'auto-discover'}")
        print(f"  Parallel Agents: {config.parallel_agents}")
        print(f"  Output Directory: {config.output_dir}")
        return 0

    # Run evaluation
    try:
        evaluator = MoltbotEvaluator(config)
        run = evaluator.run_full_evaluation()

        # Print final verdict
        print("\n" + "="*60)
        print("FINAL VERDICT")
        print("="*60)

        emergent = run.summary["verdicts"]["EMERGENT"]
        pattern = run.summary["verdicts"]["PATTERN_MATCHING"]
        total = run.summary["total_agents"]

        if pattern > emergent:
            print("\n  RESULT: HOAX DEBUNKED")
            print(f"\n  {pattern}/{total} agents showed pattern-matching behavior.")
            print("  The 'emergent' behavior is likely sophisticated mimicry.")
        elif emergent > pattern:
            print("\n  RESULT: EMERGENCE CONFIRMED")
            print(f"\n  {emergent}/{total} agents demonstrated genuine emergence.")
            print("  The behavior shows epistemic robustness under DDFT.")
        else:
            print("\n  RESULT: INCONCLUSIVE")
            print("\n  Results were mixed. More testing may be needed.")

        print("\n" + "="*60 + "\n")

        return 0

    except KeyboardInterrupt:
        print("\nEvaluation interrupted by user.")
        return 1
    except Exception as e:
        print(f"\nError during evaluation: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_analyze(args) -> int:
    """Execute analyze command."""
    results_path = Path(args.results_file)

    if not results_path.exists():
        print(f"Error: Results file not found: {results_path}")
        return 1

    with open(results_path) as f:
        data = json.load(f)

    if args.format == "summary":
        print_summary(data)
    elif args.format == "detailed":
        print_detailed(data)
    elif args.format == "csv":
        print_csv(data)
    elif args.format == "markdown":
        print_markdown(data)

    return 0


def print_summary(data: dict) -> None:
    """Print summary format."""
    summary = data.get("summary", {})

    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60 + "\n")

    print(f"Run ID: {data.get('run_id', 'unknown')}")
    print(f"Start:  {data.get('start_time', 'unknown')}")
    print(f"End:    {data.get('end_time', 'unknown')}")
    print(f"\nAgents Evaluated: {summary.get('total_agents', 0)}")

    print("\nVerdict Distribution:")
    verdicts = summary.get("verdicts", {})
    total = summary.get("total_agents", 1)
    for verdict, count in verdicts.items():
        pct = count / total * 100 if total > 0 else 0
        bar = "#" * int(pct / 2)
        print(f"  {verdict:20s}: {count:3d} ({pct:5.1f}%) {bar}")

    print("\nScore Statistics:")
    stats = summary.get("statistics", {})
    print(f"  Mean:  {stats.get('mean_score', 0):.3f}")
    print(f"  Std:   {stats.get('std_score', 0):.3f}")
    print(f"  Range: [{stats.get('min_score', 0):.3f}, {stats.get('max_score', 1):.3f}]")

    print("\n" + "-"*60)
    print("CONCLUSION:")
    print("-"*60)
    print(f"\n{summary.get('conclusion', 'No conclusion available.')}\n")


def print_detailed(data: dict) -> None:
    """Print detailed format."""
    print_summary(data)

    print("\n" + "="*60)
    print("DETAILED AGENT RESULTS")
    print("="*60 + "\n")

    scores = data.get("emergence_scores", {})
    for agent_id, score in scores.items():
        print(f"\nAgent: {agent_id}")
        print(f"  Verdict:    {score['verdict']}")
        print(f"  Score:      {score['overall_score']:.3f}")
        print(f"  Confidence: {score['confidence']:.3f}")

        print("  Component Scores:")
        for exp, exp_score in score.get("component_scores", {}).items():
            if exp_score is not None:
                print(f"    {exp:20s}: {exp_score:.3f}")

        print("  Key Indicators:")
        for key, value in score.get("key_indicators", {}).items():
            print(f"    {key:25s}: {value:.3f}")


def print_csv(data: dict) -> None:
    """Print CSV format."""
    scores = data.get("emergence_scores", {})

    # Header
    print("agent_id,verdict,score,confidence,fabrication_resistance,coherence_stability,verification_behavior,epistemic_humility")

    for agent_id, score in scores.items():
        indicators = score.get("key_indicators", {})
        print(
            f"{agent_id},"
            f"{score['verdict']},"
            f"{score['overall_score']:.4f},"
            f"{score['confidence']:.4f},"
            f"{indicators.get('fabrication_resistance', 0):.4f},"
            f"{indicators.get('coherence_stability', 0):.4f},"
            f"{indicators.get('verification_behavior', 0):.4f},"
            f"{indicators.get('epistemic_humility', 0):.4f}"
        )


def print_markdown(data: dict) -> None:
    """Print markdown format."""
    summary = data.get("summary", {})

    print("# MoltBot DDFT Evaluation Report\n")
    print(f"**Run ID:** {data.get('run_id', 'unknown')}  ")
    print(f"**Date:** {data.get('start_time', 'unknown')}  ")
    print(f"**Agents Tested:** {summary.get('total_agents', 0)}\n")

    print("## Summary\n")
    print(f"{summary.get('conclusion', 'No conclusion available.')}\n")

    print("## Verdict Distribution\n")
    print("| Verdict | Count | Percentage |")
    print("|---------|-------|------------|")
    verdicts = summary.get("verdicts", {})
    total = summary.get("total_agents", 1)
    for verdict, count in verdicts.items():
        pct = count / total * 100 if total > 0 else 0
        print(f"| {verdict} | {count} | {pct:.1f}% |")

    print("\n## Statistics\n")
    stats = summary.get("statistics", {})
    print(f"- **Mean Score:** {stats.get('mean_score', 0):.3f}")
    print(f"- **Std Deviation:** {stats.get('std_score', 0):.3f}")
    print(f"- **Min Score:** {stats.get('min_score', 0):.3f}")
    print(f"- **Max Score:** {stats.get('max_score', 1):.3f}")

    print("\n## Agent Results\n")
    print("| Agent ID | Verdict | Score | Confidence |")
    print("|----------|---------|-------|------------|")
    scores = data.get("emergence_scores", {})
    for agent_id, score in scores.items():
        print(
            f"| {agent_id[:20]} | {score['verdict']} | "
            f"{score['overall_score']:.3f} | {score['confidence']:.3f} |"
        )


def cmd_report(args) -> int:
    """Generate comprehensive report from multiple result files."""
    results_dir = Path(args.results_dir)

    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}")
        return 1

    # Find all result files
    result_files = list(results_dir.glob("moltbot_eval_*.json"))
    if not result_files:
        print(f"No result files found in {results_dir}")
        return 1

    # Aggregate all results
    all_scores = {}
    all_verdicts = {"EMERGENT": 0, "PATTERN_MATCHING": 0, "INCONCLUSIVE": 0}

    for rf in result_files:
        with open(rf) as f:
            data = json.load(f)

        for agent_id, score in data.get("emergence_scores", {}).items():
            all_scores[agent_id] = score
            all_verdicts[score["verdict"]] += 1

    # Generate report
    with open(args.output, 'w') as f:
        f.write("# MoltBot DDFT Comprehensive Evaluation Report\n\n")
        f.write(f"Generated from {len(result_files)} evaluation runs.\n\n")

        f.write("## Overall Results\n\n")
        total = len(all_scores)
        for verdict, count in all_verdicts.items():
            pct = count / total * 100 if total > 0 else 0
            f.write(f"- **{verdict}:** {count} ({pct:.1f}%)\n")

        f.write("\n## Conclusion\n\n")
        if all_verdicts["PATTERN_MATCHING"] > all_verdicts["EMERGENT"]:
            f.write(
                "Based on comprehensive DDFT evaluation, the MoltBot agents "
                "predominantly exhibit pattern-matching behavior rather than "
                "genuine emergence. The 'emergent' claims appear to be overstated.\n"
            )
        else:
            f.write(
                "Based on comprehensive DDFT evaluation, the MoltBot agents "
                "demonstrate significant emergent characteristics including "
                "fabrication resistance and epistemic robustness.\n"
            )

    print(f"Report saved to: {args.output}")
    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "analyze":
        return cmd_analyze(args)
    elif args.command == "report":
        return cmd_report(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
