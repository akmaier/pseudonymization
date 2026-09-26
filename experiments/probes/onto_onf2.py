"""Robust .onf parser + detokenised-text alignment. Second cut."""
from __future__ import annotations
import re, unicodedata

SEC = re.compile(r"^(Plain sentence|Treebanked sentence|Speaker information|Tree|Leaves):\s*$")
RULE = re.compile(r"^-{3,}\s*$")
BAR = re.compile(r"^-{60,}\s*$")

PTB = {"-LRB-": "(", "-RRB-": ")", "-LCB-": "{", "-RCB-": "}",
       "-LSB-": "[", "-RSB-": "]", "``": '"', "''": '"'}
TRACE = re.compile(r"^(\*.*\*(-\d+)?|\*(-\d+)?|0)$")

def strip_marks(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))

def norm_token(t: str, lang: str) -> str:
    if t in PTB:
        return PTB[t]
    t = t.replace("\\/", "/").replace("\\*", "*")
    if lang == "arabic":
        t = strip_marks(t)
        t = (t.replace("{", "ا").replace("<", "إ").replace(">", "أ")
               .replace("ٱ", "ا").replace("|", "آ").replace("_", ""))
        t = t.replace("-", "")
    return t

def parse_onf(text: str):
    lines = text.split("\n")
    blocks, cur = [], []
    for ln in lines:
        if BAR.match(ln):
            if cur: blocks.append(cur)
            cur = []
        else:
            cur.append(ln)
    if cur: blocks.append(cur)
    for blk in blocks:
        sections, name, buf = {}, None, []
        for ln in blk:
            m = SEC.match(ln)
            if m:
                if name: sections[name] = buf
                name, buf = m.group(1), []
                continue
            if RULE.match(ln) and not buf: continue
            if name: buf.append(ln)
        if name: sections[name] = buf
        if "Plain sentence" not in sections or "Treebanked sentence" not in sections:
            continue
        plain = " ".join(l.strip() for l in sections["Plain sentence"] if l.strip())
        tokens = " ".join(l.strip() for l in sections["Treebanked sentence"] if l.strip()).split()
        speaker = None
        for l in sections.get("Speaker information", []):
            if l.strip().startswith("name:"):
                speaker = l.split(":", 1)[1].strip()
        names, corefs = [], []
        for l in sections.get("Leaves", []):
            s = l.strip()
            m = re.match(r"^name:\s+(\S+)\s+(\d+)-(\d+)\s+(.*)$", s)
            if m:
                names.append((m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)))
                continue
            m = re.match(r"^coref:\s+(\S+)\s+(\S+)\s+(\d+)-(\d+)\s+(.*)$", s)
            if m:
                corefs.append((m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), m.group(5)))
        yield {"plain": plain, "tokens": tokens, "speaker": speaker,
               "names": names, "corefs": corefs}

def align(tokens, plain, lang):
    """Token index -> (start,end) into `plain`, or None.

    Greedy with bounded resync: if a token does not match at the cursor, look ahead a little
    (the plain sentence sometimes renders a token differently, e.g. quotes), and if still not
    found, leave it unaligned and carry on without moving the cursor.
    """
    spans = [None] * len(tokens)
    pos = 0
    LOOK = 12
    for k, t in enumerate(tokens):
        tn = norm_token(t, lang)
        if not tn:
            continue
        while pos < len(plain) and plain[pos].isspace():
            pos += 1
        if plain.startswith(tn, pos):
            spans[k] = (pos, pos + len(tn)); pos += len(tn); continue
        j = plain.find(tn, pos, pos + len(tn) + LOOK)
        if j >= 0:
            spans[k] = (j, j + len(tn)); pos = j + len(tn); continue
        # case-insensitive last resort (plain sometimes recases sentence-initially)
        j = plain.lower().find(tn.lower(), pos, pos + len(tn) + LOOK)
        if j >= 0:
            spans[k] = (j, j + len(tn)); pos = j + len(tn); continue
    leftover = plain[pos:].strip()
    unaligned = [k for k, sp in enumerate(spans) if sp is None and not TRACE.match(tokens[k])]
    return spans, unaligned, leftover

def span_of(spans, i, j):
    sub = [spans[k] for k in range(i, j + 1) if k < len(spans) and spans[k]]
    if not sub:
        return None
    return (sub[0][0], sub[-1][1])
