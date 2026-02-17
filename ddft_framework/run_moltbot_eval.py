#!/usr/bin/env python3
"""
MoltBot DDFT Evaluation Runner

Run from the repository root:
    python run_moltbot_eval.py run --all
    python run_moltbot_eval.py run --experiment crustafarianism
    python run_moltbot_eval.py analyze moltbot_results/*.json
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from moltbot.cli import main

if __name__ == "__main__":
    sys.exit(main())
