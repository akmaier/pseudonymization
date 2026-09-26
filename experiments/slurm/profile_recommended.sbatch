#!/bin/bash
# Exposure at document, case and entity denominators for the recommended 13-detector union.
#
# Bernhard Kainz, 2026-09-25: the exposure figures in the draft belong to the max-sensitivity
# operating point, not to the ensemble the paper recommends, and 7 clear-text names over 400 letters
# cannot sit beside 7 % of patients.  This recomputes both denominators for the ensemble actually
# recommended, so the table and the prose describe one release.
#
#SBATCH --job-name=profile_rec
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=06:00:00
#SBATCH --output=logs/profile_rec_%j.out
#SBATCH --error=logs/profile_rec_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/leakage
. config/env.sh
export PYTHONPATH=src
for CORPUS in cardiode tab ontonotes enron; do
    echo; echo "=== $CORPUS === $(date -Is)"
    .venv/bin/python experiments/leakage_profile.py --corpus "$CORPUS" \
        --points results/detection/recommended_points.json \
        --out results/leakage/${CORPUS}_recommended_profile.json || echo "  FAILED: $CORPUS"
done
echo; echo "=== done === $(date -Is)"
