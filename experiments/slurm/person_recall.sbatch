#!/bin/bash
#SBATCH --job-name=person_recall
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=04:00:00
#SBATCH --output=logs/person_recall_%j.out
#SBATCH --error=logs/person_recall_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/person_recall.py
