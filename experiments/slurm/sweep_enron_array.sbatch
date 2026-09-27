#!/usr/bin/env bash
# The Enron operating-point sweep: A2, A3 and A5 at every one of the 2,150 span sources, so the
# attack column exists at every point of the sensitivity/specificity plane (paper 2, AM 2026-09-27).
#
# CPU only. Detection is already cached at 100% coverage for all 15 detectors, so no model runs
# here: each task is set arithmetic, an in-memory condition-B build, a cosine and a small numpy fit.
#
# Resumable by design. sweep_leakage.py reads the rows already in its destination and skips those
# span sources, so a task killed by the wall clock is continued by resubmitting the same array.
# That is why the wall time is the 24 h soft limit rather than a guess at the true duration.
#
# Each task writes its OWN destination under results/leakage_sweep/shards/<NN>/ . Tasks
# appending to one file would interleave lines. experiments/merge_sweep_shards.py joins them after.
#
#SBATCH --job-name=sweep_enron
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=84G
#SBATCH --time=24:00:00
#SBATCH --array=0-7
#SBATCH --output=logs/sweep_enron_%A_%a.out
#SBATCH --error=logs/sweep_enron_%A_%a.err
# mem=84G fits the 90 GB nodes; 96G was used by leak_ablation but excludes the smallest, and 160G
# is above every node and is rejected outright.
#
# EIGHT tasks, not eleven: AssocMaxSubmitJobLimit is 8 and it counts array elements, so an 11-task
# array is refused at submit. 269 sources per task at the ~257 s the sweep's own docstring records
# for Enron is about 19 h against the 24 h soft limit; if a task is killed by the clock, resubmit
# the same array and it continues from its own destination.
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
# env.sh carries PSEUDONYMKIT_WORK and PSEUDONYMKIT_DUA. pseudonymkit.paths refuses to guess the
# DUA root and stops the process when it is unset, so this must come before any python call --
# sweep_leakage's CORPORA table names cardiode even for an Enron run.
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/leakage_sweep/shards

NN=$(printf '%02d' "$SLURM_ARRAY_TASK_ID")
SOURCES="results/leakage_sweep/shards/enron_${NN}.txt"
OUT="results/leakage_sweep/shards/${NN}"
mkdir -p "$OUT"
DEST="${OUT}/enron_PERSON.jsonl"
touch "$DEST"

echo "host=$(hostname) task=${SLURM_ARRAY_TASK_ID} sources=${SOURCES} started=$(date -Is)"
echo "planned $(wc -l < "$SOURCES") span sources; already done $(wc -l < "$DEST")"

PYTHONPATH=src .venv/bin/python experiments/sweep_leakage.py \
    --corpus enron \
    --entity-type PERSON \
    --sources "$SOURCES" \
    --out "$OUT" \
    --max-size 3 \
    --seed 0 \
    --folds 5

status=$?
echo "finished=$(date -Is) exit=${status} rows=$(wc -l < "$DEST")"
exit $status
