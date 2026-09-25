"""Would rebuilding condition A today produce the same bytes? Compare per document."""
import sys, gzip, json, hashlib
from pathlib import Path
def digests(path):
    out = {}
    for line in gzip.open(path, "rt", encoding="utf-8"):
        d = json.loads(line)
        if d.get("text") is None:
            continue
        out[d["doc_id"]] = hashlib.sha256(d["text"].encode("utf-8")).hexdigest()[:16]
    return out
old, new = digests(sys.argv[1]), digests(sys.argv[2])
same = sum(1 for k in old if new.get(k) == old[k])
changed = [k for k in old if k in new and new[k] != old[k]]
print(f"  documents on disk {len(old)}, rebuilt {len(new)}, identical {same}, "
      f"changed {len(changed)}, missing {len(set(old) - set(new))}, new {len(set(new) - set(old))}")
