#!/bin/bash
#SBATCH --job-name=lsweep
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=24:00:00
#SBATCH --output=logs/lsweep_%x_%j.out
#SBATCH --error=logs/lsweep_%x_%j.err
set -euo pipefail
cd "$PSEUDONYMKIT_WORK"
PYTHONPATH=src .venv/bin/python experiments/sweep_leakage.py --corpus "${CORPUS:-cardiode}"   --max-size "${MAXSIZE:-3}" --entity-type "${ET:-PERSON}"
