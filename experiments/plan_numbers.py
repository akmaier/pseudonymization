import sys, json, collections
sys.path.insert(0, "src")
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.paths import cardiode_a, dua_dir

rows = [json.loads(l) for l in open(dua_dir()/"cardiode"/"A"/"cardiode_A_map_seed0.jsonl", encoding="utf-8")]
roles = collections.Counter(r["role"] for r in rows)
types = collections.Counter(r["type"] for r in rows)
print(f"map rows (runs filled)     {len(rows)}")
print(f"PER runs                   {types['PER']}")
print(f"ORG runs                   {types['ORG']}")
print(f"PER roles                  {dict((k,v) for k,v in roles.most_common() if k in ('patient','patient_body','signature','referring'))}")

per_letter_entities, patient_mentions, patient_surfaces = [], [], 0
docs = list(iter_documents(cardiode_a()))
for d in docs:
    persons = [m for m in d.mentions if m.type == "PERSON"]
    per_letter_entities.append(len({m.gold_entity_id for m in persons}))
    pat = [m for m in persons if m.gold_entity_id == f"{d.doc_id}:patient"]
    patient_mentions.append(len(pat))
    if len({m.span.text for m in pat}) > 1:
        patient_surfaces += 1
n = len(docs)
print(f"person entities per letter {sum(per_letter_entities)/n:.2f}  (total {sum(per_letter_entities)})")
print(f"patient mentions per letter{sum(patient_mentions)/n:.3f}")
print(f"patient >1 surface form    {patient_surfaces} of {n}")
kinds = collections.Counter(m.type for d in docs for m in d.mentions)
print(f"gold mentions              {sum(kinds.values())}  {dict(kinds.most_common())}")
lay = collections.Counter()
for d in docs:
    for k, v in (d.task or {}).items():
        if isinstance(v, (list, tuple)): lay[k] += len(v)
print(f"annotation layers          {dict(lay)}")
