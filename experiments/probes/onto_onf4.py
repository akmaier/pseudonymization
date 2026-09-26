"""ONF parser + alignment, fourth cut.

Measured correction over the third cut: the ONF *Plain sentence* keeps ``````, ``''``,
``-LRB-`` and ``-RRB-`` verbatim -- it does not restore real quotes or brackets -- so the
aligner must match those tokens literally and the *text* must be repaired afterwards.
"""
from __future__ import annotations
import re

SEC = re.compile(r"^(Plain sentence|Treebanked sentence|Speaker information|Tree|Leaves):\s*$")
RULE = re.compile(r"^-{3,}\s*$")
BAR = re.compile(r"^-{60,}\s*$")
TRACE = re.compile(r"^(\*.*\*(-\d+)?|\*(-\d+)?|0)$")
DROP = re.compile(r"^(%pw|%uh|%ah|%um|%hm|%bcack)$")

AR_MARKS = re.compile("[ً-ْٰـٓ-ٟۖ-ۭ]")
AR_ALEF = str.maketrans({"إ": "ا", "أ": "ا", "آ": "ا",
                         "ٱ": "ا", "{": "ا", "<": "ا", ">": "ا",
                         "|": "ا", "ى": "ي", "ة": "ه",
                         "`": None, "_": None, "-": None})

def ar_key(s: str) -> str:
    return AR_MARKS.sub("", s).translate(AR_ALEF)

def norm_token(t: str, lang: str) -> str:
    if DROP.match(t):
        return ""
    t = t.replace("\\/", "/").replace("\\*", "*")
    return ar_key(t) if lang == "arabic" else t

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
            s = l.strip().lstrip("!").strip()
            m = re.match(r"^name:\s+(\S+)\s+(\d+)-(\d+)\s*(.*)$", s)
            if m:
                names.append((m.group(1), int(m.group(2)), int(m.group(3)), m.group(4))); continue
            m = re.match(r"^coref:\s+(\S+)\s+(\S+)\s+(\d+)-(\d+)\s*(.*)$", s)
            if m:
                corefs.append((m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), m.group(5)))
        yield {"plain": plain, "tokens": tokens, "speaker": speaker,
               "names": names, "corefs": corefs}

def align(tokens, plain, lang):
    """Token index -> (start, end) into the *real* plain string."""
    if lang == "arabic":
        # build a key string of the same length as plain, char by char, so offsets survive
        key_chars, idx = [], []
        for i, c in enumerate(plain):
            k = ar_key(c)
            if k:
                key_chars.append(k); idx.append(i)
        hay = "".join(key_chars)
        pos_map = idx + [len(plain)]
    else:
        hay = plain
        pos_map = list(range(len(plain) + 1))
    spans = [None] * len(tokens)
    pos = 0
    LOOK = 12
    for k, t in enumerate(tokens):
        tn = norm_token(t, lang)
        if not tn:
            continue
        while pos < len(hay) and hay[pos].isspace():
            pos += 1
        j = -1
        if hay.startswith(tn, pos):
            j = pos
        else:
            j = hay.find(tn, pos, pos + len(tn) + LOOK)
            if j < 0:
                j = hay.lower().find(tn.lower(), pos, pos + len(tn) + LOOK)
        if j >= 0:
            spans[k] = (pos_map[j], pos_map[j + len(tn) - 1] + 1)
            pos = j + len(tn)
    leftover = hay[pos:].strip()
    unaligned = [k for k, sp in enumerate(spans)
                 if sp is None and not TRACE.match(tokens[k]) and norm_token(tokens[k], lang)]
    return spans, unaligned, leftover

def span_of(spans, i, j):
    sub = [spans[k] for k in range(i, j + 1) if k < len(spans) and spans[k]]
    return (sub[0][0], sub[-1][1]) if sub else None

REPAIR = [("``", '"'), ("''", '"'), ("-LRB-", "("), ("-RRB-", ")"),
          ("-LCB-", "{"), ("-RCB-", "}"), ("-LSB-", "["), ("-RSB-", "]")]

def repair(text: str, spans):
    """Rewrite the residual PTB escapes in `text`, remapping every offset in `spans`."""
    out, shift, cuts = [], 0, []
    i = 0
    while i < len(text):
        for pat, rep in REPAIR:
            if text.startswith(pat, i):
                out.append(rep); cuts.append((i + len(pat), len(pat) - len(rep)))
                i += len(pat); break
        else:
            out.append(text[i]); i += 1
    new = "".join(out)
    def remap(p):
        d = sum(c for at, c in cuts if at <= p)
        return p - d
    return new, [(remap(s), remap(e)) if sp else None for sp in spans for s, e in [sp or (0, 0)]]
