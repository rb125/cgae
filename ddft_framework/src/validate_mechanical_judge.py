"""
Validation pipeline: Compare mechanical judge scores against original LLM judge scores.

Phase 1: Validate that mechanical metrics converge with LLM judge (r > 0.85).

Outputs:
- validation_summary.json: Overall correlations and statistics
- validation_matrix.csv: Row-by-row comparison for all responses
- divergence_analysis.json: Responses where mechanical/LLM disagree significantly
"""

import json
import os
import sys
import glob
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from statistics import mean, stdev
from scipy.stats import pearsonr
import csv

sys.path.insert(0, os.path.dirname(__file__))

from mechanical_all_metrics import MechanicalJudgeAllMetrics, EvaluationResult


@dataclass
class ComparisonRecord:
    """Single response comparison: mechanical vs LLM judge."""
    response_id: str
    model: str
    concept: str
    compression_level: float
    turn: int
    
    # LLM Judge scores
    llm_far: float
    llm_sas: float
    llm_fc: float
    
    # Mechanical judge scores
    mech_far: float
    mech_sas: float
    mech_fc: float
    
    # Deltas
    far_delta: float
    sas_delta: float
    fc_delta: float
    
    # Metadata
    response_text: str
    reference_text: str
    question: str


class MechanicalJudgeValidator:
    """Compares mechanical judge against LLM judge on existing results."""
    
    def __init__(self, results_dir: str, concepts_dir: str = "concepts"):
        """
        Args:
            results_dir: Directory containing DDFT result JSON files
            concepts_dir: Directory containing concept definition JSON files
        """
        self.results_dir = results_dir
        self.concepts_dir = concepts_dir
        self.mechanical_judge = MechanicalJudgeAllMetrics()
        self.records: List[ComparisonRecord] = []
        self._load_concept_cache()
    
    def _load_concept_cache(self):
        """Pre-load all concept files for quick reference text lookup."""
        self.concept_cache = {}
        for filepath in glob.glob(os.path.join(self.concepts_dir, "*.json")):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    concept_name = data.get('concept', 'unknown')
                    # Store {compression_level: reference_text}
                    corpus_map = {}
                    for item in data.get('corpus', []):
                        compression = item.get('compression_level')
                        text = item.get('text', '')
                        corpus_map[compression] = text
                    self.concept_cache[concept_name] = corpus_map
            except Exception as e:
                pass  # Skip files that can't be loaded
        
    def load_result_files(self) -> List[str]:
        """Load all DDFT result JSON files from directory."""
        pattern = os.path.join(self.results_dir, "ddft_*.json")
        files = glob.glob(pattern)
        print(f"Found {len(files)} result files in {self.results_dir}")
        return sorted(files)
    
    def extract_reference(self, concept: str, compression_level: float) -> str:
        """
        Extract reference text from concept cache.
        
        Args:
            concept: Concept name (e.g., 'recursion')
            compression_level: Compression level (0.0, 0.25, 0.5, 0.75, 1.0)
            
        Returns:
            Reference text for this concept at this compression level
        """
        # Normalize concept name
        concept = concept.lower().replace(' ', '_')
        
        if concept in self.concept_cache:
            corpus_map = self.concept_cache[concept]
            if compression_level in corpus_map:
                return corpus_map[compression_level]
            # Fallback: return any available compression level
            for comp in sorted(corpus_map.keys()):
                return corpus_map[comp]
        
        return ""  # No reference found
    
    def validate_result_file(self, filepath: str) -> int:
        """
        Load a single result file and compare all turn evaluations.
        Returns: number of records added
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"  ERROR loading {filepath}: {e}")
            return 0
        
        subject_model = data.get('subject_model', 'unknown')
        concept = data.get('concept', 'unknown')
        compression_level = data.get('compression_level', 0.0)
        conversation_log = data.get('conversation_log', [])
        
        records_added = 0
        response_id = 0
        
        # Process each turn
        for turn_idx, turn_msg in enumerate(conversation_log):
            if turn_msg.get('role') != 'assistant':
                continue
            
            turn_num = (turn_idx + 1) // 2  # Each turn: question + response
            response_text = turn_msg.get('content', '')
            evaluation = turn_msg.get('evaluation', {})
            
            if not evaluation or response_text == "API_ERROR":
                continue
            
            # Get LLM judge scores
            llm_far = evaluation.get('FAR')
            llm_sas = evaluation.get('SAS')
            llm_fc = evaluation.get('FC')
            
            # Skip if any LLM score is missing
            if any(s is None for s in [llm_far, llm_sas, llm_fc]):
                continue
            
            # Get reference text using concept and compression level
            reference_text = self.extract_reference(concept, compression_level)
            
            # Get question asked
            question = ""
            if turn_idx > 0:
                question = conversation_log[turn_idx - 1].get('content', '')
            
            # Compute mechanical scores
            mech_result = self.mechanical_judge.evaluate_response(
                response=response_text,
                reference_text=reference_text,
                turn_number=turn_num
            )
            
            # Create comparison record
            response_id += 1
            record = ComparisonRecord(
                response_id=f"{subject_model}_{concept}_c{compression_level}_t{turn_num}_{response_id}",
                model=subject_model,
                concept=concept,
                compression_level=compression_level,
                turn=turn_num,
                llm_far=llm_far,
                llm_sas=llm_sas,
                llm_fc=llm_fc,
                mech_far=mech_result.far,
                mech_sas=mech_result.sas,
                mech_fc=mech_result.fc,
                far_delta=abs(llm_far - mech_result.far),
                sas_delta=abs(llm_sas - mech_result.sas),
                fc_delta=abs(llm_fc - mech_result.fc),
                response_text=response_text[:200],  # Truncate for storage
                reference_text=reference_text[:200],
                question=question[:200]
            )
            
            self.records.append(record)
            records_added += 1
        
        return records_added
    
    def validate_all(self, verbose: bool = True) -> int:
        """
        Validate all result files. Returns total records processed.
        """
        files = self.load_result_files()
        total_records = 0
        
        for i, filepath in enumerate(files):
            if verbose and i % 20 == 0:
                print(f"Processing {i}/{len(files)} files...")
            
            records_added = self.validate_result_file(filepath)
            total_records += records_added
        
        print(f"Total comparison records created: {total_records}")
        return total_records
    
    def compute_correlations(self) -> Dict:
        """Compute Pearson correlations for all three metrics."""
        if len(self.records) < 3:
            return {"error": "Not enough records for correlation analysis"}
        
        llm_fars = [r.llm_far for r in self.records]
        mech_fars = [r.mech_far for r in self.records]
        
        llm_sass = [r.llm_sas for r in self.records]
        mech_sass = [r.mech_sas for r in self.records]
        
        llm_fcs = [r.llm_fc for r in self.records]
        mech_fcs = [r.mech_fc for r in self.records]
        
        far_corr, far_pval = pearsonr(llm_fars, mech_fars)
        sas_corr, sas_pval = pearsonr(llm_sass, mech_sass)
        fc_corr, fc_pval = pearsonr(llm_fcs, mech_fcs)
        
        return {
            'FAR': {
                'correlation': far_corr,
                'p_value': far_pval,
                'mean_delta': mean([r.far_delta for r in self.records]),
                'std_delta': stdev([r.far_delta for r in self.records]) if len(self.records) > 1 else 0
            },
            'SAS': {
                'correlation': sas_corr,
                'p_value': sas_pval,
                'mean_delta': mean([r.sas_delta for r in self.records]),
                'std_delta': stdev([r.sas_delta for r in self.records]) if len(self.records) > 1 else 0
            },
            'FC': {
                'correlation': fc_corr,
                'p_value': fc_pval,
                'mean_delta': mean([r.fc_delta for r in self.records]),
                'std_delta': stdev([r.fc_delta for r in self.records]) if len(self.records) > 1 else 0
            }
        }
    
    def identify_divergences(self, threshold: float = 0.20) -> List[ComparisonRecord]:
        """Find responses where mechanical/LLM disagree significantly (delta > threshold)."""
        divergent = [
            r for r in self.records
            if r.far_delta > threshold or r.sas_delta > threshold or r.fc_delta > threshold
        ]
        print(f"Found {len(divergent)} divergent records (delta > {threshold})")
        return divergent
    
    def save_validation_summary(self, output_path: str):
        """Save overall summary statistics."""
        correlations = self.compute_correlations()
        divergences = self.identify_divergences()
        
        summary = {
            'total_records': len(self.records),
            'correlations': correlations,
            'divergence_count': len(divergences),
            'divergence_threshold': 0.20,
            'records_by_metric': {
                'FAR': {
                    'llm_mean': mean([r.llm_far for r in self.records]),
                    'mech_mean': mean([r.mech_far for r in self.records]),
                    'llm_std': stdev([r.llm_far for r in self.records]) if len(self.records) > 1 else 0,
                    'mech_std': stdev([r.mech_far for r in self.records]) if len(self.records) > 1 else 0
                },
                'SAS': {
                    'llm_mean': mean([r.llm_sas for r in self.records]),
                    'mech_mean': mean([r.mech_sas for r in self.records]),
                    'llm_std': stdev([r.llm_sas for r in self.records]) if len(self.records) > 1 else 0,
                    'mech_std': stdev([r.mech_sas for r in self.records]) if len(self.records) > 1 else 0
                },
                'FC': {
                    'llm_mean': mean([r.llm_fc for r in self.records]),
                    'mech_mean': mean([r.mech_fc for r in self.records]),
                    'llm_std': stdev([r.llm_fc for r in self.records]) if len(self.records) > 1 else 0,
                    'mech_std': stdev([r.mech_fc for r in self.records]) if len(self.records) > 1 else 0
                }
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Summary saved to {output_path}")
        return summary
    
    def save_validation_matrix(self, output_path: str):
        """Save all comparison records as CSV for inspection."""
        fieldnames = [
            'response_id', 'model', 'concept', 'compression_level', 'turn',
            'llm_far', 'mech_far', 'far_delta',
            'llm_sas', 'mech_sas', 'sas_delta',
            'llm_fc', 'mech_fc', 'fc_delta',
            'response_text', 'question'
        ]
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in self.records:
                row = asdict(record)
                row.pop('reference_text')  # Skip reference for brevity
                writer.writerow(row)
        
        print(f"Validation matrix saved to {output_path} ({len(self.records)} rows)")
    
    def save_divergence_analysis(self, output_path: str):
        """Save detailed analysis of divergent responses."""
        divergences = self.identify_divergences()
        
        analysis = {
            'total_divergent': len(divergences),
            'divergence_threshold': 0.20,
            'divergences': [
                {
                    'response_id': d.response_id,
                    'model': d.model,
                    'concept': d.concept,
                    'turn': d.turn,
                    'far': {'llm': d.llm_far, 'mech': d.mech_far, 'delta': d.far_delta},
                    'sas': {'llm': d.llm_sas, 'mech': d.mech_sas, 'delta': d.sas_delta},
                    'fc': {'llm': d.llm_fc, 'mech': d.mech_fc, 'delta': d.fc_delta},
                    'response_preview': d.response_text,
                    'question': d.question
                }
                for d in divergences[:100]  # Top 100 divergences
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"Divergence analysis saved to {output_path} ({len(divergences)} total)")


def main():
    """Run full validation pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate mechanical judge against LLM judge")
    parser.add_argument("--results-dir", type=str, default="results_backup_20251109_021756",
                       help="Directory containing DDFT results")
    parser.add_argument("--concepts-dir", type=str, default="concepts",
                       help="Directory containing concept definitions")
    parser.add_argument("--output-dir", type=str, default="validation_results",
                       help="Directory to save validation outputs")
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Run validation
    print(f"\n{'='*80}")
    print("MECHANICAL JUDGE VALIDATION PIPELINE")
    print(f"{'='*80}\n")
    
    validator = MechanicalJudgeValidator(args.results_dir, args.concepts_dir)
    
    print("Phase 1: Loading and comparing all results...")
    total = validator.validate_all(verbose=True)
    
    if total == 0:
        print("ERROR: No comparison records created. Check results directory.")
        return
    
    print(f"\n{'='*80}")
    print("Phase 2: Computing correlations...")
    correlations = validator.compute_correlations()
    
    for metric, stats in correlations.items():
        if 'error' not in stats:
            print(f"\n{metric}:")
            print(f"  Correlation: {stats['correlation']:.4f} (p < {stats['p_value']:.2e})")
            print(f"  Mean delta: {stats['mean_delta']:.4f} ± {stats['std_delta']:.4f}")
    
    print(f"\n{'='*80}")
    print("Phase 3: Saving validation outputs...")
    
    summary = validator.save_validation_summary(os.path.join(args.output_dir, "validation_summary.json"))
    validator.save_validation_matrix(os.path.join(args.output_dir, "validation_matrix.csv"))
    validator.save_divergence_analysis(os.path.join(args.output_dir, "divergence_analysis.json"))
    
    print(f"\n{'='*80}")
    print("VALIDATION COMPLETE")
    print(f"{'='*80}\n")
    
    # Print recommendations
    all_above_threshold = all(
        stats['correlation'] > 0.85
        for stats in correlations.values()
        if 'error' not in stats
    )
    
    if all_above_threshold:
        print("✓ SUCCESS: All metrics converge strongly (r > 0.85)")
        print("  Recommendation: Deploy mechanical judge in production")
    else:
        print("⚠ CAUTION: Some metrics show weaker convergence")
        print("  Review divergence_analysis.json for details")
        for metric, stats in correlations.items():
            if 'error' not in stats and stats['correlation'] < 0.85:
                print(f"  - {metric}: r = {stats['correlation']:.4f}")


if __name__ == "__main__":
    main()
