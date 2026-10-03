#!/usr/bin/env bash
#SBATCH --job-name=linear_a4
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --output=logs/linear_a4_%j.out
#SBATCH --error=logs/linear_a4_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/phase1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"; export MKL_NUM_THREADS="$OMP_NUM_THREADS"
echo "host=$(hostname) corpus=${CORPUS} started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/run_linear_a4.py --corpus "$CORPUS" ${EXTRA:-}
echo "finished=$(date -Is)"
