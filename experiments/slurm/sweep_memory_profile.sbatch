#!/usr/bin/env bash
# Attribute the Enron sweep's resident set to a stage (AM, 2026-09-27).
#SBATCH --job-name=sweepmem
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=110G
#SBATCH --time=01:00:00
#SBATCH --output=logs/sweepmem_%j.out
#SBATCH --error=logs/sweepmem_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
echo "host=$(hostname) started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/probes/sweep_memory_profile.py "${CORPUS:-enron}"
echo "finished=$(date -Is)"
