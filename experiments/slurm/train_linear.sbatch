#!/usr/bin/env bash
# Fit the frozen linear utility instruments (plan §8.5). CPU only, no gateway, no GPU.
#
# CARDIO:DE fits on the login node in under three minutes and does not need this. Enron does:
# 58,636 documents, a 176-label folder task, and a multinomial logistic regression whose
# coefficient array alone is 176 x max_features. score_recommended.py was OOM-killed on the head
# node on Enron for less, so it goes through Slurm.
#
#SBATCH --job-name=train_linear
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=logs/train_linear_%j.out
#SBATCH --error=logs/train_linear_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/instruments
# BLAS threads pinned to the allocation: an unpinned OpenBLAS took a 32-core node to CPULoad 45
# during the leakage sweep and halved per-task throughput.
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
echo "host=$(hostname) corpus=${CORPUS:?set CORPUS} started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/train_linear_tasks.py --corpus "$CORPUS" ${EXTRA:-}
echo "finished=$(date -Is)"
