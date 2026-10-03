#!/usr/bin/env bash
# The gateway detectors (axis D's LLM levels) as one Slurm job.
#
# detect_gateway.py is a network client and has run as a plain process on the head node. It runs
# here as a single small job for two reasons that came up on 2026-10-03: a job can wait for another
# with --dependency, so a model whose deployment is busy with an A4 job starts when that job ends
# instead of contending with it -- or being parked behind a waiter loop on the head node, which is
# what had to be cleaned up that day; and a job is visible in squeue rather than in /tmp. One job,
# one CPU: the work is in recv(), and an array would only hold association slots doing nothing.
#
#   CORPORA   which condition-A corpora (default: enron2)
#   MODELS    gateway model ids, space-separated (default: detect_gateway.DEFAULT_MODELS)
#   CONC      requests in flight per model (default: 8)
#   CACHE     detector cache root (default: results/detector_cache). A standalone check that must
#             stay out of the plane's detector pool -- DeepSeek, AM 2026-10-01 -- gets its own root.
#
#SBATCH --job-name=detect_gw
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=24:00:00
#SBATCH --output=logs/detect_gw_%j.out
#SBATCH --error=logs/detect_gw_%j.err
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
. config/env.sh
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
echo "host=$(hostname) corpora=${CORPORA:-enron2} models=${MODELS:-default} cache=${CACHE:-results/detector_cache} started=$(date -Is)"
PYTHONPATH=src .venv/bin/python experiments/detect_gateway.py \
    --corpora ${CORPORA:-enron2} \
    ${MODELS:+--models $MODELS} \
    --concurrency "${CONC:-8}" \
    --cache "${CACHE:-results/detector_cache}"
rc=$?
echo "finished=$(date -Is) exit=$rc"
exit $rc
