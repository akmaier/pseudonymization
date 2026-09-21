#!/bin/bash
# Conditions B and C at the four operating points, then utility on each.
#
# The existing patch sets answer "what does the combination rule do" (§7's D'/D"). These answer
# "what does the ensemble we would deploy cost in utility", which is the question the operating
# points were defined to pose and which nothing currently measures.
#SBATCH --job-name=oppoints
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --output=logs/oppoints_%x_%j.out
#SBATCH --error=logs/oppoints_%x_%j.err
set -euo pipefail
cd "${PSEUDONYMKIT_WORK:-$PWD}"
export PYTHONPATH=src
CORPUS="${CORPUS:?set CORPUS}"

echo "=== building conditions at the operating points === $(date -Is)"
.venv/bin/python experiments/build_operating_points.py --corpus "$CORPUS"

echo; echo "=== utility at each === $(date -Is)"
# The tags build_BC writes are rule-single0.5-Ndet-<fingerprint>; the fingerprint distinguishes
# ensembles of the same size, so each point has its own patch set and its own utility file.
for TAG in $(.venv/bin/python - <<'PY'
import json, glob, os, sys
sys.path.insert(0, "src")
from pseudonymkit.paths import cardiode_conditions, work_dir
corpus = os.environ["CORPUS"]
root = cardiode_conditions() if corpus == "cardiode" else work_dir() / "results/conditions"
pts = json.load(open(work_dir() / f"results/detection/{corpus}_operating_points.json"))["points"]
import hashlib
seen = set()
for name, p in pts.items():
    fp = hashlib.sha256("\x1f".join(sorted(p["ensemble"])).encode()).hexdigest()[:6]
    rule = "union" if p["rule"] == "single" else p["rule"]
    tag = f"{rule}-single0.5-{len(p['ensemble'])}det-{fp}"
    if tag not in seen and (root / f"{corpus}_B_{tag}.patch.jsonl").exists():
        seen.add(tag); print(tag)
PY
); do
    echo; echo "--- utility on $TAG --- $(date -Is)"
    .venv/bin/python experiments/run_utility.py --corpus "$CORPUS" --rule "$TAG"
done
echo; echo "=== done === $(date -Is)"
