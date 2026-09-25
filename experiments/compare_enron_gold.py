"""Did the word-boundary fix change the text, and what did it do to the gold?

Three questions, in order of consequence:

1. Is the document text byte-identical? If yes, the 3.1 GB detector cache and both patch sets stay
   valid and nothing has to be re-detected. If no, the fix has scope far beyond the gold layer.
2. How many PERSON mentions did the old gold invent? Compared per document, body only.
3. Which entities lose the most, and do any real people lose mentions they should have kept?
"""
import sys
from collections import Counter

sys.path.insert(0, "src")
from pseudonymkit.serialisation import iter_documents

from pseudonymkit.detectors.cache import text_digest

OLD = "data/conditionA/enron_A.jsonl.gz"
NEW = "data/conditionA/enron_A_fixed.jsonl.gz"

old = {d.doc_id: d for d in iter_documents(OLD)}
new = {d.doc_id: d for d in iter_documents(NEW)}
print(f"documents: old {len(old):,}  new {len(new):,}  shared {len(set(old) & set(new)):,}")

same_text = sum(1 for k in old if k in new and text_digest(old[k].text) == text_digest(new[k].text))
print(f"text byte-identical on {same_text:,} of {len(old):,} documents "
      f"-> detector cache and patch sets {'STAY VALID' if same_text == len(old) else '*** INVALIDATED ***'}")

def body_person(doc):
    cut = doc.text.find("\n\n")
    if cut < 0:
        return []
    return [(m.span.start, m.span.end, doc.text[m.span.start:m.span.end].strip().lower(),
             m.gold_entity_id)
            for m in doc.mentions if m.type == "PERSON" and m.span.start >= cut + 2]

o_n = n_n = 0
dropped = Counter(); kept = Counter(); added = Counter()
o_ents, n_ents = set(), set()
for k in old:
    if k not in new:
        continue
    o = {(s, e) for s, e, _, _ in body_person(old[k])}
    ob = {(s, e): (surf, eid) for s, e, surf, eid in body_person(old[k])}
    nb = {(s, e): (surf, eid) for s, e, surf, eid in body_person(new[k])}
    o_n += len(ob); n_n += len(nb)
    for span, (surf, eid) in ob.items():
        o_ents.add(eid)
        if span in nb: kept[surf] += 1
        else: dropped[surf] += 1
    for span, (surf, eid) in nb.items():
        n_ents.add(eid)
        if span not in ob: added[surf] += 1

print(f"\nbody PERSON mentions: old {o_n:,} -> new {n_n:,}   "
      f"removed {o_n - n_n:,} ({(o_n - n_n) / max(o_n, 1):.1%})")
print(f"distinct body entities: old {len(o_ents):,} -> new {len(n_ents):,}")
print(f"\ntop surfaces REMOVED (these were the invented mentions):")
for s, c in dropped.most_common(16):
    print(f"   {c:>7,}  {s!r}")
print(f"\ntop surfaces KEPT:")
for s, c in kept.most_common(12):
    print(f"   {c:>7,}  {s!r}")
if added:
    print(f"\n*** surfaces ADDED (unexpected, investigate): {sum(added.values()):,}")
    for s, c in added.most_common(8):
        print(f"   {c:>7,}  {s!r}")
