"""Minimal .onf parser + token->plain-sentence character alignment. Probe quality."""
from __future__ import annotations
import re, unicodedata, collections

SEC = re.compile(r"^(Plain sentence|Treebanked sentence|Speaker information|Tree|Leaves):\s*$")
RULE = re.compile(r"^-{3,}\s*$")
BAR = re.compile(r"^-{50,}\s*$")

PTB = {"-LRB-": "(", "-RRB-": ")", "-LCB-": "{", "-RCB-": "}",
       "-LSB-": "[", "-RSB-": "]", "``": '"', "''": '"', "`": "'"}
TRACE = re.compile(r"^(\*[A-Za-z?]*\*(-\d+)?|\*(-\d+)?|0|\*[A-Za-z]+\*)$")
DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")

def _norm_token(t: str) -> str:
    if t in PTB:
        return PTB[t]
    t = t.replace(r"\/", "/").replace(r"\*", "*")
    return t

def _ar_norm(s: str) -> str:
    s = DIAC.sub("", s)
    s = s.replace("ٱ", "ا").replace("{", "ا").replace("<", "إ").replace(">", "أ")
    return s

def parse_onf(text: str):
    """Yield dicts: {plain, tokens, speaker, leaves:[(idx, tok)], anns:[(kind,label,i,j,surface)]}."""
    lines = text.split("\n")
    blocks, cur = [], []
    for ln in lines:
        if BAR.match(ln):
            if cur:
                blocks.append(cur)
            cur = []
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    for blk in blocks:
        sections, name, buf = {}, None, []
        for ln in blk:
            m = SEC.match(ln)
            if m:
                if name:
                    sections[name] = buf
                name, buf = m.group(1), []
                continue
            if RULE.match(ln) and not buf:
                continue
            if name:
                buf.append(ln)
        if name:
            sections[name] = buf
        if "Plain sentence" not in sections:
            continue
        plain = " ".join(l.strip() for l in sections["Plain sentence"] if l.strip())
        tb = " ".join(l.strip() for l in sections.get("Treebanked sentence", []) if l.strip())
        tokens = tb.split()
        speaker = None
        for l in sections.get("Speaker information", []):
            if l.strip().startswith("name:"):
                speaker = l.split(":", 1)[1].strip()
        anns = []
        for l in sections.get("Leaves", []):
            s = l.strip()
            m = re.match(r"^(coref|name):\s+(\S+)\s+(?:(\S+)\s+)?(\d+)-(\d+)\s+(.*)$", s)
            if m:
                kind, a, b, i, j, surf = m.groups()
                if kind == "name":
                    anns.append((kind, a, int(i), int(j), surf))
                else:
                    anns.append((kind, b, int(i), int(j), surf))
        yield {"plain": plain, "tokens": tokens, "speaker": speaker, "anns": anns}

def align(tokens, plain, arabic=False):
    """Greedy token -> (start,end) in plain. Returns (spans, n_unmatched_nontrace, consumed_all)."""
    P = plain
    Pn = _ar_norm(P) if arabic else P
    spans, unmatched, pos = [], 0, 0
    for t in tokens:
        tn = _norm_token(t)
        if arabic:
            tn = _ar_norm(tn).replace("-", "")
        while pos < len(P) and P[pos].isspace():
            pos += 1
        if tn and Pn.startswith(tn, pos):
            spans.append((pos, pos + len(tn)))
            pos += len(tn)
        else:
            spans.append(None)
            if not TRACE.match(t):
                unmatched += 1
    rest = P[pos:].strip()
    return spans, unmatched, (rest == "")
