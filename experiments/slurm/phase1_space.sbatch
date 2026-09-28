#!/usr/bin/env bash
# Phase 1's expensive half: the release-derived candidate space and the attacker flagging counts.
#SBATCH --job-name=phase1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=24G
#SBATCH --time=24:00:00
#SBATCH --output=logs/phase1_%A_%a.out
#SBATCH --error=logs/phase1_%A_%a.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/phase1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"; export MKL_NUM_THREADS="$OMP_NUM_THREADS"
CORPUS="${CORPUS:-cardiode}"
NN=$(printf '%02d' "$SLURM_ARRAY_TASK_ID")
echo "host=$(hostname) corpus=${CORPUS} task=${NN} started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/person_candidate_space.py \
    --corpus "$CORPUS" \
    --sources "results/leakage_sweep/shards/${CORPUS}_${NN}.txt" \
    --out "results/phase1/${CORPUS}_${NN}.jsonl" \
    --variants "results/phase1/${CORPUS}_variants.json"
echo "finished=$(date -Is) exit=$?"
