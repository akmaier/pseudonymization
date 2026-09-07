"""Axis A: the pseudonymisation policy.

ENISA distinguishes deterministic, document-randomised and fully-randomised pseudonymisation and
states the trade-off qualitatively: full randomisation protects best but prevents any comparison
between records, while the other two provide utility at the price of linkability.

In this implementation a policy is *only* a scoping rule.  It says what the entity key is qualified
by before the technique maps it to an index, and nothing else.  That is what keeps axes A and B
orthogonal: no technique can make a fully-randomised corpus linkable, and none can make a
deterministic one unlinkable.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .domain import Mention
from .registry import Registry

__all__ = ["Policy", "POLICIES"]


@runtime_checkable
class Policy(Protocol):
    """Qualifies an entity key with the scope within which a pseudonym stays stable."""

    name: str

    def scope_key(self, entity_key: str, mention: Mention) -> tuple[str, ...]: ...


POLICIES: Registry[Policy] = Registry("policy")


@POLICIES.register("deterministic")
class Deterministic:
    """One pseudonym per entity, corpus-wide.

    The policy the stability requirement forces, and — per ENISA — the one that permits linkage
    between records. Every downstream linkage and frequency attack is defined against it.
    """

    name = "deterministic"

    def scope_key(self, entity_key: str, mention: Mention) -> tuple[str, ...]:
        return (entity_key,)


@POLICIES.register("document")
class DocumentRandomised:
    """One pseudonym per entity per document; different documents disagree.

    Cross-scope drift is the specified behaviour here, not a defect — the stability metrics label
    it accordingly.
    """

    name = "document"

    def scope_key(self, entity_key: str, mention: Mention) -> tuple[str, ...]:
        return (entity_key, mention.doc_id)


@POLICIES.register("full")
class FullyRandomised:
    """A fresh pseudonym for every mention.

    Best protection, no linkability at all, and the stability metrics are meaningless by
    construction — which is the point of including it as a bound.
    """

    name = "full"

    def scope_key(self, entity_key: str, mention: Mention) -> tuple[str, ...]:
        return (entity_key, mention.doc_id, mention.mention_id)
