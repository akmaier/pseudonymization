"""Integrity of the detector cache — what is on disk, and whether it can be trusted.

The cache is append-only JSONL, and :meth:`DetectorCache._read` deliberately skips a line it cannot
parse: a job killed by a wall clock leaves a torn final line, and losing the run because of it would
be worse than losing the line.  The cost of that tolerance is silence.  A record damaged in the
*middle* of a file is skipped just as quietly as a torn last line, and nothing downstream can tell
the difference between a document that was never detected and one whose record was destroyed.

Two things actually damaged records here, and they are worth separating because only one was a bug:

* **Interleaved writes.**  ``O_APPEND`` is atomic only to ``PIPE_BUF`` (4 KB); a record runs to 13 KB.
  Two gateway *processes* overlapping across a restart wrote inside one another, leaving a truncated
  record spliced onto an intact one.  Fixed by the ``flock`` in :meth:`DetectorCache.append`; this
  checker is how the fix is confirmed to hold.
* **Storage.**  One record is a run of NUL bytes — no JSON at all, written by nothing this code does.
  That is the overnight service on the home directories, and no amount of locking prevents it.

So this reports, per (corpus, detector): lines that will not parse, records carrying a NUL, records
with no ``text_sha256`` (written before the digest existed, therefore unverifiable), recorded
failures, duplicate document ids, and coverage against the corpus.  It **names the affected document
ids**, because the repair is to re-detect exactly those and nothing else.

Read-only.  It never edits a cache file: a corrupt record is evidence until a re-detection replaces
it, and rewriting the file in place would destroy the evidence and the append-only guarantee at once.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pseudonymkit.detectors.cache import DetectorCache, text_digest  # noqa: E402
from pseudonymkit.paths import cardiode_a_optional, condition_a_dir, work_dir  # noqa: E402
from pseudonymkit.serialisation import iter_documents  # noqa: E402

CORPORA = ("cardiode", "tab", "ontonotes", "enron")


def condition_a(corpus: str) -> Path | None:
    if corpus == "cardiode":
        return cardiode_a_optional()
    return condition_a_dir() / f"{corpus}_A.jsonl.gz"


def inspect(path: Path) -> dict:
    """One cache file, line by line, without going through the tolerant reader."""
    report = {
        "lines": 0, "parsed": 0, "unparseable": [], "nul": [], "no_digest": [],
        "errors": [], "doc_ids": Counter(), "spans": 0,
    }
    with path.open("rb") as handle:
        for number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            report["lines"] += 1
            if b"\x00" in raw:
                report["nul"].append(number)
                continue
            try:
                record = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                report["unparseable"].append(number)
                continue
            report["parsed"] += 1
            doc_id = record.get("doc_id")
            report["doc_ids"][doc_id] += 1
            if record.get("error") is not None:
                report["errors"].append(doc_id)
                continue
            report["spans"] += len(record.get("spans", ()))
            if record.get("text_sha256") is None:
                report["no_digest"].append(doc_id)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpora", nargs="+", default=list(CORPORA))
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--stale", action="store_true",
                    help="also load condition A and report records whose digest no longer matches")
    ap.add_argument("--ids", action="store_true", help="print the affected document ids")
    args = ap.parse_args()

    root = args.cache or (work_dir() / "results" / "detector_cache")
    bad_total = 0

    for corpus in args.corpora:
        cache = DetectorCache(root, corpus)
        if not cache.root.exists():
            print(f"\n=== {corpus}: no cache at {cache.root} ===")
            continue

        texts: dict[str, str] = {}
        if args.stale:
            source = condition_a(corpus)
            if source is None:
                print(f"\n=== {corpus}: condition A unavailable (PSEUDONYMKIT_DUA unset) — "
                      f"staleness not checked ===")
            elif not source.exists():
                print(f"\n=== {corpus}: {source} missing — staleness not checked ===")
            else:
                texts = {d.doc_id: d.text for d in iter_documents(source)}

        header = f"\n=== {corpus} ==="
        if texts:
            header += f"  {len(texts)} documents in condition A"
        print(header)

        for path in sorted(cache.root.glob("*.jsonl")):
            detector = path.stem.replace("__", "/")
            report = inspect(path)
            duplicates = {d: n for d, n in report["doc_ids"].items() if n > 1}
            stale: list[str] = []
            if texts:
                for doc_id, digest in cache.digests(detector).items():
                    current = texts.get(doc_id)
                    if current is not None and digest != text_digest(current):
                        stale.append(doc_id)

            damaged = len(report["unparseable"]) + len(report["nul"])
            bad_total += damaged
            flags = []
            if damaged:
                flags.append(f"DAMAGED {damaged}")
            if report["errors"]:
                flags.append(f"errors {len(report['errors'])}")
            if report["no_digest"]:
                flags.append(f"no-digest {len(report['no_digest'])}")
            if duplicates:
                flags.append(f"dup-ids {len(duplicates)}")
            if stale:
                flags.append(f"STALE {len(stale)}")
            if texts:
                missing = len(set(texts) - set(cache.digests(detector)))
                if missing:
                    flags.append(f"missing {missing}")

            unique = len(report["doc_ids"])
            print(f"  {detector:<56} lines {report['lines']:>6}  docs {unique:>6}"
                  + ("  " + ", ".join(flags) if flags else "  ok"))

            if args.ids and (damaged or stale):
                if report["unparseable"]:
                    print(f"      unparseable at lines: {report['unparseable']}")
                if report["nul"]:
                    print(f"      NUL bytes at lines:   {report['nul']}")
                if stale:
                    print(f"      stale doc ids:        {sorted(stale)[:20]}"
                          + (" …" if len(stale) > 20 else ""))

    print(f"\ndamaged records across all corpora: {bad_total}")
    return 1 if bad_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
