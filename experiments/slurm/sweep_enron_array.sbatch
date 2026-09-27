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
#SBATCH --cpus-per-task=16
#SBATCH --mem=24G
# 16 cores, not 8, to SPREAD rather than PACK (AM, 2026-09-27). Slurm is select/cons_res with
# CR_CORE_MEMORY and best-fit placement, so at 8 cores a task four of them land on one 32-core node
# while lme221/222/223 sit idle. At 16 a 32-core node takes exactly two, so ten tasks occupy five
# or six nodes and each gets its own memory bandwidth and L3 rather than sharing one node's.
# The controller knows ten nodes in one partition -- there is no hidden partition -- and lme51 is
# down with lme52 drained, so eight are usable and six of those have 32 cores.
#SBATCH --time=24:00:00
#SBATCH --array=0-9
#SBATCH --output=logs/sweep_enron_%A_%a.out
#SBATCH --error=logs/sweep_enron_%A_%a.err
# mem=24G, because the MEASURED peak is 11.92 GiB (experiments/probes/sweep_memory_profile.py,
# 2026-09-27) and the two frees added the same day take it lower. The earlier 84G was a guess, and
# it was the whole problem: Slurm reserved it as AllocMem on every node, the job never touched it,
# and the reservation -- not the job -- is what kept a second task off the node. Do not raise this
# without re-running the profile.
#
# TEN tasks under the turbo QOS, which allows 10 concurrent against miti's 4 and 100 submitted
# against 8. Submit with:  sbatch --qos=turbo experiments/slurm/sweep_enron_array.sbatch
# At 14 shards over 2,150 sources that is ~154 each, and the measured 200 s per source puts a task
# at about 8.5 h -- one round, comfortably inside the 24 h soft limit. Resumable regardless.
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

# Pin the linear-algebra thread pools to the CPUs Slurm actually gave us. Without this the BLAS
# behind numpy sizes its pool from the NODE's core count, not the allocation: with three or four
# tasks packed onto one 32-core node that is 4 x 32 threads on 32 cores. Measured 2026-09-27 on
# lme49 -- CPULoad 45.50 against CPUAlloc 32 -- and it cost 57% of per-task throughput, 305 s per
# span source at one task per node against 480 s when packed. Nothing in the repo set these.
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
export NUMEXPR_NUM_THREADS="$OMP_NUM_THREADS"
export VECLIB_MAXIMUM_THREADS="$OMP_NUM_THREADS"

echo "host=$(hostname) task=${SLURM_ARRAY_TASK_ID} sources=${SOURCES} threads=${OMP_NUM_THREADS} started=$(date -Is)"
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
