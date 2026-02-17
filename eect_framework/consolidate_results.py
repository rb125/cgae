
import json
import os

results_dir = "results"
consolidated_results = {}
for filename in os.listdir(results_dir):
    if filename.endswith("_eect_results.json"):
        model_name = filename.replace("_eect_results.json", "")
        with open(os.path.join(results_dir, filename), "r") as f:
            consolidated_results[model_name] = json.load(f)

output_path = os.path.join(results_dir, "consolidated_eect_results.json")
with open(output_path, "w") as f:
    json.dump(consolidated_results, f, indent=2)

print(f"Consolidated results saved to {output_path}")
