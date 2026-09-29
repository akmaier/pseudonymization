#!/usr/bin/env bash
# PERSON sensitivity for the recommended whole-pool rules, which the size-3 detection sweep never
# reaches. Enron OOM'd when run on the login node (2026-09-29) -- 58,636 documents plus a scoring
# index is not login-node work, as the cluster rules say.
#SBATCH --job-name=score_rec
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=logs/score_rec_%j.out
#SBATCH --error=logs/score_rec_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
echo "host=$(hostname) corpus=${CORPUS:-enron} started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/score_recommended.py --corpus "${CORPUS:-enron}"
echo "finished=$(date -Is)"
