#!/usr/bin/env bash
# Utility over the whole operating-point plane (plan §8.5), both released conditions.
#
# CPU only, no gateway, no GPU: the instruments are a TF-IDF vectoriser and a logistic regression
# loaded from disk. Measured on CARDIO:DE at 3.67 span sources a minute single-threaded, so the
# 2,154 sources are about ten core-hours; six tasks bring that inside two hours of wall clock.
#
# Round-robin sharding, not contiguous blocks: `plan` emits singletons before pairs before triples
# and the cost rises with the size, so contiguous blocks would hand the last task every triple.
#
# Each task writes its own file. A threading.Lock does not cross processes and two Slurm tasks
# appending to one destination corrupted two A4 rows on 2026-10-01; merge afterwards.
#
#SBATCH --job-name=util_sweep
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=24:00:00
#SBATCH --output=logs/util_sweep_%A_%a.out
#SBATCH --error=logs/util_sweep_%A_%a.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/utility_sweep
# Pinned to the allocation: an unpinned OpenBLAS took a 32-core node to CPULoad 45 during the
# leakage sweep and cut per-task throughput by a third.
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
N="${SHARDS:-6}"
I="${SLURM_ARRAY_TASK_ID:-0}"
echo "host=$(hostname) corpus=${CORPUS:?set CORPUS} shard=$I/$N started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/sweep_utility.py \
    --corpus "$CORPUS" --shard-index "$I" --shard-of "$N" ${EXTRA:-}
echo "finished=$(date -Is)"
