#!/bin/bash
#SBATCH --job-name=a4_cardiode
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=24:00:00
#SBATCH --output=logs/a4_%x_%j.out
#SBATCH --error=logs/a4_%x_%j.err
set -euo pipefail
cd "$PSEUDONYMKIT_WORK"
PYTHONPATH=src .venv/bin/python experiments/run_leakage.py --corpus cardiode   --rule "${RULE:-union}" --attacks a4 --a4-limit "${LIMIT:-200}"
