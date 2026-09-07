# OntoNotes 5.0 (LDC2013T19) — LDC

**Blocked on one fact:** is FAU an LDC member, and if so through which department?

LDC states that **non-members may license OntoNotes 5.0 at no charge**, subject to shipping and
handling. Members get it as part of the membership corpora. Either way the cost is negligible; the
question is which route is faster and who at FAU already holds the membership.

## Why it is in the meta corpus

It is the only member that supplies all three of these at once:

- **real names** in natural distribution (tier T1);
- **co-reference annotation** — one of only two corpora in the set that has it, the other being TAB;
- **non-Latin scripts with real names** — English, **Chinese** and **Arabic**, across news, broadcast,
  weblog, telephone speech and usenet.

That last point is why it was added. The OpenAI Privacy Filter evaluation reports detector collapse
on non-Latin scripts (Arabic F1 0.04, Cyrillic 0.03), which is exactly where H1 and H2 are stressed
hardest — and before OntoNotes we had no non-Latin corpus with real names at all.

English portion: 3,637 documents, ~2 M tokens, 18 named-entity types.

## Next step

1. AM checks FAU's LDC status (the Technische Fakultät or the university library will know).
2. If a member: request through the existing membership.
3. If not: apply as a non-member — no licence fee, confirm the current delivery route is electronic
   rather than physical media.
4. Read the licence for the same two clauses as BRONCO — re-identification and third-party transfer —
   before assuming the leakage axis runs here. OntoNotes is a general NLP corpus rather than a
   clinical one, so the terms are likely looser, but check rather than assume.
