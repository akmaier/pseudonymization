# A1 at scale — what hashing actually protects

162,253 US Census surnames as the attacker's dictionary, TAB PERSON entities, N2 normaliser,
deterministic policy, realistic surrogates drawn from a 309,522-name inventory.

| technique | A1 top-1 | recovered | in scope? |
|---|---:|---:|---|
| **hash** (SHA-256) | **0.104** | 568 | yes — unkeyed |
| counter | 0.088 | 451 | yes — unkeyed |
| hmac | 0.000 | 0 | **no** — attacker cannot evaluate the function |
| aes_siv | 0.000 | 0 | **no** |
| table | 0.000 | 0 | **no** — the table is the secret |

The three zeros are **not measured resistance**. They are the threat model: without the key there is
nothing for the attacker to compute. Reporting them as a defensive result would be a category error,
so the implementation refuses to score them and says so in the result's own notes.

## The curve, which is the actual finding

A1 top-1 against how common the name is:

| band | inversion |
|---|---:|
| **very common** | **0.758** |
| common | 0.320 |
| uncommon | 0.083 |
| **not in the dictionary** | **0.000** |

And against name length:

| length | inversion |
|---:|---:|
| ≤ 4 | 0.27 |
| 5–7 | 0.35 |
| 8–11 | 0.07 |
| **12+** | **0.00** |

> **Hashing inverts three quarters of the commonest names and none of the rare ones. The names it
> protects are exactly the names that identify people.**

That is the sharp form of ENISA's verdict that a cryptographic hash is "prone to brute force and
dictionary attacks", and it is more useful than the verdict: the risk is not uniform, it is
concentrated on the population a dictionary already covers. A practitioner reading only the ENISA
line would conclude "do not hash"; reading this, they would conclude "hashing fails on the common
names, and a rare name is not protected by the hash but by its absence from the attacker's list" —
which is a much less comfortable place to be, because absence from a list is not a security property.

## How it sits with A2

The two attacks are complementary, and between them they close off the deterministic policy:

| | A1 dictionary | A2 frequency |
|---|---|---|
| applies to | unkeyed techniques only | **all five** |
| succeeds on | **common** names | **frequent** entities |
| needs | the pipeline and a name list | nothing but the released corpus |
| TAB | 0.104 | 0.013 |
| Enron | — | **0.201** |

A1 is stopped by a key. A2 is not stopped by anything except changing the policy. That asymmetry is
H1's content, and it is why the paper's recommendation is about policy rather than cryptography.

## Gazetteers

| source | gives | size | licence |
|---|---|---:|---|
| US Census 2010 surnames | surnames + counts | 162,253 | public domain |
| UCI "Gender by Name" (591) | given names + sex + counts | 147,269 | CC-BY 4.0 |
| GeoNames `cities15000` | cities + population | 34,135 | CC-BY 4.0 |

On the cluster at `gazetteers/`. CC-BY is compatible with the build-recipe distribution: loaders and
a manifest ship, the tables themselves do not.
