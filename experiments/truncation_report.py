"""Output truncation as a first-class number — and the gap it opens between two pipeline stages.

A gateway reply that ends with ``finish_reason="length"`` carries a span list that is short because
the model ran out of output budget, not because the text was clean.  :meth:`LLMDetector.detect_with_meta`
records that per window, which is what makes the two cases distinguishable at all.

**The two consumers of that flag disagree, and the disagreement is not visible in either's output.**
:func:`detected_documents` — and therefore every condition B and C — drops a truncated record, so the
released text is never built from a half-finished span list.  :mod:`experiments/score_detection` does
not: it reads the cache directly, so the detection table scores those documents with the spans the
model managed before it was cut off, counting the rest as misses.  The detection table and the
utility/leakage tables are therefore computed over different subsets for exactly the models that
truncate most.

Neither choice is obviously wrong.  Scoring the truncated reply measures what a deployment at that
output budget would actually get, which is a real operating characteristic; dropping it measures the
detector's ability to find identifiers, which is what axis D is nominally about.  What is wrong is
leaving the difference unmeasured, so this reports it: per model, the truncation rate and the token
recall computed both ways, over the same documents.

    python experiments/truncation_report.py --corpus cardiode --out results/detection
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_detection import CORPORA, restrict  # noqa: E402

from pseudonymkit.detectors.cache import DetectorCache  # noqa: E402
from pseudonymkit.metrics.detection import (  # noqa: E402
    frequency_weight,
    prepare,
    score_prepared,
    tokenise,
)
from pseudonymkit.serialisation import iter_documents  # noqa: E402
from pseudonymkit.taxonomy import Harmoniser, source_for  # noqa: E402


def truncated_documents(cache: DetectorCache, detector: str) -> set[str]:
    """Documents whose latest successful record was cut off.

    Later records win, as everywhere else: a document re-detected cleanly is no longer truncated.
    """
    out: set[str] = set()
    for record in cache._read(cache.path(detector)):
        if record.get("error") is not None:
            continue
        if record.get("truncated"):
            out.add(record["doc_id"])
        else:
            out.discard(record["doc_id"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, choices=sorted(CORPORA))
    ap.add_argument("--cache", type=Path, default=Path("results/detector_cache"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    documents = list(iter_documents(CORPORA[args.corpus]()))
    texts = {d.doc_id: d.text for d in documents}
    counts: Counter[str] = Counter()
    total = 0
    for document in documents:
        for start, end in tokenise(document.text):
            counts[document.text[start:end].casefold()] += 1
            total += 1
    index = prepare(documents, corpus=args.corpus, weight=frequency_weight(counts, total),
                    weight_model=f"unigram:{args.corpus}")
    cache = DetectorCache(args.cache, args.corpus)
    every = {d.doc_id for d in documents}

    print(f"=== {args.corpus}: {len(documents)} documents ===")
    print(f"{'detector':<54} {'trunc':>6} {'rate':>7} {'tokR scored':>12} {'tokR clean':>11} "
          f"{'delta':>7}")
    rows = []
    for path in sorted(cache.root.glob("*.jsonl")):
        name = path.stem.replace("__", "/")
        truncated = truncated_documents(cache, name)
        if not truncated:
            continue
        harmoniser = Harmoniser(source_for(name, args.corpus))
        spans = {d: harmoniser.spans(o.spans)
                 for d, o in cache.load(name, texts=texts).items()}
        scored = score_prepared(index, spans, detector=name)
        keep = every - truncated
        clean = score_prepared(restrict(index, keep),
                               {d: s for d, s in spans.items() if d in keep}, detector=name)
        row = {
            "corpus": args.corpus, "detector": name,
            "documents": len(documents), "truncated": len(truncated),
            "truncation_rate": len(truncated) / max(len(documents), 1),
            "token_recall_as_scored": scored.token_recall,
            "token_recall_excluding_truncated": clean.token_recall,
            "delta": clean.token_recall - scored.token_recall,
            "note": "as_scored is what results/detection reports; excluding_truncated is the "
                    "subset conditions B and C are actually built from",
        }
        rows.append(row)
        print(f"{name:<54} {len(truncated):>6} {row['truncation_rate']:7.1%} "
              f"{scored.token_recall:12.3f} {clean.token_recall:11.3f} {row['delta']:+7.3f}")

    if not rows:
        print("  no truncated records — the two stages agree on this corpus")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        destination = args.out / f"{args.corpus}_truncation.jsonl"
        destination.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        print(f"\nwrote {len(rows)} rows to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
