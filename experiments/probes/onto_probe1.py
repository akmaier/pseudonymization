"""Measure what the OntoNotes adapter supplies today."""
import sys, re, json, collections
sys.path.insert(0, "src")
from pseudonymkit.adapters import ontonotes as ON

ROOT = "data/ontonotes"
report = {}
corpus = ON.load(ROOT, report=report)
docs = list(corpus.documents)
print("documents:", len(docs))
for lang, r in report.items():
    print(f"  {lang}: {r}")

# per language / genre
by_lg = collections.Counter()
mentions_by_lg = collections.Counter()
chained_by_lg = collections.Counter()
type_counts = collections.Counter()
type_by_lang = collections.defaultdict(collections.Counter)
chain_by_type = collections.Counter()
tot_by_type = collections.Counter()
chars_by_lg = collections.Counter()
docs_with_coref = collections.Counter()
empty_mentions = 0
for d in docs:
    key = (d.language, d.domain)
    by_lg[key] += 1
    chars_by_lg[key] += len(d.text)
    mentions_by_lg[key] += len(d.mentions)
    if d.metadata.get("has_coref"):
        docs_with_coref[key] += 1
    if not d.mentions:
        empty_mentions += 1
    for m in d.mentions:
        type_counts[m.type] += 1
        type_by_lang[d.language][m.type] += 1
        tot_by_type[m.type] += 1
        if m.gold_entity_id is not None:
            chained_by_lg[key] += 1
            chain_by_type[m.type] += 1

print("\n=== documents / mentions / coref by (lang, genre) ===")
print(f"{'lang':5} {'genre':24} {'docs':>6} {'chars':>12} {'ments':>8} {'w/coref':>8} {'chained_ments':>14}")
for key in sorted(by_lg):
    l, g = key
    print(f"{l:5} {g:24} {by_lg[key]:6d} {chars_by_lg[key]:12d} {mentions_by_lg[key]:8d} {docs_with_coref[key]:8d} {chained_by_lg[key]:14d}")

print("\n=== harmonised type counts (all) ===")
for t, c in type_counts.most_common():
    print(f"  {t:14} {c:8d}   with chain id: {chain_by_type[t]:7d}  ({100*chain_by_type[t]/c:5.1f}%)")

print("\n=== type by language ===")
for lang in sorted(type_by_lang):
    print(f"  {lang}: {dict(type_by_lang[lang].most_common())}")

print("\ndocuments with zero mentions:", empty_mentions)
print("total mentions:", sum(type_counts.values()))
print("total chars:", sum(chars_by_lg.values()))

# distinct PERSON surfaces
persons = collections.Counter()
for d in docs:
    for m in d.mentions:
        if m.type == "PERSON":
            persons[m.surface] += 1
print("\ndistinct PERSON surfaces:", len(persons), "tokens:", sum(persons.values()))
print("top 15:", persons.most_common(15))
