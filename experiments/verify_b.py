"""Does condition B now build on a real corpus, for every document, with nothing left unrendered?"""
import sys, collections, secrets
sys.path.insert(0, "src"); sys.path.insert(0, "experiments")
from pathlib import Path
from pseudonymkit.conditions import build
from pseudonymkit.serialisation import iter_documents
from build_BC import inventory_for

docs = list(iter_documents(Path("data/conditionA/tab_A.jsonl.gz")))[:200]
langs = {d.language for d in docs}
inventory, notes = inventory_for(langs, documents=docs)
print("languages:", sorted(langs))
print("DEMOGRAPHIC pool:", notes.get("DEMOGRAPHIC", "")[:220])
print()

engine = build("B", inventory=inventory, key=secrets.token_bytes(32))
ok = failed = 0
errors = collections.Counter()
by_kind = collections.Counter()
changed = collections.Counter()
for d in docs:
    try:
        result = engine.pseudonymise(d)
    except Exception as exc:
        failed += 1
        errors[f"{type(exc).__name__}: {str(exc)[:90]}"] += 1
        continue
    ok += 1
    for a in result.assignments:
        by_kind[a.entity_type] += 1
        if a.surface != a.entity_key:
            changed[a.entity_type] += 0      # entity_key is normalised; compare below instead

print(f"documents rendered : {ok}/{len(docs)}")
print(f"documents failed   : {failed}")
for e, n in errors.most_common(5):
    print(f"   {n:5d}  {e}")
print("\nassignments by type:")
for k, v in by_kind.most_common():
    print(f"   {k:<14}{v:>7}")

# spot-check the three behaviours that matter, on real spans
d = docs[0]
res = engine.pseudonymise(d)
seen = {}
for a in res.assignments:
    seen.setdefault(a.entity_type, []).append((a.entity_key, a.surface))
print("\none example per type (original-key -> surrogate):")
for k in ("PERSON", "CODE", "DATETIME", "QUANTITY", "DEMOGRAPHIC", "ORG", "LOC", "MISC"):
    if k in seen:
        key, surf = seen[k][0]
        print(f"   {k:<13} {key[:34]!r:38} -> {surf[:34]!r}")
