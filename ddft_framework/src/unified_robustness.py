"""
Unified Robustness Framework: CDCT-DDFT Integration

Provides metrics, classification, and analysis for combined semantic (CDCT/CSI)
and epistemic (DDFT/ECR+CCI) robustness evaluation.
"""

import pandas as pd
import numpy as np
from scipy.stats import pearsonr, spearmanr
from typing import Dict, Tuple, List, Optional


class RobustnessProfile:
    """Single model robustness measurement."""
    
    def __init__(self, model_name: str, csi: Optional[float] = None, 
                 ecr: Optional[float] = None, cci: Optional[float] = None,
                 params: Optional[int] = None):
        self.model_name = model_name
        self.csi = csi  # CDCT Semantic Compression Index
        self.ecr = ecr  # DDFT Error Convergence Rate
        self.cci = cci  # DDFT Context Coherence Index
        self.params = params
    
    def has_both_dimensions(self) -> bool:
        """Check if model has both semantic and epistemic measurements."""
        return self.csi is not None and self.ecr is not None
    
    def has_semantic(self) -> bool:
        return self.csi is not None
    
    def has_epistemic(self) -> bool:
        return self.ecr is not None
    
    def is_complete(self) -> bool:
        """Check if all metrics available."""
        return self.has_both_dimensions() and self.cci is not None


