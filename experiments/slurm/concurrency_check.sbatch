#!/bin/bash
# Does --concurrency change the numbers? Same 24 documents, once sequentially and once eight at a
# time. It must not: the calls are independent and the writer stays on the main thread. Run in an
# allocation because ner_agreement loads Presidio, which the head node SIGKILLs.
#SBATCH --job-name=concurrency_check
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --output=logs/concurrency_check_%j.out
#SBATCH --error=logs/concurrency_check_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
mkdir -p logs
export PYTHONPATH=src
A=$SECONDS
.venv/bin/python experiments/run_utility.py --corpus tab --rule vote --conditions A \
    --tasks ner_agreement --limit 24 --concurrency 1 --out /tmp/u_fast --restart >/dev/null
echo "one instrument, sequential   $((SECONDS-A)) s"
B=$SECONDS
.venv/bin/python experiments/run_utility.py --corpus tab --rule vote --conditions A \
    --tasks ner_agreement --limit 24 --concurrency 4 --out /tmp/u_con --restart >/dev/null
echo "one instrument, concurrent 4 $((SECONDS-B)) s"
.venv/bin/python - <<'PY'
import json
def load(p):
    return {(r["doc_id"], r["task"]): r.get("score")
            for r in map(json.loads, open(p)) if "score" in r}
a = load("/tmp/u_fast/tab_vote.jsonl"); b = load("/tmp/u_con/tab_vote.jsonl")
print("rows", len(a), len(b), "| identical key set:", set(a) == set(b))
print("score differences:", sum(1 for k in a if abs((a[k] or 0) - (b.get(k) or 0)) > 1e-12))
PY
