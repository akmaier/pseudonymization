#!/bin/bash
# Recompute every Enron metric against the corrected gold. The detector cache and both patch sets
# are unchanged and already revalidated, so nothing is re-detected: this is scoring only.
#SBATCH --job-name=enron_remetric
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=06:00:00
#SBATCH --output=logs/enron_remetric_%j.out
#SBATCH --error=logs/enron_remetric_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
echo '=== both error rates, per rule ==='
.venv/bin/python experiments/per_language.py
echo '=== exposure against the release ==='
.venv/bin/python experiments/exposure_from_release.py
echo '=== header/body split ==='
.venv/bin/python experiments/enron_header_split.py