class UnifiedRobustnessFramework:
    """Main framework for analysis and classification."""
    
    # Classification thresholds
    THRESHOLDS = {
        'semantic_robust': 0.12,
        'epistemic_robust': 0.35,
        'recovery_strong': 0.5,
        'recovery_weak': 0.3,
    }
    
    def __init__(self):
        self.profiles: Dict[str, RobustnessProfile] = {}
        self.data_frame: Optional[pd.DataFrame] = None
    
    def add_model(self, profile: RobustnessProfile) -> None:
        """Add a model profile."""
        self.profiles[profile.model_name] = profile
    
    def build_dataframe(self) -> pd.DataFrame:
        """Convert profiles to DataFrame."""
        data = []
        for name, profile in self.profiles.items():
            data.append({
                'Model': name,
                'CSI': profile.csi,
                'ECR': profile.ecr,
                'CCI': profile.cci,
                'Params': profile.params,
            })
        
        self.data_frame = pd.DataFrame(data)
        return self.data_frame
    
    def compute_seb(self, csi: float, ecr: float) -> float:
        """Semantic-Epistemic Balance: how evenly robust across dimensions."""
        if not self.data_frame is None:
            csi_norm = csi / self.data_frame['CSI'].max()
            ecr_norm = ecr / self.data_frame['ECR'].max()
        else:
            # Use default normalization
            csi_norm = csi / 0.18
            ecr_norm = ecr / 0.77
        
        return 1 - abs(csi_norm - ecr_norm)
    
    def compute_ori(self, csi: Optional[float], ecr: Optional[float]) -> Optional[float]:
        """Overall Robustness Index: composite metric."""
        if csi is None or ecr is None:
            return None
        
        if not self.data_frame is None:
            csi_max = self.data_frame['CSI'].max()
            ecr_max = self.data_frame['ECR'].max()
        else:
            csi_max = 0.18
            ecr_max = 0.77
        
        return (csi + (ecr / ecr_max * csi_max)) / 2
    
    def compute_bi(self, ecr: float, cci: Optional[float]) -> float:
        """Brittleness Index: ECR weighted by recovery."""
        if cci is None:
            return ecr
        
        recovery_factor = max(cci, 0)
        return ecr - 0.5 * recovery_factor
    
    def classify_robustness_type(self, csi: Optional[float], ecr: Optional[float], 
                                 cci: Optional[float]) -> str:
        """Classify model into robustness profile."""
        
        if csi is None and ecr is None:
            return "Unclassified"
        
        # Both dimensions available
        if csi is not None and ecr is not None:
            if csi < self.THRESHOLDS['semantic_robust'] and ecr < self.THRESHOLDS['epistemic_robust']:
                return "Dual-Robust"
            elif csi < self.THRESHOLDS['semantic_robust'] and ecr >= self.THRESHOLDS['epistemic_robust']:
                if cci is not None and cci > self.THRESHOLDS['recovery_strong']:
                    return "Semantic-Robust, Self-Correcting"
                else:
                    return "Semantic-Robust-Epistemic-Brittle"
            elif ecr < self.THRESHOLDS['epistemic_robust']:
                return "Epistemic-Robust"
            elif cci is not None and cci > self.THRESHOLDS['recovery_strong']:
                return "Recoverable-Epistemic"
            else:
                return "Fragile-NonRecoverable"
        
        # Only semantic available
        elif csi is not None:
            if csi < self.THRESHOLDS['semantic_robust']:
                return "Semantic-Robust (ECR unknown)"
            elif csi < 0.13:
                return "Semantic-Borderline"
            else:
                return "Semantic-Fragile"
        
        # Only epistemic available
        elif ecr is not None:
            if ecr < self.THRESHOLDS['epistemic_robust']:
                return "Epistemic-Robust"
            elif ecr < 0.40 and cci is not None and cci > self.THRESHOLDS['recovery_weak']:
                return "Recoverable-Epistemic"
            else:
                return "Epistemic-Brittle"
        
        return "Unclassified"
    
    def compute_all_metrics(self) -> pd.DataFrame:
        """Compute all metrics and return enriched DataFrame."""
        if self.data_frame is None:
            self.build_dataframe()
        
        df = self.data_frame.copy()
        
        # Add derived metrics
        df['SEB'] = df.apply(
            lambda row: self.compute_seb(row['CSI'], row['ECR']) 
            if pd.notna(row['CSI']) and pd.notna(row['ECR']) else np.nan,
            axis=1
        )
        
        df['ORI'] = df.apply(
            lambda row: self.compute_ori(row['CSI'], row['ECR']),
            axis=1
        )
        
        df['BI'] = df.apply(
            lambda row: self.compute_bi(row['ECR'], row['CCI'])
            if pd.notna(row['ECR']) else np.nan,
            axis=1
        )
        
        df['Robustness_Type'] = df.apply(
            lambda row: self.classify_robustness_type(row['CSI'], row['ECR'], row['CCI']),
            axis=1
        )
        
        return df
    
    def correlation_analysis(self) -> Dict[str, Tuple[float, float]]:
        """Compute correlations between dimensions."""
        if self.data_frame is None:
            self.build_dataframe()
        
        df = self.data_frame.dropna(subset=['CSI', 'ECR'])
        
        if len(df) < 3:
            return {
                'CSI_ECR': (np.nan, np.nan),
                'CSI_CCI': (np.nan, np.nan),
                'ECR_CCI': (np.nan, np.nan),
            }
        
        results = {}
        
        # CSI vs ECR
        if len(df[['CSI', 'ECR']].dropna()) >= 3:
            r, p = pearsonr(df['CSI'], df['ECR'])
            results['CSI_ECR'] = (r, p)
        
        # CSI vs CCI
        df_cci = df.dropna(subset=['CCI'])
        if len(df_cci) >= 3:
            r, p = pearsonr(df_cci['CSI'], df_cci['CCI'])
            results['CSI_CCI'] = (r, p)
        
        # ECR vs CCI
        if len(df_cci) >= 3:
            r, p = pearsonr(df_cci['ECR'], df_cci['CCI'])
            results['ECR_CCI'] = (r, p)
        
        return results
    
    def group_by_paradigm(self, paradigm_col: str = 'Robustness_Type') -> Dict[str, pd.DataFrame]:
        """Group models by paradigm/type."""
        if self.data_frame is None:
            self.build_dataframe()
        
        df = self.compute_all_metrics()
        return dict(list(df.groupby(paradigm_col)))
    
    def ranking_by_ori(self) -> pd.DataFrame:
        """Rank models by Overall Robustness Index."""
        df = self.compute_all_metrics()
        df_with_ori = df.dropna(subset=['ORI'])
        return df_with_ori.sort_values('ORI')[['Model', 'ORI', 'SEB', 'Robustness_Type']]
    
    def summary_stats(self) -> Dict:
        """Generate summary statistics by robustness type."""
        df = self.compute_all_metrics()
        groups = df.groupby('Robustness_Type')
        
        summary = {}
        for rtype, group in groups:
            summary[rtype] = {
                'count': len(group),
                'models': group['Model'].tolist(),
                'mean_csi': group['CSI'].mean(),
                'mean_ecr': group['ECR'].mean(),
                'mean_cci': group['CCI'].mean(),
                'mean_ori': group['ORI'].mean(),
            }
        
        return summary


