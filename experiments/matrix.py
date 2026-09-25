"""Which (type, language) pools does condition B actually need, and which exist?"""
import sys, collections
sys.path.insert(0, "src"); sys.path.insert(0, "experiments")
from pathlib import Path
from pseudonymkit.conditions import POOLED
from pseudonymkit.paths import cardiode_a_optional
from pseudonymkit.serialisation import iter_documents
from build_BC import inventory_for

CONDITION_A = Path("data/conditionA")
CORPORA = [
    ("cardiode",  cardiode_a_optional()),
    ("tab",       CONDITION_A / "tab_A.jsonl.gz"),
    ("ontonotes", CONDITION_A / "ontonotes_A.jsonl.gz"),
    ("enron",     CONDITION_A / "enron_A.jsonl.gz"),
]
need = collections.Counter()
for name, path in CORPORA:
    if path is None or not path.exists():
        continue
    for d in iter_documents(path):
        for m in d.mentions:
            if m.type in POOLED:
                need[(m.type, d.language)] += 1

langs = {lang for _, lang in need}
# Arabic needs the corpus itself; it supplies only (PERSON, ar) by construction, so report it apart
inventory, notes = inventory_for(langs - {"ar"}, documents=None)
ARABIC_HAS = {("PERSON", "ar")}
print("pools condition B needs, and whether one exists:\n")
print(f"{'type':<14}{'lang':<6}{'mentions':>10}  pool")
for (t, lang), n in sorted(need.items(), key=lambda kv: -kv[1]):
    if lang == "ar":
        size = "corpus-built" if (t, lang) in ARABIC_HAS else 0
    else:
        try:
            size = inventory.size(t, lang)
        except Exception:
            size = 0
    print(f"{t:<14}{lang:<6}{n:>10}  {size if size else 'MISSING':>8}")
