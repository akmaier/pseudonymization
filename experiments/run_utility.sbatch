#!/bin/bash
# §8.3 utility, in a CPU allocation.
#
# Two of the three CARDIO:DE tasks are gateway calls and would sit happily on the head node, but
# NER agreement loads Presidio, and Presidio on the head node is what was SIGKILLed three times.
# One allocation covers all three rather than splitting the run across two machines.
#
# Partition and account come from SBATCH_PARTITION / SBATCH_ACCOUNT; source config/env.sh first.
#
#SBATCH --job-name=run_utility
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=24:00:00
#SBATCH --output=logs/run_utility_%x_%j.out
#SBATCH --error=logs/run_utility_%x_%j.err

set -euo pipefail
R="${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p "$R/logs"
cd "$R"

CORPUS="${CORPUS:-cardiode}"
# **Sequentially, not one job per rule.** Every rule's patch set is scored by the same frozen models
# through the same gateway, so four parallel jobs would contend for one deployment and finish no
# sooner in total -- while making each one's throughput, and therefore its ETA, unreadable.
RULES="${RULES:-${RULE:-union}}"

echo "host      $(hostname)"
echo "corpus    ${CORPUS}  rules ${RULES}"
echo "started   $(date -Is)"

for RULE in $RULES; do
    echo
    echo "=== rule ${RULE} === $(date -Is)"
    PYTHONPATH=src "$R/.venv/bin/python" experiments/run_utility.py \
        --corpus "${CORPUS}" --rule "${RULE}"
done

echo "finished  $(date -Is)"