def load_sample_data() -> UnifiedRobustnessFramework:
    """Load default CDCT-DDFT dataset."""
    fw = UnifiedRobustnessFramework()
    
    # CDCT + DDFT measured
    fw.add_model(RobustnessProfile('gpt-5-mini', csi=0.0949, ecr=0.576, cci=0.676, params=12))
    fw.add_model(RobustnessProfile('deepseek-v3-0324', csi=0.1395, ecr=0.768, cci=1.031, params=671))
    fw.add_model(RobustnessProfile('mistral-medium-2505', csi=0.1610, ecr=0.692, cci=-0.274, params=7))
    fw.add_model(RobustnessProfile('phi-4-mini-instruct', csi=0.1616, ecr=0.585, cci=-0.588, params=4))
    fw.add_model(RobustnessProfile('gpt-oss-120b', csi=0.1774, ecr=0.537, cci=-0.438, params=120))
    
    # CDCT only
    fw.add_model(RobustnessProfile('grok-4-fast-reasoning', csi=0.1048, params=100))
    fw.add_model(RobustnessProfile('gpt-4.1', csi=0.1671, params=100))
    
    # DDFT only
    fw.add_model(RobustnessProfile('Llama-4-Maverick', ecr=0.088, cci=0.025, params=17))
    fw.add_model(RobustnessProfile('Qwen3-235B', ecr=0.169, cci=0.663, params=235))
    
    return fw


if __name__ == '__main__':
    # Example usage
    fw = load_sample_data()
    
    print("=" * 160)
    print("UNIFIED ROBUSTNESS FRAMEWORK - ANALYSIS")
    print("=" * 160)
    print()
    
    # Compute metrics
    metrics = fw.compute_all_metrics()
    print("Full Metrics Table:")
    print(metrics[['Model', 'CSI', 'ECR', 'CCI', 'ORI', 'SEB', 'Robustness_Type']].to_string())
    print()
    
    # Correlation analysis
    print("\nCorrelation Analysis:")
    corrs = fw.correlation_analysis()
    for pair, (r, p) in corrs.items():
        if not np.isnan(r):
            print(f"  {pair}: r={r:+.4f}, p={p:.4f}")
    print()
    
    # Ranking
    print("\nRanking by ORI (Overall Robustness Index):")
    ranking = fw.ranking_by_ori()
    for idx, (i, row) in enumerate(ranking.iterrows(), 1):
        print(f"  {idx}. {row['Model']:30s} ORI={row['ORI']:.4f} SEB={row['SEB']:.4f} {row['Robustness_Type']}")
    print()
    
    # Summary by type
    print("\nSummary by Robustness Type:")
    summary = fw.summary_stats()
    for rtype, stats in summary.items():
        print(f"\n  {rtype} (n={stats['count']}):")
        print(f"    Models: {', '.join(stats['models'])}")
        print(f"    Avg CSI: {stats['mean_csi']:.4f}" if not np.isnan(stats['mean_csi']) else f"    Avg CSI: N/A")
        print(f"    Avg ECR: {stats['mean_ecr']:.4f}" if not np.isnan(stats['mean_ecr']) else f"    Avg ECR: N/A")
