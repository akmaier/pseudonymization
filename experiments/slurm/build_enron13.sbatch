#!/bin/bash
#SBATCH --job-name=build_enron13
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=08:00:00
#SBATCH --output=logs/build_enron13_%j.out
#SBATCH --error=logs/build_enron13_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
ENS=$(cat results/leakage_sweep/large_ensemble.txt | tr '+' ' ')
.venv/bin/python experiments/build_BC.py --corpus enron --detectors $ENS --rule union --conditions B C
