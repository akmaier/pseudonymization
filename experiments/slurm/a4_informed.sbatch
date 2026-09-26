#!/bin/bash
# A4 against an adversary who knows the release was pseudonymised (AM, 2026-09-25).
#
# The patch sets prove that conditions B and C replace identical spans, so the C release is a text
# rewrite of the B release and cannot carry information B lacks.  The measured gap is the ranker
# believing the surrogate.  These two arms measure what a realistic attacker recovers: one masks
# name-like spans with a public name list, the other is simply told the scheme.
#
#SBATCH --job-name=a4_informed
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=logs/a4_informed_%j.out
#SBATCH --error=logs/a4_informed_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/leakage
. config/env.sh
export PYTHONPATH=src
for MODE in forewarned mask; do
    echo; echo "=== tab / $MODE === $(date -Is)"
    .venv/bin/python experiments/a4_informed.py --corpus tab --rule union \
        --a4-limit 200 --mode "$MODE" || echo "  FAILED: $MODE"
done
echo; echo "=== done === $(date -Is)"
