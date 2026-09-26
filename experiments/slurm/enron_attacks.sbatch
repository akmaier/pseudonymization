#!/bin/bash
# Re-run the Enron attacks against the corrected gold, for the recommended ensemble only.
# A2's priors, A3/A5's gallery and truth map are all built from gold entities, so every one of them
# inherited the substring defect. Nothing is re-detected; the detector cache is untouched.
#SBATCH --job-name=enron_attacks
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=08:00:00
#SBATCH --output=logs/enron_attacks_%j.out
#SBATCH --error=logs/enron_attacks_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
. config/env.sh
export PYTHONPATH=src
cp results/leakage_sweep/enron_PERSON.jsonl results/leakage_sweep/enron_PERSON.oldgold.jsonl 2>/dev/null || true
.venv/bin/python experiments/sweep_leakage.py --corpus enron \
    --sources results/leakage_sweep/enron_recommended_only.txt --restart
