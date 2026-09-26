#!/bin/bash
# The informed adversaries, on the recommended 13-detector release rather than the 15-detector one,
# so the whole A4 paragraph describes one ensemble.
#SBATCH --job-name=a4_inf13
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=logs/a4_inf13_%x_%j.out
#SBATCH --error=logs/a4_inf13_%x_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/leakage
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/a4_informed.py --corpus tab --rule union --a4-limit 200 --mode "$MODE"
