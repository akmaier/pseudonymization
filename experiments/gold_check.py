"""Is the ground truth intact and complete after the rebuild?"""
import sys, json, collections
sys.path.insert(0, "src")
from pseudonymkit.serialisation import iter_documents
from pseudonymkit.paths import cardiode_a, dua_dir

docs = list(iter_documents(cardiode_a()))
print(f"documents {len(docs)}")

# 1. every mention's offsets must address its own text
bad = sum(1 for d in docs for m in d.mentions if d.text[m.span.start:m.span.end] != m.span.text)
kinds = collections.Counter(m.type for d in docs for m in d.mentions)
print(f"\n1. detection gold")
print(f"   mentions {sum(kinds.values())}, offset mismatches {bad}")
print(f"   by type: {dict(kinds.most_common())}")

# 2. the run -> entity map, which §12.1 calls the detection gold
rows = [json.loads(l) for l in open(dua_dir()/"cardiode"/"A"/"cardiode_A_map_seed0.jsonl", encoding="utf-8")]
by_doc = {d.doc_id: d for d in docs}
missing = sum(1 for r in rows if "entity_id" not in r or not r.get("surface"))
print(f"\n2. run -> entity map")
print(f"   rows {len(rows)}, fields {sorted(rows[0])}")
print(f"   rows lacking an entity or a surface: {missing}")
roles = collections.Counter(r["role"] for r in rows)
print(f"   roles: {dict(roles.most_common())}")

# 3. identity: what evaluation consumes
ent = collections.defaultdict(set)
for d in docs:
    for m in d.mentions:
        if m.gold_entity_id:
            ent[m.gold_entity_id].add(d.doc_id)
multi = [k for k, v in ent.items() if len(v) > 1]
print(f"\n3. identity")
print(f"   entities with a chain id {len(ent)}, of which cross-document {len(multi)}")
print(f"   documents with co-reference {sum(1 for d in docs if any(m.gold_entity_id for m in d.mentions))}")

# 4. the utility gold layers must have moved with the text
lay = collections.Counter()
for d in docs:
    for k, v in (d.task or {}).items():
        if isinstance(v, (list, tuple)):
            lay[k] += len(v)
print(f"\n4. utility gold")
print(f"   layers: {dict(lay)}")
off = 0
for d in docs:
    for span in (d.task or {}).get("medications", ()):
        if getattr(span, "text", None) and d.text[span.start:span.end] != span.text:
            off += 1
print(f"   medication spans whose offsets disagree with the text: {off}")

# 5. the manifest
man = json.load(open(dua_dir()/"cardiode"/"A"/"conditionA_manifest.json", encoding="utf-8"))
entry = man.get("cardiode", man)
pop = (entry.get("population") or {}) if isinstance(entry, dict) else {}
print(f"\n5. manifest records the construction: {bool(pop)}")
if pop:
    print(f"   spec {pop.get('spec')}")
    print(f"   weights source recorded: {str(pop.get('family_names', {}).get('source'))[:80]}…")
