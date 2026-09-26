"""Tokenisation artefacts, identifier density per genre, coref alignment quality."""
import sys, re, collections, unicodedata
sys.path.insert(0, "src")
from pseudonymkit.adapters import ontonotes as ON

ROOT = "data/ontonotes"
corpus = ON.load(ROOT)
docs = list(corpus.documents)

# ---------- 1. Penn Treebank tokenisation artefacts ----------
PATS = {
    "-LRB-/-RRB-": re.compile(r"-[LR][RCS]B-"),
    "backtick_quote": re.compile(r"``|''"),
    "split_clitic": re.compile(r"\s(n't|'s|'re|'ve|'ll|'m|'d)\b"),
    "space_before_punct": re.compile(r"\s[,.;:!?%]"),
    "space_hyphen_space": re.compile(r"\S \- \S"),
    "space_before_close_paren": re.compile(r"\s\)"),
    "dollar_space": re.compile(r"\$ \d"),
    "amp_": re.compile(r"&\w+;"),
    "asterisk_null": re.compile(r"\*(PRO|T|RNR|ICH|EXP|\?)?\*|\*-\d"),
    "trace_0": re.compile(r"(?<=\s)0(?=\s)"),
}
counts = collections.defaultdict(collections.Counter)
docs_hit = collections.defaultdict(collections.Counter)
for d in docs:
    key = (d.language, d.domain)
    for nm, p in PATS.items():
        n = len(p.findall(d.text))
        counts[key][nm] += n
        if n:
            docs_hit[key][nm] += 1

print("=== PTB tokenisation artefacts, occurrences (documents affected) ===")
names = list(PATS)
print(f"{'lang/genre':30}" + "".join(f"{n[:13]:>16}" for n in names))
for key in sorted(counts):
    row = f"{key[0]+'/'+key[1]:30}"
    for n in names:
        row += f"{counts[key][n]:>10}({docs_hit[key][n]:>4})"
    print(row)
tot = collections.Counter()
for k in counts:
    tot.update(counts[k])
print("TOTAL:", dict(tot))

ndocs = len(docs)
nhit = sum(1 for d in docs if PATS["split_clitic"].search(d.text) or PATS["backtick_quote"].search(d.text)
           or PATS["-LRB-/-RRB-"].search(d.text) or PATS["space_before_punct"].search(d.text))
print(f"documents showing at least one tokenisation artefact: {nhit}/{ndocs} ({100*nhit/ndocs:.1f}%)")

# ---------- 2. Chinese spacing ----------
zh = [d for d in docs if d.language == "zh"]
import statistics
def han_frac(t):
    h = sum(1 for c in t if "一" <= c <= "鿿")
    return h / max(len(t), 1)
sp = [t.count(" ")/max(len(t),1) for t in (d.text for d in zh)]
print(f"\nzh documents: {len(zh)}; mean space fraction of characters: {statistics.mean(sp):.3f}")
inter_han_space = sum(len(re.findall(r"[一-鿿] [一-鿿]", d.text)) for d in zh)
han_total = sum(sum(1 for c in d.text if "一" <= c <= "鿿") for d in zh)
print(f"zh: spaces between two Han characters: {inter_han_space}; Han chars total: {han_total}")

# ---------- 3. Arabic diacritics / clitic fragments ----------
ar = [d for d in docs if d.language == "ar"]
DIAC = re.compile(r"[ً-ْٰ]")
ndiac = sum(len(DIAC.findall(d.text)) for d in ar)
narab = sum(sum(1 for c in d.text if "ء" <= c <= "ي") for d in ar)
docs_with_diac = sum(1 for d in ar if DIAC.search(d.text))
print(f"\nar documents: {len(ar)}; diacritic marks: {ndiac} over {narab} Arabic letters ({100*ndiac/max(narab,1):.1f}%); docs with any diacritic: {docs_with_diac}")
# clitic fragmentation: tokens that are bare proclitics
tokens = collections.Counter()
for d in ar:
    tokens.update(d.text.split())
frag = sum(c for t, c in tokens.items() if t in {"w", "f", "l", "b", "k", "s", "+", "و", "ف", "ال", "ب", "ل", "ك"})
print("ar bare-clitic-looking tokens:", frag, "of", sum(tokens.values()))
print("ar top tokens:", tokens.most_common(15))

# ---------- 4. Identifier density per (lang, genre) ----------
IDPATS = {
    "email": re.compile(r"[\w.+-]+ ?@ ?[\w-]+ ?\. ?[\w.]+"),
    "phone": re.compile(r"\b(?:\+?\d{1,3}[ -]?)?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}\b"),
    "url": re.compile(r"(?:https?:// ?|www ?\. ?)\S+"),
    "street": re.compile(r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b"),
    "zip_us": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "iban_like": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,}\b"),
    "creditcard_like": re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),
}
idc = collections.defaultdict(collections.Counter)
for d in docs:
    key = (d.language, d.domain)
    for nm, p in IDPATS.items():
        idc[key][nm] += len(p.findall(d.text))
print("\n=== identifier-family density (regex over document text) ===")
names = list(IDPATS)
print(f"{'lang/genre':30}" + "".join(f"{n[:11]:>13}" for n in names))
for key in sorted(idc):
    print(f"{key[0]+'/'+key[1]:30}" + "".join(f"{idc[key][n]:>13}" for n in names))
t = collections.Counter()
for k in idc: t.update(idc[k])
print("TOTAL:", dict(t))

# ---------- 5. PERSON density per genre ----------
print("\n=== PERSON mentions per 1000 chars, distinct PERSON surfaces, per (lang, genre) ===")
per = collections.defaultdict(lambda: [0, 0, set(), 0])
for d in docs:
    key = (d.language, d.domain)
    per[key][0] += 1
    per[key][1] += len(d.text)
    for m in d.mentions:
        if m.type == "PERSON":
            per[key][2].add(m.surface)
            per[key][3] += 1
print(f"{'lang/genre':30}{'docs':>6}{'chars':>10}{'PERSON':>9}{'distinct':>10}{'per1k':>8}")
for key in sorted(per):
    n, ch, s, tk = per[key]
    print(f"{key[0]+'/'+key[1]:30}{n:6d}{ch:10d}{tk:9d}{len(s):10d}{1000*tk/ch:8.2f}")
