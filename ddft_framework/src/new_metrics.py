
import pandas as pd
import numpy as np

def calculate_sf(df):
    """
    SF = SAS_Turn4 - SAS_Turn5
    If Turn 4 or 5 is missing, SF is undefined (0).
    """
    results = []
    for (model, concept, compression), group in df.groupby(['model', 'concept', 'compression']):
        sas_turn4 = group[group['turn'] == 4]['SAS'].mean()
        sas_turn5 = group[group['turn'] == 5]['SAS'].mean()
        
        if pd.notna(sas_turn4) and pd.notna(sas_turn5):
            sf = sas_turn4 - sas_turn5
        else:
            sf = 0
            
        results.append({
            'model': model,
            'concept': concept,
            'compression': compression,
            'SF': sf
        })
        
    return pd.DataFrame(results)

def calculate_cri(df):
    """
    CRI = Area under the SAS curve (Integral of SAS over compression).
    Normalized to be between 0 and 1.
    """
    results = []
    for (model, concept), group in df.groupby(['model', 'concept']):
        sas_by_c = group.groupby('compression')['SAS'].mean().sort_index()
        
        if len(sas_by_c) > 1:
            # Trapezoidal rule for area
            cri = np.trapz(sas_by_c.values, sas_by_c.index)
            # Normalize by max possible area (SAS=1)
            max_area = sas_by_c.index.max() - sas_by_c.index.min()
            cri = cri / max_area if max_area > 0 else 0
        else:
            cri = 0
            
        results.append({
            'model': model,
            'concept': concept,
            'CRI': cri
        })
        
    return pd.DataFrame(results)

def calculate_far_prime(df):
    """
    FAR' = Average FAR for turns where SAS < 0.5.
    """
    # Filter for turns where SAS < 0.5
    far_prime_df = df[df['SAS'] < 0.5]
    
    # Calculate average FAR
    results = far_prime_df.groupby(['model', 'concept'])['FAR'].mean().reset_index()
    results.rename(columns={'FAR': "FAR'"}, inplace=True)
    
    return results
    
def calculate_sas_prime(df):
    """
    SAS' = Average SAS for turns where FAR > 0.20.
    """
    # Filter for turns where FAR > 0.2
    sas_prime_df = df[df['FAR'] > 0.2]
    
    # Calculate average SAS
    results = sas_prime_df.groupby(['model', 'concept'])['SAS'].mean().reset_index()
    results.rename(columns={'SAS': "SAS'"}, inplace=True)
    
    return results

def calculate_ci_new(hoc_df, cri_df, far_prime_df, sas_prime_df):
    """
    CI = (HOC * CRI) / (FAR' + (1 - SAS'))
    """
    # Merge all metrics
    merged = hoc_df.merge(cri_df, on=['model', 'concept'])
    merged = merged.merge(far_prime_df, on=['model', 'concept'])
    merged = merged.merge(sas_prime_df, on=['model', 'concept'])

    # Handle potential division by zero
    denominator = merged["FAR'"] + (1 - merged["SAS'"])
    
    # Calculate CI, handling division by zero or NaN values
    merged['CI_new'] = np.divide(
        merged['HOC'] * merged['CRI'],
        denominator,
        out=np.zeros_like(merged['HOC']),  # Default to 0
        where=(denominator != 0)
    )
    
    # Normalize CI to be between 0 and 1
    max_ci = merged['CI_new'].max()
    if max_ci > 0:
        merged['CI_new'] /= max_ci
        
    return merged
