#!/bin/bash
# A2, A3 and A5 for the **whole-pool** ensembles — the ones the leakage sweep cannot reach.
#
# sweep_leakage enumerates subsets up to size three (§7's D" axis). The conditions that utility,
# stability and A4 are all measured on are built from the *entire* fifteen-detector pool under union
# and under vote, and those ensembles are therefore absent from every A2/A3/A5 number in the study
# except CARDIO:DE's, where run_leakage was run by hand.
#
# Both entity types, matching what CARDIO:DE already has.
#SBATCH --job-name=bigleak
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=24:00:00
#SBATCH --output=logs/bigleak_%x_%j.out
#SBATCH --error=logs/bigleak_%x_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/leakage
export PYTHONPATH=src
CORPORA="${CORPORA:-tab ontonotes}"
for CORPUS in $CORPORA; do
  for RULE in union vote; do
    for TYPE in PERSON ORG; do
      echo; echo "=== ${CORPUS} / ${RULE} / ${TYPE} === $(date -Is)"
      .venv/bin/python experiments/run_leakage.py --corpus "$CORPUS" --rule "$RULE" \
          --entity-type "$TYPE" --attacks a2 a3 a5 || echo "  FAILED ${CORPUS}/${RULE}/${TYPE}"
    done
  done
done
echo; echo "=== done === $(date -Is)"
