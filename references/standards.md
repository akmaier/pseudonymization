# Standards and regulatory references

Retrieved 2026-09-06. **iso.org returns 403 to scripted access** — entries below marked *not
verified* were not opened directly and must be checked before being relied on.

| ref | what it is | status |
|---|---|---|
| **DIN EN ISO 25237:2026-06** — *Medizinische Informatik — Pseudonymisierung* (ISO/DIS 25237), `10.31030/3696721` | the health-informatics pseudonymisation standard, **revised June 2026** | metadata verified via Crossref; **text not obtained — not open access** |
| DIN EN ISO 25237:2017-05, `10.31030/2555889` | superseded edition | metadata verified |
| BSI *Health informatics. Pseudonymization*, `10.3403/30285709` | BSI equivalent | metadata verified |
| **ENISA (2021), *Data Pseudonymisation: Advanced Techniques and Use Cases*** | the practical European reference; source of the technique and policy taxonomies used in `PLAN.md` | **downloaded and read** |
| ENISA (2019), *Pseudonymisation techniques and best practices* | the earlier report ENISA 2021 builds on | page verified, PDF not read |
| ISO/IEC 20889 | privacy-enhancing de-identification terminology and technique classification | *not verified* |
| GDPR Art. 4(5) | legal definition of pseudonymisation | — |
| Art. 29 WP Opinion 05/2014 on Anonymisation Techniques | the origin of the "hashing is pseudonymisation, not anonymisation" position | *not verified* |

## The two taxonomies that structure the study

**Techniques** (ENISA 2021), with ENISA's own verdicts:

| technique | verdict |
|---|---|
| Counter | simplest; the ordinal value "can still provide information on the order of the data" |
| RNG + mapping table | stronger; *"Collisions, however, may be an issue, as well as scalability"* |
| Cryptographic hash | *"generally considered **weak** as a pseudonymisation technique, as it is prone to **brute force and dictionary attacks**"* |
| MAC / HMAC | *"generally considered a **robust** pseudonymisation technique from a data protection point of view"* |
| Symmetric encryption | robust |

ENISA also groups the strong three: *"random number generator, message authentication codes and
encryption are stronger techniques as they prevent by design exhaustive search, dictionary search and
random search."*

**Policies** (ENISA 2021) — the axis the study turns on:

> *"fully-randomised pseudonymisation offers the best protection level but prevents any comparison
> between databases. Document-randomised and deterministic functions provide utility but allow
> linkability between records."*

The stability requirement — one person, one pseudonym, corpus-wide — forces the **deterministic**
policy, i.e. the one the standard itself says permits linkage. That trade-off is stated
qualitatively in the standard and, as far as this survey found, has never been measured.
