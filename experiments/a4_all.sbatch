#!/bin/bash
# A4 re-run after the auxiliary-context fix of 2026-09-22.
#
# The context arm used to draw its evidence windows from condition A for every condition it scored,
# so attacking the release handed the attacker the name-to-context binding pseudonymisation exists
# to break. Fixed; these are the numbers that replace it. The no-context arm is unaffected but is
# re-run alongside so both arms come from one pass and stay comparable.
#
#SBATCH --job-name=a4_redo
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/leakage
for CORPUS in tab cardiode ontonotes; do
    echo "=== $CORPUS $(date -Is) ==="
    PYTHONPATH=src .venv/bin/python experiments/run_leakage.py --corpus "$CORPUS" \
        --rule union --attacks a4 --a4-limit "${LIMIT:-200}" || echo "  $CORPUS FAILED"
done
echo "=== done $(date -Is) ==="
