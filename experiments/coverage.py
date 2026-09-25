"""Per (corpus, detector): current, stale, missing — against condition A as it stands now."""
import sys
sys.path.insert(0, "src")
from pathlib import Path
from pseudonymkit.detectors.cache import DetectorCache, text_digest
from pseudonymkit.paths import cardiode_a_optional
from pseudonymkit.serialisation import iter_documents

CONDITION_A = Path("data/conditionA")
CORPORA = [
    ("cardiode", cardiode_a_optional()),
    ("tab", CONDITION_A / "tab_A.jsonl.gz"),
    ("ontonotes", CONDITION_A / "ontonotes_A.jsonl.gz"),
    ("enron", CONDITION_A / "enron_A.jsonl.gz"),
]
for name, path in CORPORA:
    if path is None or not path.exists():
        print(f"{name}: no condition A at {path}"); continue
    index = {d.doc_id: text_digest(d.text) for d in iter_documents(path)}
    cache = DetectorCache("results/detector_cache", name)
    print(f"\n=== {name}  ({len(index)} documents) ===")
    rows = []
    for f in sorted(cache.root.glob("*.jsonl")):
        det = f.stem.replace("__", "/")
        rec = cache.digests(det)
        cur = sum(1 for k, v in index.items() if rec.get(k) == v)
        stale = sum(1 for k in index if k in rec and rec[k] != index[k])
        rows.append((cur, det, stale, len(index) - cur - stale))
    for cur, det, stale, missing in sorted(rows, reverse=True):
        flag = "  <-- complete" if missing == 0 and stale == 0 else ""
        print(f"  {det:52s} current {cur:6d}  stale {stale:4d}  missing {missing:6d}{flag}")
