
.PHONY: install analyze clean

# =============================================================================
# SETUP & INSTALLATION
# =============================================================================

install:
	@echo "--- Setting up Python virtual environment and installing dependencies ---"
	@python3 -m venv venv
	@./venv/bin/pip install --upgrade pip
	@./venv/bin/pip install -e .
	@echo "--- Installation complete. Activate with: source venv/bin/activate ---"

# =============================================================================
# CORE COMMANDS
# =============================================================================

analyze:
	@echo "--- Running DDFT analysis ---"
	@./venv/bin/python src/main.py --run-analysis
	@echo "--- Analysis complete. See results in paper_logic_rankings.csv ---"

analyze-new:
	@echo "--- Running DDFT analysis with new metrics ---"
	@./venv/bin/python src/analyze_results.py
	@echo "--- Analysis complete. See results in paper_logic_rankings.csv and new_metrics_rankings.csv ---"

# =============================================================================
# CLEANUP
# =============================================================================

clean:
	@echo "--- Cleaning up Python artifacts and virtual environment ---"
	@rm -rf venv
	@rm -rf .pytest_cache
	@rm -rf src/*.egg-info
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "--- Cleanup complete ---"

