
import json
import glob
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# --- Data Loading and Processing ---

def load_and_process_data():
    """Loads all result files and extracts the data needed for the heatmap."""
    data = []
    # Find all result files
    result_files = glob.glob('results/results_*.json')

    if not result_files:
        print("Warning: No result files found in the 'results/' directory.")
        return pd.DataFrame()

    for f_path in result_files:
        with open(f_path, 'r') as f:
            try:
                content = json.load(f)
                # Extract the required fields
                model = content.get('model', 'Unknown Model')
                domain = content.get('domain', 'Unknown Domain')
                csi = content.get('analysis', {}).get('CSI')

                if csi is not None:
                    data.append({
                        'Model': model,
                        'Domain': domain.replace('_', ' ').title(), # Clean up domain names for display
                        'CSI': csi
                    })
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON from {f_path}")
                continue
    
    return pd.DataFrame(data)

def create_heatmap(df):
    """Generates and saves the heatmap from the processed DataFrame."""
    if df.empty:
        print("Cannot generate heatmap: DataFrame is empty.")
        return

    # Create a pivot table for the heatmap
    pivot_table = df.pivot_table(index='Model', columns='Domain', values='CSI')

    # Reorder columns for logical grouping
    ordered_domains = [
        'Logic', 'Physics', 'Mathematics', 'Linguistics', 
        'Biology', 'Computer Science', 'Ethics', 'Art'
    ]
    pivot_table = pivot_table[ordered_domains]

    # --- Plotting ---
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))

    sns.heatmap(
        pivot_table, 
        annot=True, 
        fmt=".3f", 
        linewidths=.5, 
        cmap="viridis_r", # Use a reversed colormap where lower CSI (better) is greener
        ax=ax
    )

    # --- Formatting ---
    ax.set_title('Heatmap of Comprehension Stability Index (CSI) by Model and Domain', fontsize=16, pad=20)
    ax.set_xlabel('Conceptual Domain', fontsize=12)
    ax.set_ylabel('Model', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)

    plt.tight_layout()
    plt.savefig('csi_heatmap.png', dpi=300)
    print("Heatmap saved as csi_heatmap.png")
    plt.show()

if __name__ == '__main__':
    # Main execution block
    processed_df = load_and_process_data()
    create_heatmap(processed_df)
