#!/bin/bash
#SBATCH --job-name=pr_rules
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=03:00:00
#SBATCH --output=logs/pr_rules_%j.out
#SBATCH --error=logs/pr_rules_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/person_recall_rules.py
