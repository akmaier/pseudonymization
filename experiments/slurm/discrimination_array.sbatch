#!/usr/bin/env bash
# The discrimination surface (plan §8.3) over a corpus's whole plane, one shard per array task.
#
# CPU only, no model calls. Each span source rebuilds condition B in memory and fits a handful of
# small logistic regressions, so a task is set arithmetic plus seconds of sklearn per source. The
# shards are the leakage sweep's own (results/leakage_sweep/shards/<corpus>_NN.txt), so the two
# sweeps cover the identical span sources and their rows join on the label. Resumable.
#
#SBATCH --job-name=discrim
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=24:00:00
#SBATCH --output=logs/discrim_%A_%a.out
#SBATCH --error=logs/discrim_%A_%a.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/discrimination
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"; export MKL_NUM_THREADS="$OMP_NUM_THREADS"
CORPUS="${CORPUS:?set CORPUS}"
NN=$(printf '%02d' "$SLURM_ARRAY_TASK_ID")
echo "host=$(hostname) corpus=${CORPUS} task=${NN} started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/discrimination_surface.py \
    --corpus "$CORPUS" \
    --sources "results/leakage_sweep/shards/${CORPUS}_${NN}.txt" \
    --variants "results/phase1/${CORPUS}_variants.json" \
    --out "results/discrimination/${CORPUS}_${NN}.jsonl"
status=$?
echo "finished=$(date -Is) exit=${status}"
exit $status
