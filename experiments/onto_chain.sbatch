#!/bin/bash
# Wait for the OntoNotes re-detections to finish, then submit the downstream chain.
#
# **Polls the cache, not the processes.** The first version of this polled `pgrep` for the gateway
# runs, which only works on the node they happen to be on — and it was a login-node process itself,
# so the head node reaped it within the hour (§6: that is how the first CARDIO:DE sweep died at
# 1,600 of 2,151 sources with no traceback). Record counts live on the shared filesystem and are
# visible from any node, so this belongs in Slurm where nothing reaps it.
#
# It verifies rather than trusts: a detection process can exit because it was killed, and a sweep
# over a half-filled cache would score ensembles on documents some members never saw.
#
#SBATCH --job-name=onto_watch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err

set -u
R="${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p "$R/logs"
cd "$R"
. config/env.sh

TARGET=5994
DEADLINE=$(( $(date +%s) + 11*3600 ))

count_incomplete() {
    .venv/bin/python - <<'PY'
import pathlib
root = pathlib.Path("results/detector_cache/ontonotes")
bad = []
for p in sorted(root.glob("llm:*.jsonl")):
    n = sum(1 for line in p.open(errors="replace") if line.strip())
    if n < 5994:
        bad.append(f"{p.name.split(':')[-1][:28]}={n}")
print(";".join(bad))
PY
}

echo "watching the OntoNotes cache, target ${TARGET} records per gateway model"
while :; do
    MISSING=$(count_incomplete)
    if [ -z "$MISSING" ]; then
        echo "$(date -Is)  cache complete for every gateway model"
        break
    fi
    if [ "$(date +%s)" -ge "$DEADLINE" ]; then
        echo "$(date -Is)  GIVING UP — still incomplete: $MISSING"
        echo "not submitting; finish detection and submit the chain by hand (§1: report, do not substitute)"
        exit 1
    fi
    echo "$(date -Is)  still missing: $MISSING"
    sleep 300
done

echo "submitting the OntoNotes chain"
CORPUS=ontonotes STEPS="sweep choose build stability" \
    sbatch --job-name=onto_chain experiments/evaluate_corpus.sbatch
