
import json
import glob
import numpy as np
from scipy.optimize import curve_fit
from scipy.interpolate import UnivariateSpline
import os

def logistic_function(x, L, k, x0):
    """
    A standard logistic function.
    L: the curve's maximum value
    k: the logistic growth rate or steepness of the curve
    x0: the x-value of the sigmoid's midpoint
    """
    try:
        return L / (1 + np.exp(-k * (x - x0)))
    except (RuntimeWarning, OverflowError):
        return np.inf

def calculate_r_squared(y_true, y_pred):
    """Calculates the R-squared value."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0:
        # Handle case where the total sum of squares is zero (e.g., constant data)
        return 1.0 if ss_res == 0 else 0.0
    return 1 - (ss_res / ss_tot)

def analyze_file(filepath):
    """
    Analyzes a single result file, fits logistic and spline models,
    and returns the R-squared values and other metrics.
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None, None, None, None, None

    model_name = data.get("model")
    domain_name = data.get("domain")
    performance_data = data.get("performance", [])

    if not performance_data:
        return model_name, domain_name, None, None, None

    # Sort by context length to ensure correct normalization and plotting
    performance_data.sort(key=lambda p: p.get("context_length", 0))

    scores = np.array([p.get("score", 0) for p in performance_data])
    context_lengths = np.array([p.get("context_length", 0) for p in performance_data])

    # Normalize context length to get 'c'
    max_context = np.max(context_lengths)
    if max_context == 0:
        return model_name, domain_name, None, None, None
        
    # The paper defines c=0 as max compression (min words) and c=1 as min compression (max words).
    # The raw context_length is word count, so we need to normalize it accordingly.
    c_values = context_lengths / max_context

    # --- Logistic Fit ---
    r_squared_logistic = None
    inflection_point = None
    try:
        # Provide reasonable initial guesses for the parameters [L, k, x0]
        # L ~ max score, k ~ 1 (can be negative), x0 ~ mean c
        initial_guesses = [np.max(scores), 1, np.mean(c_values)]
        popt, _ = curve_fit(logistic_function, c_values, scores, p0=initial_guesses, maxfev=5000)
        y_pred_logistic = logistic_function(c_values, *popt)
        r_squared_logistic = calculate_r_squared(scores, y_pred_logistic)
        inflection_point = popt[2] # x0 is the inflection point
    except (RuntimeError, ValueError):
        r_squared_logistic = np.nan # Could not fit

    # --- Spline Fit ---
    r_squared_spline = None
    try:
        # Use a smoothing spline to avoid overfitting
        # The smoothing factor 's' is crucial. Start with a reasonable value.
        # s = len(scores) * np.var(scores) is a common heuristic
        spline = UnivariateSpline(c_values, scores, s=len(scores)*np.var(scores)*0.1)
        y_pred_spline = spline(c_values)
        r_squared_spline = calculate_r_squared(scores, y_pred_spline)
    except Exception:
        r_squared_spline = np.nan # Could not fit

    return model_name, domain_name, r_squared_logistic, r_squared_spline, inflection_point

def main():
    """
    Main function to find all result files, analyze them, and print a summary.
    """
    results_path = "/home/rahul/arXiv/CDCT/cdct_framework/results"
    result_files = glob.glob(os.path.join(results_path, "*.json"))

    all_results = []
    for filepath in result_files:
        model, domain, r2_log, r2_spline, c0 = analyze_file(filepath)
        if model is not None:
            all_results.append({
                "model": model,
                "domain": domain,
                "r2_logistic": r2_log,
                "r2_spline": r2_spline,
                "inflection_c0": c0
            })

    # Sort results for consistent output
    all_results.sort(key=lambda x: (x["model"], x["domain"]))

    # Print header
    print(f"{ 'Model':<25} { 'Domain':<20} { 'R² Logistic':<15} { 'R² Spline':<15} { 'Inflection (c0)':<20}")
    print("="*95)

    # Print results
    for res in all_results:
        r2_log_str = f"{res['r2_logistic']:.4f}" if res['r2_logistic'] is not None else "N/A"
        r2_spline_str = f"{res['r2_spline']:.4f}" if res['r2_spline'] is not None else "N/A"
        c0_str = f"{res['inflection_c0']:.4f}" if res['inflection_c0'] is not None else "N/A"
        print(f"{res['model']:<25} {res['domain']:<20} {r2_log_str:<15} {r2_spline_str:<15} {c0_str:<20}")

    # --- Aggregate Analysis ---
    print("\n" + "="*40)
    print("Aggregate R-squared values")
    print("="*40)
    
    # Filter out failed fits (NaNs) before calculating mean
    valid_logistic_r2 = [r['r2_logistic'] for r in all_results if r['r2_logistic'] is not None and not np.isnan(r['r2_logistic'])]
    valid_spline_r2 = [r['r2_spline'] for r in all_results if r['r2_spline'] is not None and not np.isnan(r['r2_spline'])]

    if valid_logistic_r2:
        avg_r2_logistic = np.mean(valid_logistic_r2)
        print(f"Average R² (Logistic): {avg_r2_logistic:.4f}")
    if valid_spline_r2:
        avg_r2_spline = np.mean(valid_spline_r2)
        print(f"Average R² (Spline):   {avg_r2_spline:.4f}")

    print(f"\nAnalysis based on {len(all_results)} experiment files.")
    print("The 'Inflection (c0)' is the critical compression threshold from the logistic model.")
    print("It indicates the point of steepest performance decay. A lower c0 is better.")


if __name__ == "__main__":
    main()
