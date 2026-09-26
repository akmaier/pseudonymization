#!/bin/bash
#SBATCH --job-name=leakprof_enron
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=06:00:00
#SBATCH --output=logs/leakprof_enron_%j.out
#SBATCH --error=logs/leakprof_enron_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
PYTHONPATH=src .venv/bin/python experiments/leakage_profile.py --corpus enron --out results/detection
