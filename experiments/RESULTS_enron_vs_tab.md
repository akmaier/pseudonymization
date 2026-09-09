# The frequency-skew prediction, tested

The TAB run produced a puzzle: under a deterministic policy Spearman ρ = 1.000 — the frequency
signal survives completely — yet A2 recovered only **1.3 %** of PERSON entities at top-1. The
reading was that TAB's entity distribution is nearly flat, so a perfectly preserved signal cannot
identify anyone, and the prediction that followed was:

> Enron should convert the signal into identification and TAB should not, because the same people
> recur across thousands of messages there.

**Confirmed.** 20,000 Enron messages sampled with stride 25 across the whole archive, 426,146
structural mentions, 1,208 distinct people, N2 normaliser, opaque tags.

| corpus | ρ (deterministic) | **A2 top-1** | A2 top-5 | entities mentioned once |
|---|---:|---:|---:|---:|
| TAB / ECHR | 1.000 | **0.013** | — | most |
| **Enron** | 1.000 | **0.201** | 0.499 | **0 %** |

Same rank correlation, **15× the identification**. Half of all pseudonyms are recovered within five
guesses. The frequency signal was identical in both corpora; only the shape of the distribution
differed.

So H1 should be stated as two claims rather than one:

1. **Under a deterministic policy the frequency signal survives completely and identically across
   techniques.** Counter, mapping table, SHA-256, HMAC and AES-SIV are again indistinguishable —
   every row in both corpora. The cryptographic axis does nothing.
2. **Whether that signal identifies anyone is a property of the corpus, not of the function.**
   Flat distribution, no identification; skewed distribution, one in five at the first guess.

The second is the more useful half for a practitioner: it says the question to ask about a corpus is
not which hash it used but how often its people recur.

## The curve, on the corpus that has one

A2 top-1 by mention-frequency band, deterministic policy:

| band | top-1 |
|---:|---:|
| 2–4 mentions | 0.042 |
| 5–19 | 0.047 |
| **20+** | **0.257** |

Frequent entities fall first, which is the shape the hash-versus-HMAC debate assumes — except that
here it holds for *every* technique, including the keyed ones.

## Cross-document drift, measured for the first time

Enron is now the only corpus in the meta corpus with cross-document entity identity, since n2c2
became unavailable. Under a deterministic policy with N2:

| | rate |
|---|---:|
| within-document fragmentation | 0.018 |
| **cross-document drift** | **0.147** |

**Drift is eight times fragmentation.** The same person is written differently in different
messages, so a scheme that looks stable inside a document is markedly less stable across a corpus.
That gap is invisible to every benchmark that scores spans within documents, and it is the concrete
form of the gap `experiment_plan.md` §3 identifies. Under a document-randomised policy drift is 1.000 by
construction, as specified.

## Caveats

Enron mentions are **structural** — derived from message headers and an identity table learned from
sender pairs — not human gold, and every document records that. The A2 reference distribution is
corpus-internal in both runs, which is the upper bound rather than the realistic setting; an
external gazetteer will be weaker. The sample is 20,000 of ~500,000 messages.

Rows: [`results/enron_first_cells.jsonl`](results/enron_first_cells.jsonl). Reproduce with
`python experiments/run_enron.py --enron <tarball> --limit 20000 --stride 25`.
