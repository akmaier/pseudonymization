#!/usr/bin/env bash
#SBATCH --job-name=build_sample
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --output=logs/build_sample_%j.out
#SBATCH --error=logs/build_sample_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/conditions
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"; export MKL_NUM_THREADS="$OMP_NUM_THREADS"
echo "host=$(hostname) corpus=${CORPUS:-cardiode} started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/build_sample_conditions.py --corpus "${CORPUS:-cardiode}"
echo "finished=$(date -Is)"
