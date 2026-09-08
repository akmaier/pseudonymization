#!/usr/bin/env python3
"""Build the Enron sample — ``subject`` @ 0.10 — on a machine that can hold it.

**Scheme fixed to ``subject`` (AM, 2026-09-08).** ``experiment_plan.md`` §5 assigned different
schemes to different measurements — ``stratified`` for detection, utility and A2; ``subject`` for
A3, A5 and drift — but two schemes are two different document sets, and detection would then have to
cover their union. Enron is already 86 % of the detection budget, so that doubles the most expensive
thing in the study. One scheme it is, and ``subject`` is the one to keep:

* **Profile completeness cannot be recovered by any other means.** Measured at rate 0.2, ``subject``
  retains 67 % of each entity's profile against ``stratified``'s 20 %. A3 and A5 are starved by the
  alternative; nothing is starved by this one.
* **A2 tolerates it.** Inside a kept mailbox the frequency distribution is *complete*, so pseudonym
  frequency still mirrors real-name frequency. What is lost is statistical power — fewer entities —
  not the effect. §5's own prediction is that A2 is robust to rate.
* **Detection and utility do not care which documents**, only how many.
* And with one scheme, detection, stability, utility and leakage are measured **on the same
  documents**, which is the property §4 claims for Enron in the first place.

**Why this runs here and not on the cluster.** Enron cannot be materialised in full anywhere: the
head node has too little memory, and a full pass on an 18 GB laptop was killed while constructing the
517,401 documents. So the sample is taken as a **stream filter**, before documents are built:

1. One pass over every message builds the identity table — it holds names, not texts, and took 30 s
   for 11,124 names. Cross-document identity is therefore complete **even for mailboxes that are not
   sampled**, which is what makes the kept profiles trustworthy.
2. Mailboxes are drawn with the same rule and seed as :func:`pseudonymkit.sampling.by_subject`.
3. A second pass builds documents for the drawn mailboxes only, reusing that full identity table.

The result is written as JSONL and shipped to the cluster, where the detection run reads it.

    python experiments/build_enron.py --source enron_mail_20150507.tar.gz --out enron_subject010.jsonl.gz
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from pseudonymkit.adapters import enron
from pseudonymkit.domain import Corpus
from pseudonymkit.serialisation import write_corpus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True, help="enron_mail_20150507.tar.gz")
    ap.add_argument("--out", type=Path, required=True, help="destination .jsonl or .jsonl.gz")
    ap.add_argument("--rate", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-name-count", type=int, default=2)
    args = ap.parse_args()

    started = time.time()

    def log(message: str) -> None:
        print(f"[{time.time() - started:7.1f}s] {message}", flush=True)

    # --- pass 1: every mailbox, and the identity table over *all* messages --------------------
    log("pass 1/2 — scanning every message for mailboxes and sender identities")
    mailboxes: set[str] = set()
    seen = 0

    def raws():
        nonlocal seen
        for _, mailbox, raw in enron.iter_raw_messages(args.source):
            mailboxes.add(mailbox)
            seen += 1
            if seen % 100_000 == 0:
                log(f"  {seen} messages, {len(mailboxes)} mailboxes")
            yield raw

    table = enron.build_identity_table(raws())
    known = sum(1 for n in table.names() if table.counts.get(n, 0) >= args.min_name_count)
    log(f"pass 1 done — {seen} messages, {len(mailboxes)} mailboxes, "
        f"{len(table.by_name)} names ({known} seen at least {args.min_name_count}×)")

    # --- draw whole mailboxes, exactly as sampling.by_subject does ------------------------------
    ordered = sorted(mailboxes)
    keep_n = max(1, round(len(ordered) * args.rate))
    keep = sorted(random.Random(args.seed).sample(ordered, keep_n))
    log(f"drawn: {keep_n}/{len(ordered)} mailboxes at rate {args.rate} seed {args.seed}")
    log(f"  {', '.join(keep[:8])}{' …' if len(keep) > 8 else ''}")

    # --- pass 2: documents for the drawn mailboxes only, with the full identity table -----------
    log("pass 2/2 — building documents for the drawn mailboxes")
    corpus = enron.load(
        args.source,
        mailboxes=keep,
        identity_table=table,
        min_name_count=args.min_name_count,
        progress=lambda m: log(f"  {m}"),
    )
    # Stamp the provenance the way sampling._stamp does, so no result can be quoted without it.
    name = f"enron[subject@{args.rate}#{args.seed}]"
    corpus = Corpus(name, corpus.documents)

    mentions = sum(len(d.mentions) for d in corpus.documents)
    subjects = {d.subject_id for d in corpus.documents}
    log(f"built {len(corpus)} documents, {mentions} mentions, {len(subjects)} subjects")

    written = write_corpus(corpus, args.out)
    size = args.out.stat().st_size / 1e6
    log(f"wrote {written} documents to {args.out} ({size:.0f} MB) as {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
