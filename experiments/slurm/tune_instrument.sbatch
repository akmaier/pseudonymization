#!/usr/bin/env bash
# Search for a utility instrument that clears its own baseline (§8.3). CPU only, no gateway.
#
# Enron's folder classifier is the reason this exists: word unigrams reached 0.2530 against a
# majority-class rate of 0.2621, so it could not have shown a loss under B or C whatever the
# release did. Seven configurations, cheapest first, each ~20 min at 29k messages and 176 labels.
#
#SBATCH --job-name=tune_inst
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=24:00:00
#SBATCH --output=logs/tune_inst_%j.out
#SBATCH --error=logs/tune_inst_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/instruments
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
echo "host=$(hostname) corpus=${CORPUS:?} task=${TASK:?} started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/tune_instrument.py \
    --corpus "$CORPUS" --task "$TASK" ${EXTRA:-}
echo "finished=$(date -Is)"
