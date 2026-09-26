#!/bin/bash
#SBATCH --job-name=table_split
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=logs/table_split_%j.out
#SBATCH --error=logs/table_split_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/table_split.py
