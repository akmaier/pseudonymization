import sys, collections, json
sys.path.insert(0, "src")
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.paths import cardiode_a, dua_dir

docs = list(iter_documents(cardiode_a()))
print(f"documents {len(docs)}")

# 1. does any document-level grouping survive in the record?
keys = set()
for d in docs[:5]:
    keys |= set((d.metadata or {}).keys())
print(f"document metadata keys: {sorted(keys)}")
print(f"subject_id non-null: {sum(1 for d in docs if getattr(d,'subject_id',None))}")

# 2. do FILLED PERSON SURFACES recur across letters?
surf_docs = collections.defaultdict(set)
patient_surf = {}
for d in docs:
    for m in d.mentions:
        if m.type != "PERSON":
            continue
        surf_docs[m.span.text].add(d.doc_id)
        if m.gold_entity_id == f"{d.doc_id}:patient":
            patient_surf.setdefault(d.doc_id, m.span.text)
multi = {s: v for s, v in surf_docs.items() if len(v) > 1}
print(f"\ndistinct PERSON surfaces      {len(surf_docs)}")
print(f"  surfaces in >1 document     {len(multi)}")
print(f"  documents touched by those  {len(set().union(*multi.values())) if multi else 0}")

pat = collections.Counter(patient_surf.values())
print(f"\npatient surfaces: {len(pat)} distinct over {len(patient_surf)} letters")
print(f"  patient names shared by >1 letter: {sum(1 for v in pat.values() if v > 1)}")

# 3. surname-only overlap (a family name is the linkable token)
last = collections.defaultdict(set)
for d in docs:
    for m in d.mentions:
        if m.type == "PERSON":
            last[m.span.text.split()[-1]].add(d.doc_id)
lm = {k: v for k, v in last.items() if len(v) > 1}
print(f"\ndistinct surnames             {len(last)}")
print(f"  surnames in >1 document     {len(lm)}")

# 4. what the ORG/LOC layers do - hospitals are drawn from a city list, so they SHOULD recur
for t in ("ORG", "LOC"):
    s = collections.defaultdict(set)
    for d in docs:
        for m in d.mentions:
            if m.type == t:
                s[m.span.text].add(d.doc_id)
    rec = {k: v for k, v in s.items() if len(v) > 1}
    print(f"{t}: {len(s)} distinct, {len(rec)} recur across documents, "
          f"max fan-out {max((len(v) for v in s.values()), default=0)}")
