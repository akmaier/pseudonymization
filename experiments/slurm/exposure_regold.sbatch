#!/bin/bash
#SBATCH --job-name=exposure_regold
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=04:00:00
#SBATCH --output=logs/exposure_regold_%j.out
#SBATCH --error=logs/exposure_regold_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/detection
. config/env.sh
export PYTHONPATH=src
date +'start %H:%M:%S'
.venv/bin/python -u experiments/exposure_denominators.py
date +'end   %H:%M:%S'
