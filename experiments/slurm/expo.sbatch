#!/bin/bash
#SBATCH --job-name=expo_denom
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=06:00:00
#SBATCH --output=logs/expo_denom_%j.out
#SBATCH --error=logs/expo_denom_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/exposure_denominators.py
