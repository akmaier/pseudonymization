#!/usr/bin/env python3
"""Build ENRON 2.0 — body and subject only, deduplicated, CARDIO:DE-sized (AM, 2026-10-03).

The why, and the six decisions, are in :mod:`pseudonymkit.adapters.enron2`. This script is the
build: one streaming pass over all 517,401 messages of the archive, then a seeded draw, then the
header-informed gold for the drawn messages only.

    . config/env.sh
    sbatch experiments/slurm/build_enron2.sbatch

What one pass does, per message: learn the sender's name and address for the identity table;
extract the body and strip quoting and embedded header blocks; skip it if nothing is left;
deduplicate it against every body seen so far, across folders *and* mailboxes, keeping the copy
with the smallest archive path so the choice does not depend on read order. The envelope — every
address on From, To, Cc and Bcc — is kept beside the body, because it is what resolves the names in
it, but it never enters the document text.

Then the draw (:func:`pseudonymkit.adapters.enron2.draw`): whole threads within a mailbox, in a
seeded order, until the corpus holds CARDIO:DE's token count, with no mailbox above the cap and no
message a near-duplicate of one already drawn.

**Nothing is overwritten.** The paper-1 corpus is ``enron_A.jsonl.gz`` and stays as it is; this
writes ``enron2_A.jsonl.gz`` and refuses to replace an existing file without ``--force``. An
earlier session overwrote a paper-1 result file in place; that does not happen here.

**Acceptance checks run in the same process** and land in the provenance file beside the corpus:
the token total, zero exact and zero near duplicates among the drawn bodies, zero embedded header
blocks left, the mailbox spread, the gold by rule, and how the attack split falls — identical
bodies across its halves must be zero, and threads that straddle it are counted, because the
subject line stays in the text (AM, 2026-10-03) and repeats down a thread.
"""
from __future__ import annotations

import argparse
import email
import json
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "src")

from pseudonymkit.adapters import enron
from pseudonymkit.adapters.enron2 import (
    GOLD_RULES,
    decoded_body,
    HEADER_LINE,
    WINDOW,
    NameIndex,
    ShingleIndex,
    Unit,
    clean_body,
    dedup_key,
    document_text,
    draw,
    find_mentions,
    participants,
    shingles,
    thread_key,
)
from pseudonymkit.attacks.profiles import disjoint_document_split
from pseudonymkit.domain import Corpus, Document
from pseudonymkit.metrics.detection import tokenise
from pseudonymkit.paths import condition_a_dir, shared_corpora
from pseudonymkit.serialisation import write_corpus

CARDIODE_TOKENS = 885_059
"""CARDIO:DE in the study's own tokens (``metrics.detection.tokenise``), measured on 2026-10-03 over
the 400 letters of ``cardiode_A``. AM, 2026-10-03: ENRON 2.0 is to be about the same size, so that
the two corpora cost the same to detect and carry their sensitivity and specificity on comparable
denominators."""

T0 = time.time()


def log(message: str) -> None:
    print(f"[{time.time() - T0:8.1f}s] {message}", flush=True)


def commit() -> str:
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "experiments"],
                               capture_output=True, text=True)
        return head.stdout.strip()[:12] + ("+dirty" if dirty.stdout.strip() else "")
    except Exception:
        return "unknown"


def gazetteers():
    """The union the paper-1 adapter uses, plus given names and surnames apart for the full-name
    test. ``None`` everywhere if the lists are not on this machine — reported, not hidden."""
    try:
        from pseudonymkit.attacks.priors import load_census_surnames, load_uci_given_names
        root = shared_corpora() / "gazetteers"
        surnames = frozenset(n.casefold() for n in load_census_surnames(root / "Names_2010Census.csv"))
        given = frozenset(n.casefold() for n in load_uci_given_names(root / "name_gender_dataset.csv"))
        return surnames | given, given, surnames
    except Exception as error:
        log(f"  NO GAZETTEERS ({type(error).__name__}: {error}) — structural name rules only")
        return None, None, None


