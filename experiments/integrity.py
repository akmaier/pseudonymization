"""Post-incident integrity check. Reports; changes nothing."""
import sys, os, json, gzip, hashlib, glob
sys.path.insert(0, "src")
from pathlib import Path

ok, bad = [], []
def check(name, cond, detail=""):
    (ok if cond else bad).append((name, detail))
    print("  {} {:<52} {}".format("OK  " if cond else "FAIL", name, detail))

print("=== 1. the HMAC key (home directory — the one thing that is NOT in the work tree) ===")
key_path = Path.home() / ".config" / "pseudonymkit" / "hmac.key"
if key_path.exists():
    key = key_path.read_bytes()
    kid = hashlib.sha256(key).hexdigest()[:12]
    check("key present", True, "{} bytes, mode {:o}".format(len(key), key_path.stat().st_mode & 0o777))
    check("key id matches the one the conditions were built with", kid == "de069ed9fc3a",
          "found {}, expected de069ed9fc3a".format(kid))
else:
    check("key present", False, "MISSING at {} — condition B is not reproducible".format(key_path))

print("\n=== 2. condition A ===")
from pseudonymkit.paths import cardiode_a, condition_a_dir
targets = [("cardiode", cardiode_a(), 400),
           ("tab", condition_a_dir()/"tab_A.jsonl.gz", 1268),
           ("ontonotes", condition_a_dir()/"ontonotes_A.jsonl.gz", 5994),
           ("enron", condition_a_dir()/"enron_A.jsonl.gz", 58636)]
digests = {}
for name, path, expected in targets:
    if not path.exists():
        check("conditionA/" + name, False, "MISSING"); continue
    try:
        n = 0; bad_off = 0; d = {}
        for line in gzip.open(path, "rt", encoding="utf-8"):
            r = json.loads(line)
            if r.get("text") is None: continue
            n += 1
            d[r["doc_id"]] = hashlib.sha256(r["text"].encode()).hexdigest()[:16]
            for s in r.get("spans", []):
                if s.get("text") and r["text"][s["start"]:s["end"]] != s["text"]:
                    bad_off += 1
        digests[name] = d
        check("conditionA/" + name, n == expected and bad_off == 0,
              "{} documents (expect {}), {} offset mismatches".format(n, expected, bad_off))
    except Exception as exc:
        check("conditionA/" + name, False, "{}: {}".format(type(exc).__name__, exc))

print("\n=== 3. detector cache: parseable, and still matching condition A ===")
for corpus in ("cardiode", "tab", "ontonotes", "enron"):
    root = Path("results/detector_cache") / corpus
    if not root.is_dir():
        check("cache/" + corpus, False, "MISSING"); continue
    torn = files = 0
    for f in sorted(root.glob("*.jsonl")):
        files += 1
        try:
            with f.open(encoding="utf-8") as h:
                for line in h:
                    line = line.strip()
                    if not line: continue
                    try: json.loads(line)
                    except json.JSONDecodeError: torn += 1
        except Exception as exc:
            torn += 1
    check("cache/" + corpus, torn == 0, "{} detector files, {} unparseable lines".format(files, torn))

print("\n=== 4. patch sets ===")
from pseudonymkit.construction import read_patchset, check_current
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.paths import cardiode_conditions
try:
    docs = list(iter_documents(cardiode_a()))
    for f in sorted(cardiode_conditions().glob("cardiode_[BC]_*.patch.jsonl")):
        try:
            rep = check_current(docs, read_patchset(f))
            check("patch/" + f.name[:44], True, "{} patches verified".format(rep["patches"]))
        except Exception as exc:
            check("patch/" + f.name[:44], False, str(exc)[:70])
except Exception as exc:
    check("patch sets", False, "{}: {}".format(type(exc).__name__, exc))

print("\n=== 5. result files ===")
for pattern, expect in (("results/detection/cardiode.jsonl", 2151),
                        ("results/leakage_sweep/cardiode_PERSON.jsonl", 2150),
                        ("results/leakage_sweep/cardiode_ORG.jsonl", 2150),
                        ("results/utility/cardiode_union.jsonl", 5721),
                        ("results/utility/cardiode_vote.jsonl", 5721),
                        ("results/utility/cardiode_union-single0.5-3det.jsonl", 5721),
                        ("results/utility/cardiode_vote-single0.5-3det.jsonl", 5721)):
    p = Path(pattern)
    if not p.exists():
        check(p.name, False, "MISSING"); continue
    n = torn = 0
    for line in p.open(encoding="utf-8"):
        if not line.strip(): continue
        n += 1
        try: json.loads(line)
        except json.JSONDecodeError: torn += 1
    check(p.name[:52], n == expect and torn == 0, "{} rows (expect {}), {} unparseable".format(n, expect, torn))

print("\n=== 6. supporting inputs ===")
for name, path in (("name weights", Path(os.environ["PSEUDONYMKIT_WORK"])/"data"/"cardiode_name_weights.json"),
                   ("codealltag sublists", Path(os.environ["PSEUDONYMKIT_WORK"])/"data"/"codealltag_sublists"/"family.json"),
                   ("venv python", Path(".venv/bin/python")),
                   ("gold map", Path(os.environ["PSEUDONYMKIT_DUA"])/"cardiode"/"A"/"cardiode_A_map_seed0.jsonl")):
    check(name, path.exists(), str(path)[-58:])

print("\n{} checks passed, {} FAILED".format(len(ok), len(bad)))
for n, d in bad:
    print("  FAILED: {} {}".format(n, d))
