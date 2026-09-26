#!/bin/bash
#SBATCH --job-name=expo_release
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=06:00:00
#SBATCH --output=logs/expo_release_%j.out
#SBATCH --error=logs/expo_release_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/exposure_from_release.py