def embedded_blocks(body: str) -> bool:
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if HEADER_LINE.match(line):
            keys = {HEADER_LINE.match(l).group(1).casefold()
                    for l in lines[i:i + WINDOW] if HEADER_LINE.match(l)}
            if len(keys) >= 2:
                return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path,
                    default=None, help="default: <shared corpora>/enron/enron_mail_20150507.tar.gz")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <condition A dir>/enron2_A.jsonl.gz")
    ap.add_argument("--token-budget", type=int, default=CARDIODE_TOKENS)
    ap.add_argument("--mailbox-cap", type=float, default=0.02,
                    help="largest share of the token budget one mailbox may supply. 0.02 means at "
                         "least fifty mailboxes; the paper-1 draw had two people at 68 %%")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-name-count", type=int, default=2)
    ap.add_argument("--validation", type=int, default=300,
                    help="messages drawn, seeded, for the human validation of the gold")
    ap.add_argument("--validation-out", type=Path,
                    default=Path("results/enron2/validation_sample.jsonl"))
    ap.add_argument("--limit", type=int, default=0, help="messages read, for a smoke run only")
    ap.add_argument("--force", action="store_true", help="replace an existing output file")
    args = ap.parse_args()

    source = args.source or shared_corpora() / "enron" / "enron_mail_20150507.tar.gz"
    out = args.out or condition_a_dir() / "enron2_A.jsonl.gz"
    provenance_path = out.parent / (out.name.split(".")[0] + ".provenance.json")
    if out.exists() and not args.force:
        raise SystemExit(f"{out} exists; refusing to overwrite it without --force")

    # --- one pass over the archive ---------------------------------------------------------------
    log(f"reading {source}{f' (first {args.limit} messages only)' if args.limit else ''}")
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    unique: dict[str, dict] = {}
    seen = Counter()
    for path, mailbox, raw in enron.iter_raw_messages(source, limit=args.limit or None):
        seen["messages"] += 1
        if seen["messages"] % 50_000 == 0:
            log(f"  {seen['messages']:,} messages, {len(unique):,} distinct bodies")
        message = email.message_from_string(raw)
        pair = enron._sender_pair(message)
        if pair is not None:
            votes[pair[0].casefold()][pair[1]] += 1
        body = clean_body(decoded_body(message))
        if not body:
            seen["empty_after_stripping"] += 1
            continue
        key = dedup_key(body)
        held = unique.get(key)
        if held is not None:
            seen["duplicate_bodies_dropped"] += 1
            if path >= held["path"]:
                continue
        unique[key] = {
            "path": path,
            "mailbox": mailbox,
            "folder": (message.get("X-Folder") or "").replace("\\", "/").rstrip("/").split("/")[-1],
            "subject": str(message.get("Subject") or ""),
            "body": body,
            "envelope": participants(message),
            "message_id": message.get("Message-ID"),
            "date": message.get("Date"),
            "origin": (message.get("X-Origin") or mailbox).strip().casefold(),
        }
    mailboxes = {rec["mailbox"] for rec in unique.values()}
    log(f"pass done: {seen['messages']:,} messages, {seen['empty_after_stripping']:,} empty after "
        f"stripping, {seen['duplicate_bodies_dropped']:,} duplicate bodies, {len(unique):,} distinct "
        f"bodies in {len(mailboxes)} mailboxes")

    table = enron.IdentityTable(
        by_name={name: addrs.most_common(1)[0][0] for name, addrs in votes.items()},
        counts={name: sum(addrs.values()) for name, addrs in votes.items()},
    )
    union, given, surnames = gazetteers()
    index = NameIndex.build(table, min_name_count=args.min_name_count, gazetteer=union,
                            given=given, surnames=surnames)
    log(f"identity table: {len(table.by_name):,} display names; name index: "
        f"{len(index.address_forms):,} addresses with forms, {len(index.multi):,} full-name forms, "
        f"{len(index.single):,} single names")

    # --- the draw ----------------------------------------------------------------------------------
    tokens = {key: len(tokenise(document_text(rec["subject"], rec["body"])))
              for key, rec in unique.items()}
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for key, rec in unique.items():
        thread = thread_key(rec["subject"])
        grouped[(rec["mailbox"], thread if thread else "#" + rec["path"])].append(key)
    units = [Unit(mailbox, thread, tuple(sorted(keys, key=lambda k: unique[k]["path"])))
             for (mailbox, thread), keys in grouped.items()]
    log(f"{len(units):,} units (threads within a mailbox), {sum(tokens.values()):,} tokens "
        f"available against a budget of {args.token_budget:,}")
    accepted, draw_stats = draw(units, tokens, lambda k: unique[k]["body"],
                                budget=args.token_budget, cap_fraction=args.mailbox_cap,
                                seed=args.seed)
    log(f"drawn: {len(accepted):,} messages, {draw_stats['tokens']:,} tokens from "
        f"{draw_stats['mailboxes']} mailboxes; {draw_stats.get('messages_near_duplicate', 0):,} "
        f"near-duplicates skipped, {draw_stats.get('units_over_mailbox_cap', 0):,} units over the cap")

    # --- documents and gold -----------------------------------------------------------------------
    documents = []
    for key in sorted(accepted, key=lambda k: unique[k]["path"]):
        rec = unique[key]
        text = document_text(rec["subject"], rec["body"])
        documents.append(Document(
            doc_id=rec["path"],
            text=text,
            language="en",
            mentions=tuple(find_mentions(rec["path"], text, rec["envelope"], index)),
            corpus="enron2",
            domain="email",
            provenance="real",
            subject_id=rec["origin"],
            task={"name": "enron2"},
            metadata={
                "annotation": "structural, header-informed",
                "mailbox": rec["mailbox"],
                "folder": rec["folder"],
                "thread": thread_key(rec["subject"]),
                "message_id": rec["message_id"],
                "date": rec["date"],
                "envelope": list(rec["envelope"]),
            },
        ))
    name = (f"enron2[body+subject,dedup+near,cap{args.mailbox_cap:g},"
            f"{args.token_budget}tok#{args.seed}]")
    corpus = Corpus(name, tuple(documents))

    # --- acceptance checks ------------------------------------------------------------------------
    bodies = [d.text.split("\n\n", 1)[1] for d in documents]
    exact = len(bodies) - len({dedup_key(b) for b in bodies})
    recheck = ShingleIndex()
    near = 0
    for body in bodies:
        sh = shingles(body)
        if recheck.is_near(sh):
            near += 1
        recheck.add(sh)
    blocks = sum(embedded_blocks(b) for b in bodies)
    total_tokens = sum(len(tokenise(d.text)) for d in documents)
    per_mailbox = Counter()
    for d in documents:
        per_mailbox[d.metadata["mailbox"]] += len(tokenise(d.text))
    rules = Counter(m.attributes.get("gold_rule") for d in documents for m in d.mentions)
    person = [m for d in documents for m in d.mentions if m.span.type == "PERSON"]
    docs_per_entity = Counter()
    for d in documents:
        for e in {m.gold_entity_id for m in d.mentions if m.span.type == "PERSON" and m.gold_entity_id}:
            docs_per_entity[e] += 1
    reference, query = disjoint_document_split(corpus, seed=0)
    by_id = {d.doc_id: d for d in documents}
    ref_bodies = {dedup_key(by_id[i].text.split("\n\n", 1)[1]) for i in reference}
    ref_threads = {by_id[i].metadata["thread"] for i in reference if by_id[i].metadata["thread"]}
    query_docs = [by_id[i] for i in query]

    def people_in(ids):
        return {m.gold_entity_id for i in ids for m in by_id[i].mentions
                if m.span.type == "PERSON" and m.gold_entity_id}

    # A person the linkage attack can be scored on at all: present in both halves of its split.
    both_sides = people_in(reference) & people_in(query)
    checks = {
        "tokens": total_tokens,
        "token_budget": args.token_budget,
        "exact_duplicate_bodies": exact,
        "near_duplicate_bodies": near,
        "bodies_with_an_embedded_header_block": blocks,
        "mailboxes": len(per_mailbox),
        "largest_mailbox_share": max(per_mailbox.values()) / max(total_tokens, 1),
        "largest_mailbox_share_of_budget": max(per_mailbox.values()) / args.token_budget,
        "gold_mentions_by_rule": dict(rules),
        "person_mentions": len(person),
        "person_mentions_without_identity": sum(1 for m in person if not m.gold_entity_id),
        "people": len(docs_per_entity),
        "people_in_two_or_more_documents": sum(1 for c in docs_per_entity.values() if c >= 2),
        "people_on_both_sides_of_the_attack_split": len(both_sides),
        "attack_split_query_bodies_identical_to_a_reference_body":
            sum(1 for d in query_docs if dedup_key(d.text.split("\n\n", 1)[1]) in ref_bodies),
        "attack_split_query_documents_whose_thread_is_also_in_the_reference_half":
            sum(1 for d in query_docs if d.metadata["thread"] in ref_threads),
    }
    for key, value in checks.items():
        log(f"  check  {key:70s} {value if not isinstance(value, float) else round(value, 4)}")
    failures = [k for k in ("exact_duplicate_bodies", "near_duplicate_bodies",
                            "bodies_with_an_embedded_header_block",
                            "attack_split_query_bodies_identical_to_a_reference_body")
                if checks[k]]
    if failures:
        log(f"  ACCEPTANCE FAILED on {failures} — written anyway, for inspection, and reported")

    written = write_corpus(corpus, out)
    log(f"wrote {written:,} documents to {out} as {name}")

    # --- the validation sample for human adjudication ------------------------------------------
    sample = random.Random(args.seed + 1).sample(documents, min(args.validation, len(documents)))
    args.validation_out.parent.mkdir(parents=True, exist_ok=True)
    with args.validation_out.open("w", encoding="utf-8") as handle:
        for d in sorted(sample, key=lambda d: d.doc_id):
            handle.write(json.dumps({
                "doc_id": d.doc_id,
                "text": d.text,
                "envelope": d.metadata["envelope"],
                "gold": [{"start": m.span.start, "end": m.span.end, "text": m.span.text,
                          "type": m.span.type, "rule": m.attributes.get("gold_rule"),
                          "entity": m.gold_entity_id} for m in d.mentions],
            }, ensure_ascii=False) + "\n")
    log(f"wrote the validation sample: {len(sample)} messages to {args.validation_out}")

    provenance = {
        "corpus": name, "file": str(out), "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "commit": commit(), "source": str(source), "seed": args.seed,
        "mailbox_cap": args.mailbox_cap, "min_name_count": args.min_name_count,
        "decisions": "AM, 2026-10-03: body and subject only; embedded header blocks stripped; "
                     "deduplicated across folders and mailboxes, near-duplicates removed; all 150 "
                     "mailboxes with a per-mailbox cap; CARDIO:DE's token count; header-informed "
                     "gold; no utility task",
        "read": dict(seen), "distinct_bodies": len(unique), "mailboxes_in_archive": len(mailboxes),
        "identity_table_names": len(table.by_name),
        "gazetteers": union is not None,
        "units": len(units), "draw": draw_stats, "documents": len(documents),
        "checks": checks, "acceptance_failures": failures,
        "gold_rules": dict(GOLD_RULES),
        "validation_sample": {"file": str(args.validation_out), "messages": len(sample),
                              "seed": args.seed + 1},
    }
    provenance_path.write_text(json.dumps(provenance, indent=1), encoding="utf-8")
    log(f"wrote {provenance_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
