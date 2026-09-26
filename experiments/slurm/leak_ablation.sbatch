#!/bin/bash
#SBATCH --job-name=leak_ablation
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=08:00:00
#SBATCH --output=logs/leak_ablation_%j.out
#SBATCH --error=logs/leak_ablation_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/leak_ablation.py
