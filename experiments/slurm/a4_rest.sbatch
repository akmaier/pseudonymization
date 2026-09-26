#!/bin/bash
# A4 — the LLM ranked-candidate attack — on the three corpora it has not been run on.
#
# §9 lists A4 across conditions A, B and C with no corpus restriction, and results/leakage/ held only
# CARDIO:DE. The attack is gateway-bound rather than CPU-bound, and small: a stratified sample of
# queries per condition, each presented with N candidates. Three corpora in one allocation because
# the QOS submit limit is eight jobs and the leakage chain and four utility runs hold the rest.
#
#SBATCH --job-name=a4_rest
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=logs/a4_rest_%j.out
#SBATCH --error=logs/a4_rest_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs results/leakage
export PYTHONPATH=src
for CORPUS in tab ontonotes enron; do
    for RULE in union vote; do
        echo; echo "=== ${CORPUS} / ${RULE} === $(date -Is)"
        .venv/bin/python experiments/run_leakage.py \
            --corpus "$CORPUS" --rule "$RULE" --attacks a4 || echo "  FAILED: ${CORPUS}/${RULE}"
    done
done
echo; echo "=== done === $(date -Is)"
