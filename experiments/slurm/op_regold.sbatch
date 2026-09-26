#!/bin/bash
#SBATCH --job-name=op_regold_iw
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=04:00:00
#SBATCH --output=logs/op_regold_iw_%j.out
#SBATCH --error=logs/op_regold_iw_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/enron_operating_points_regold.py
