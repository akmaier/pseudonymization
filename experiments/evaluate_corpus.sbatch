#!/bin/bash
# Everything downstream of detection, for one corpus, in one CPU allocation.
#
# Detection is the only step that needs a GPU or the gateway. Once the cache is full, the rest is
# set arithmetic, HMAC, record linkage and tokenised scoring — CPU-bound, and none of it belongs on
# the head node, which reaps long-lived processes (that is how the first CARDIO:DE sweep died at
# roughly 1,600 of 2,151 sources with no traceback).
#
# Order matters and is not arbitrary:
#
#   1. score_detection   the §8.1 sweep over every subset up to size three
#   2. best_ensemble     picks the operating point for the cells below, from that sweep
#   3. build_BC          patch sets: the whole pool and the chosen three, under each rule
#   4. run_stability     §8.2, condition B only, needs the patch sets from 3
#   5. sweep_leakage     §9, builds its own conditions per span source, independent of 3
#
# Utility is deliberately NOT here. It is gateway-bound rather than CPU-bound, it runs for days on a
# corpus this size, and a wall clock that kills it would take steps 1-5 with it. It has its own job.
#
# Every step resumes from its own output, so a requeue costs the item in flight, not the stage.
#
#   . config/env.sh
#   CORPUS=tab sbatch experiments/evaluate_corpus.sbatch
#
#SBATCH --job-name=evaluate
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --output=logs/evaluate_%x_%j.out
#SBATCH --error=logs/evaluate_%x_%j.err

set -euo pipefail
R="${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p "$R/logs" "$R/results/detection" "$R/results/conditions" \
         "$R/results/stability" "$R/results/leakage_sweep"
cd "$R"

CORPUS="${CORPUS:?set CORPUS=tab|ontonotes|enron|cardiode}"
MAXSIZE="${MAXSIZE:-3}"
RULES="${RULES:-union vote}"
CRITERION="${CRITERION:-product}"
FLOOR="${FLOOR:-0.5}"
STEPS="${STEPS:-sweep choose build stability leakage}"
PY="$R/.venv/bin/python"
export PYTHONPATH=src

say() { echo; echo "=== $* === $(date -Is)"; }

say "corpus ${CORPUS}  host $(hostname)  steps: ${STEPS}"

if [[ " ${STEPS} " == *" sweep "* ]]; then
    say "1. detection sweep, sizes 1..${MAXSIZE}"
    "$PY" experiments/score_detection.py --corpus "$CORPUS" --max-size "$MAXSIZE"
fi

CHOSEN=""
if [[ " ${STEPS} " == *" choose "* ]]; then
    say "2. choosing the operating point (criterion ${CRITERION}, recall floor ${FLOOR})"
    "$PY" experiments/best_ensemble.py --corpus "$CORPUS" --size 3 \
          --criterion "$CRITERION" --constraint "$FLOOR" | tee "results/detection/${CORPUS}.choice.txt"
    CHOSEN=$("$PY" experiments/best_ensemble.py --corpus "$CORPUS" --size 3 \
             --criterion "$CRITERION" --constraint "$FLOOR" --names | tr '\n' ' ')
    echo "chosen: ${CHOSEN}"
fi

if [[ " ${STEPS} " == *" build "* ]]; then
    for RULE in $RULES; do
        say "3. conditions B and C — whole pool, rule ${RULE}"
        "$PY" experiments/build_BC.py --corpus "$CORPUS" --rule "$RULE"
        if [[ -n "$CHOSEN" ]]; then
            say "3. conditions B and C — chosen three, rule ${RULE}"
            "$PY" experiments/build_BC.py --corpus "$CORPUS" --rule "$RULE" --detectors $CHOSEN
        fi
    done
fi

if [[ " ${STEPS} " == *" stability "* ]]; then
    for RULE in $RULES; do
        say "4. stability, rule ${RULE}"
        "$PY" experiments/run_stability.py --corpus "$CORPUS" --rule "$RULE"
    done
fi

if [[ " ${STEPS} " == *" leakage "* ]]; then
    say "5. leakage sweep over every span source"
    "$PY" experiments/sweep_leakage.py --corpus "$CORPUS" --max-size "$MAXSIZE" ${SOURCES:+--sources "$SOURCES"}
fi

say "done"
