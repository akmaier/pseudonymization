#!/bin/bash
# The §8.1 sweep, in a CPU allocation rather than on the head node.
#
# It belongs here for the same reason Presidio does: the head node terminates long-lived processes.
# The first full CARDIO:DE sweep died silently at roughly 1,600 of 2,151 span sources, with no
# traceback and no completion line — the signature of that reaper, not of a bug. The driver resumes
# from its own output, so a kill costs the source in flight rather than the run.
#
# No GPU: this is set arithmetic over a cached span layer and a pass over pre-tokenised documents.
#
# Partition and account come from SBATCH_PARTITION / SBATCH_ACCOUNT in the environment; source
# config/env.sh before submitting.
#
#SBATCH --job-name=score_detection
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=24:00:00
#SBATCH --output=logs/score_detection_%x_%j.out
#SBATCH --error=logs/score_detection_%x_%j.err

set -euo pipefail
R="${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p "$R/logs"
cd "$R"

CORPUS="${CORPUS:-cardiode}"
MAXSIZE="${MAXSIZE:-3}"
# RESTART=1 discards an existing file: needed whenever the gold layer changes, since
# entity-level recall depends on the gold entity ids.
RESTART="${RESTART:-}"

echo "host      $(hostname)"
echo "corpus    ${CORPUS}  max ensemble size ${MAXSIZE}"
echo "started   $(date -Is)"

PYTHONPATH=src "$R/.venv/bin/python" experiments/score_detection.py \
    --corpus "${CORPUS}" --max-size "${MAXSIZE}" ${RESTART:+--restart}

echo "finished  $(date -Is)"
