"""ONF parser + detokenised-text alignment, third cut. Probe-quality, but this is the shape
the production adapter would take."""
from __future__ import annotations
import re, unicodedata

SEC = re.compile(r"^(Plain sentence|Treebanked sentence|Speaker information|Tree|Leaves):\s*$")
RULE = re.compile(r"^-{3,}\s*$")
BAR = re.compile(r"^-{60,}\s*$")

PTB = {"-LRB-": "(", "-RRB-": ")", "-LCB-": "{", "-RCB-": "}",
       "-LSB-": "[", "-RSB-": "]", "``": '"', "''": '"',
       "/.": ".", "/?": "?", "/-": "-", "/,": ","}
TRACE = re.compile(r"^(\*.*\*(-\d+)?|\*(-\d+)?|0)$")
# speech-transcription markers the Plain sentence drops
DROP = re.compile(r"^(%pw|%uh|%ah|%um|%hm|%bcack|\[.*\]|<.*>)$")

AR_MARKS = re.compile("[ً-ْٰـٓ-ٟۖ-ۭ]")

def strip_marks(s: str) -> str:
    """Drop Arabic harakat/tatweel WITHOUT NFD-decomposing hamza carriers.

    NFD splits U+0626 (ya with hamza) into ya + combining hamza; dropping "every combining
    mark" then silently rewrites the letter.  Measured on a 120-document sample: that error
    alone produced 185 unalignable 'rayys' tokens for 'rais'."""
    return AR_MARKS.sub("", s)

def norm_token(t: str, lang: str) -> str:
    if t in PTB:
        return PTB[t]
    if DROP.match(t):
        return ""
    t = t.replace("\\/", "/").replace("\\*", "*")
    if lang == "arabic":
        t = strip_marks(t)
        t = (t.replace("{", "ا").replace("<", "إ").replace(">", "أ")
               .replace("ٱ", "ا").replace("|", "آ")
               .replace("`", "").replace("_", "").replace("-", ""))
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
            s = l.strip().lstrip("!").strip()          # '!' = annotation not on a tree node
            m = re.match(r"^name:\s+(\S+)\s+(\d+)-(\d+)\s*(.*)$", s)
            if m:
                names.append((m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)))
                continue
            m = re.match(r"^coref:\s+(\S+)\s+(\S+)\s+(\d+)-(\d+)\s*(.*)$", s)
            if m:
                corefs.append((m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), m.group(5)))
        yield {"plain": plain, "tokens": tokens, "speaker": speaker,
               "names": names, "corefs": corefs}

def align(tokens, plain, lang):
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
        j = plain.lower().find(tn.lower(), pos, pos + len(tn) + LOOK)
        if j >= 0:
            spans[k] = (j, j + len(tn)); pos = j + len(tn); continue
    leftover = plain[pos:].strip()
    unaligned = [k for k, sp in enumerate(spans)
                 if sp is None and not TRACE.match(tokens[k]) and norm_token(tokens[k], lang)]
    return spans, unaligned, leftover

def span_of(spans, i, j):
    sub = [spans[k] for k in range(i, j + 1) if k < len(spans) and spans[k]]
    if not sub:
        return None
    return (sub[0][0], sub[-1][1])
