#!/usr/bin/env bash
# The detection plane again, with the CODE sanity rule of construction.py in force (AM 2026-09-27).
#
# This is not a re-run for its own sake. experiments/prune_affected_rows.py diffs this plane against
# results/detection/enron.jsonl source by source, and every source whose detection row is unchanged
# keeps its leakage row: an identical detection row means an identical span set, so the expensive
# attack numbers do not have to be computed again. Only the sources that actually moved are deleted
# and recomputed by the leakage array.
#
# CPU only, no construction, no attacks -- set arithmetic over the cached spans.
#SBATCH --job-name=detect_filtered
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --output=logs/detect_filtered_%j.out
#SBATCH --error=logs/detect_filtered_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/detection_filtered
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
export NUMEXPR_NUM_THREADS="$OMP_NUM_THREADS"
echo "host=$(hostname) corpus=${CORPUS:-enron} started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/score_detection.py \
    --corpus "${CORPUS:-enron}" --out results/detection_filtered
echo "finished=$(date -Is) rows=$(wc -l < "results/detection_filtered/${CORPUS:-enron}.jsonl" 2>/dev/null || echo 0)"
