# A3 and A5 on Enron — after fixing train/test leakage

20,000 Enron messages (stride 25), 1,208 PERSON entities, structural annotations, N2, opaque tags,
five techniques × three policies × two attacks × two split modes. Job 777389, 22 minutes.
Rows: [`results/enron_reid_cells.jsonl`](results/enron_reid_cells.jsonl).

## The leak, and what it was worth

The first run built the **gallery from the originals of the same documents the queries came from**.
Pseudonymisation rewrites only entity spans, so both sides were byte-identical apart from the names:
the attack was matching a corpus against itself. AM flagged the numbers as implausible and was right.

| deterministic policy | leaky (`--split none`) | **honest (`--split documents`)** | inflation |
|---|---:|---:|---:|
| A3 structural, Rank-1 | 0.967 | **0.673** | **+0.294** |
| A5 learned, Rank-1 | 0.961 | **0.702** | +0.259 |

The tell was in the first run and was explained away rather than followed: **the learned attacker
failed to beat a fixed cosine.** That reads much better as *neither was being asked to generalise*
than as *the signal saturates a fixed metric*.

## Corrected results

Means over the five techniques; spread across them in the last column.

| split | policy | attack | Rank-1 | Rank-5 | mAP | technique spread |
|---|---|---|---:|---:|---:|---:|
| **documents** | deterministic | A3 structural | **0.673** | 0.773 | 0.722 | 0.000 |
| **documents** | deterministic | A5 learned | **0.702** | 0.798 | 0.749 | 0.000 |
| documents | document-randomised | A3 | 0.014 | 0.030 | 0.026 | 0.001 |
| documents | document-randomised | **A5** | **0.071** | 0.156 | 0.119 | 0.005 |
| documents | fully-randomised | A3 | 0.003 | 0.009 | 0.009 | 0.001 |
| documents | fully-randomised | **A5** | **0.064** | 0.145 | 0.108 | 0.007 |

### 1. The policy still decides, and now credibly

Rank-1 falls **0.673 → 0.014 → 0.003** across the policy axis for the structural attacker. The
finding survived the correction; only its magnitude changed.

### 2. Technique-independence is now measured three ways

Spread across counter, table, hash, HMAC and AES-SIV is **0.000–0.008** in every row. A1, A2 and now
A3/A5 all say the same thing by different means: the cryptographic axis does not move the outcome.

### 3. Learning buys most where the fixed metric fails — the reverse of the leaky reading

| policy | A3 | A5 | ratio |
|---|---:|---:|---:|
| deterministic | 0.673 | 0.702 | 1.04× |
| document-randomised | 0.014 | 0.071 | **5.1×** |
| fully-randomised | 0.003 | 0.064 | **21×** |

Under the leaky protocol the two attackers were indistinguishable. Honestly evaluated, the learned
one dominates precisely where the signal is weak. **"Frozen defenders, trained attackers" is not a
posture, it is a 21× difference** — and any study that reports only an unlearned baseline against a
randomised policy will understate leakage by more than an order of magnitude.

### 4. Full randomisation does not fully protect

Under `full`, every mention receives its own pseudonym, so there is no entity to profile and A2
collapses to zero. The learned contextual attacker still reaches **Rank-1 0.064 against a 948-entity
gallery — about 60× chance (0.1 %)**. A single mention's surrounding text still points at its
subject. The policy that defeats frequency analysis outright is not a complete defence.

## Caveats, and one that is not yet resolved

- **A5's gallery is smaller than A3's** (622 vs 1,191 under a deterministic policy) because A5 needs
  an entity-disjoint train/test split, and a smaller gallery is an easier task. So the deterministic
  **1.04×** is inside that confound and should not be quoted as A5 > A3. The 5.1× and 21× are not:
  there the galleries are comparable (996 vs 1,191; 948 vs 1,191). **The fair comparison — A3
  restricted to A5's held-out entities and gallery — has not been run and should be.**
- Enron only; TAB has no cross-document identity so it cannot host this attack.
- Mentions are **structural**, derived from headers, not human gold.
- 20,000 of ~517,000 messages; single seed; no confidence intervals.
- Non-deterministic policies produce ~100k queries (one per entity-document pair), capped at 20,000
  by random sample; the cap is recorded in every row.

## What changed in the code

`disjoint_document_split()` partitions document ids so the attacker's knowledge and the released
corpus come from different documents. A regression test asserts the honest split never scores above
the leaky one. The leaky mode is retained, labelled, so the gap stays quantifiable — this table is
the argument for keeping it.
