"""How much of each corpus condition B cannot currently render.

Counts gold mentions by harmonised kind, and — more to the point — how many DOCUMENTS contain at
least one mention of a kind with no surrogate pool, since one such mention blocks the whole document.
"""
import sys, collections
sys.path.insert(0, "src")
from pathlib import Path
from pseudonymkit.paths import cardiode_a_optional
from pseudonymkit.serialisation import iter_documents

RENDERABLE = {"PERSON", "LOC", "ORG"}          # the only kinds with inventory pools today
CONDITION_A = Path("data/conditionA")
CORPORA = [
    ("cardiode",  cardiode_a_optional()),
    ("tab",       CONDITION_A / "tab_A.jsonl.gz"),
    ("ontonotes", CONDITION_A / "ontonotes_A.jsonl.gz"),
    ("enron",     CONDITION_A / "enron_A.jsonl.gz"),
]

print(f"{'corpus':<11}{'docs':>7}{'mentions':>10}   per-kind mention counts")
grand = collections.Counter()
for name, path in CORPORA:
    if path is None or not path.exists():
        print(f"{name:<11} no condition A at {path}"); continue
    kinds = collections.Counter()
    docs = blocked = total_mentions = 0
    for d in iter_documents(path):
        docs += 1
        seen = {m.type for m in d.mentions}
        for m in d.mentions:
            kinds[m.type] += 1
        total_mentions += len(d.mentions)
        if seen - RENDERABLE:
            blocked += 1
    grand.update(kinds)
    ordered = ", ".join(f"{k} {v}" for k, v in kinds.most_common())
    print(f"\n{name:<11}{docs:>7}{total_mentions:>10}   {ordered}")
    unrend = sum(v for k, v in kinds.items() if k not in RENDERABLE)
    print(f"{'':<11}{'':>7}{'':>10}   unrenderable mentions: {unrend} "
          f"({100*unrend/max(total_mentions,1):.1f}%)")
    print(f"{'':<11}{'':>7}{'':>10}   DOCUMENTS BLOCKED: {blocked}/{docs} "
          f"({100*blocked/max(docs,1):.1f}%)")
print("\n=== all four corpora ===")
tot = sum(grand.values())
for k, v in grand.most_common():
    mark = "" if k in RENDERABLE else "   <-- no renderer"
    print(f"  {k:<14}{v:>9}  {100*v/tot:5.1f}%{mark}")
