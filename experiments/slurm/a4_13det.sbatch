#!/bin/bash
# A4 on the recommended 13-detector union (AM, 2026-09-25: "A4 needs to run on the recommended 13").
#
# The earlier run took the 15-detector patch set, because run_leakage.py resolves its condition with
# sorted(glob(...))[0].  Conditions A is unmodified text and independent of the detector set, so only
# B and C are re-run.  One corpus and one context arm per job: the ranker calls the gateway serially,
# so four short jobs finish in a quarter of the wall-clock of one long one.
#
#SBATCH --job-name=a4_13
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=logs/a4_13_%x_%j.out
#SBATCH --error=logs/a4_13_%x_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/leakage
. config/env.sh
export PYTHONPATH=src
.venv/bin/python experiments/a4_ensemble.py --corpus "$CORPUS" \
    --tag union-single0.5-13det-1797ba --a4-limit 200 --context "$ARM"
