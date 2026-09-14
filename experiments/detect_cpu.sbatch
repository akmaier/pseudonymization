#!/bin/bash
# Presidio, in a CPU allocation rather than on the head node.
#
# CPU work in this study runs on the head node (AM, 2026-09-12), and for the gateway pool — a network
# client that spends its life in recv() — that is right. Presidio is different, and the evidence is
# three killed runs: SIGKILL at tab 425/1268, SIGTERM at enron 4,005/58,636, SIGTERM again at enron
# 9,040/58,636. The third was *after* the runner was changed to stream the corpus in batches instead
# of holding it whole, so the cause is not our memory footprint. The node has 7 GB shared between
# users and something on it terminates our long-lived processes regardless. CARDIO:DE, TAB and
# OntoNotes did complete there; Enron's 58,636 documents will not.
#
# No GPU is requested: Presidio is spaCy pipelines and rule recognisers, and asking for a card would
# hold one idle for hours.
#
# Partition and account are NOT set here: Slurm reads SBATCH_PARTITION and SBATCH_ACCOUNT
# from the environment, and naming a group's account in a repository that ships with the
# paper is exactly what config/env.example.sh exists to avoid. Source config/env.sh first.
#SBATCH --job-name=detect_cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=logs/detect_cpu_%x_%j.out
#SBATCH --error=logs/detect_cpu_%x_%j.err
#
# Slurm redirects stdout/stderr *before* this script runs, so logs/ must exist at submit time or the
# job dies instantly with no log at all.

set -euo pipefail
R="${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p "$R/logs"
cd "$R"

CORPUS="${CORPUS:-enron}"
DETECTORS="${DETECTORS:-presidio}"
LIMIT="${LIMIT:-0}"
CACHE="${CACHE:-results/detector_cache}"
BATCH="${BATCH:-1000}"

echo "host      $(hostname)"
echo "job       ${SLURM_JOB_ID:-none}  corpus ${CORPUS}  detectors ${DETECTORS}  limit ${LIMIT}"
echo "memory    $(ulimit -v 2>/dev/null || echo unlimited) (ulimit -v)"
echo "started   $(date -Is)"

PYTHONPATH=src "$R/.venv/bin/python" experiments/detect_local.py \
    --detectors ${DETECTORS} \
    --corpora "${CORPUS}" \
    --device cpu \
    --stream-batch "${BATCH}" \
    --limit "${LIMIT}" \
    --cache "${CACHE}"

echo "finished  $(date -Is)"
