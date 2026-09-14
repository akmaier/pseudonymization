"""The harmonised entity taxonomy, and every source's route into it.

``experiment_plan.md`` §10 adopts **TAB's eight categories** — PERSON, LOC, ORG, DATETIME, CODE,
DEMOGRAPHIC, QUANTITY, MISC — rather than inventing a set, because TAB's were designed for
*concealing an identity* rather than for hitting a class.  Every gold layer and every detector routes
into them, and the source label survives verbatim in :attr:`~pseudonymkit.domain.Span.type_src`, so
the mapping is reversible and every deviation is countable.

Three properties of this module matter more than the tables:

**It is applied at scoring time, never at detection time.**  The detector cache on the cluster is
already written — 89 distinct labels over 1.6 million spans — and rewriting it would invalidate
records that cost model time to produce.  Harmonisation is therefore a *read* transformation:
:meth:`Harmoniser.spans` maps a cached record's labels on the way into a metric, and the cache stays
as it is.

**It reads the raw label from ``type_src or type``.**  A record written before this module existed
carries the model's raw string in ``type`` and nothing in ``type_src`` (§12.2); a record written by
one of the classical detectors carries the harmonised name in ``type`` and the raw one in
``type_src``.  Reading ``type_src or type`` handles both, and makes harmonisation idempotent: running
it twice cannot corrupt a label or double-count an unmapped one within one pass.

**Unmapped labels are counted, not discarded.**  §10: *"a detector inventing categories is a finding
about that detector"*.  Anything with no route into the eight becomes MISC **and increments
:attr:`Harmoniser.unmapped`**, which is what makes the finding reportable.  Note the distinction from
a label mapped to MISC deliberately — ``OTHERPHI`` for instance — which is a translation, not an
invention, and is not counted.

PIIBench's ``LABEL_NORM`` (187 source labels over 54 canonical types) was inspected and **not
adopted** (§10): it is a superset built for ten corpora this study does not use, its canonical set
carries BIO-prefixed duplicates, and routing through it would add a translation step without adding a
distinction any measurement here consumes.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import Iterable, Mapping, Sequence

from .domain import Document, Span

__all__ = [
    "HARMONISED",
    "PERSON",
    "LOC",
    "ORG",
    "DATETIME",
    "CODE",
    "DEMOGRAPHIC",
    "QUANTITY",
    "MISC",
    "SOURCES",
    "TaxonomyMap",
    "Harmoniser",
    "harmonise",
    "normalise_label",
    "source_for",
]

PERSON, LOC, ORG, DATETIME = "PERSON", "LOC", "ORG", "DATETIME"
CODE, DEMOGRAPHIC, QUANTITY, MISC = "CODE", "DEMOGRAPHIC", "QUANTITY", "MISC"

HARMONISED: tuple[str, ...] = (
    PERSON,
    LOC,
    ORG,
    DATETIME,
    CODE,
    DEMOGRAPHIC,
    QUANTITY,
    MISC,
)
"""TAB's eight categories, in the order §10 lists them."""

_BIO_RE = re.compile(r"^(?:[BIESUL])[-_](?=.)")
_SEPARATORS_RE = re.compile(r"[\s\-]+")


def normalise_label(label: str) -> str:
    """Put a raw label into the shape the tables are keyed by.

    Strips a BIO/BIOES prefix, uppercases, and collapses spaces and hyphens to underscores, so
    ``"B-PER"``, ``"per"`` and ``"date time"`` reach the table as ``PER``, ``PER`` and ``DATE_TIME``.
    Aggregation strategies differ between transformers pipelines and some emit the prefix, so this is
    normalisation rather than tolerance of sloppiness.
    """
    text = _BIO_RE.sub("", (label or "").strip())
    return _SEPARATORS_RE.sub("_", text).strip("_").upper()


def _identity(labels: Iterable[str]) -> dict[str, str]:
    return {normalise_label(x): x for x in labels}


def _route(**groups: str) -> dict[str, str]:
    """``_route(PERSON="PATIENT STAFF", ORG="HOSP PATORG")`` -> a label table.

    Written this way so a mapping in §10 reads the same in the code as it does in the plan's table,
    where the routes are given as ``PATIENT·STAFF → PERSON``.
    """
    table: dict[str, str] = {}
    for target, sources in groups.items():
        for source in sources.split():
            table[normalise_label(source)] = target
    return table


_HARMONISED_IDENTITY = _identity(HARMONISED)

# --------------------------------------------------------------------------------- source tables

_TAB = _route(
    PERSON="PERSON",
    LOC="LOC",
    ORG="ORG",
    DATETIME="DATETIME",
    CODE="CODE",
    QUANTITY="QUANTITY",
    DEMOGRAPHIC="DEM DEMOGRAPHIC",
    MISC="MISC",
)
"""TAB gold: its own eight, identity.  ``DEM`` is TAB's spelling of DEMOGRAPHIC."""

_ONTONOTES = _route(
    PERSON="PERSON",
    LOC="GPE LOC FAC",
    ORG="ORG",
    DATETIME="DATE TIME",
    DEMOGRAPHIC="NORP",
    QUANTITY="MONEY PERCENT QUANTITY CARDINAL ORDINAL",
    MISC="PRODUCT EVENT WORK_OF_ART LAW LANGUAGE",
)
"""OntoNotes' 18 NE types.  The five in the MISC row are §10's *"rest → MISC"*, enumerated here so
they are recorded as translated rather than counted as inventions."""

_ENRON = _route(PERSON="PERSON", CODE="EMAIL")
"""Enron gold, which our own adapter derives from message headers: PERSON and EMAIL only.  There is
therefore **no LOC gold on Enron**, and §8.1's PERSON-and-LOCATION-separately requirement cannot be
met there (§12.1)."""

_CARDIODE = _route(
    PERSON="PER",
    LOC="LOC ADDR PLZ",
    ORG="ORG",
    DATETIME="PSEUDO DATE DAY MONTH YEAR",
    CODE="PHONE OTHER OTHERG OTH II",
    DEMOGRAPHIC="TITLE SALUTE",
)
"""CARDIO:DE gold, in two layers.

As released the corpus's only identifier annotation is the ``<[Pseudo] …>`` date marker, exposed by
the adapter with ``type_src="Pseudo"``.  The condition-A fill
(:mod:`pseudonymkit.adapters.cardiode_fill`) adds the other fifteen: it replaces the IOB tag runs
left in the running text and records ``type_src`` as the tag, so ``PER``, ``TITLE``, ``ADDR`` and the
rest arrive here and need routes or they would be counted as inventions.

Two of these are judgements rather than translations and are marked as such.  ``TITLE`` (*Dr.*,
*Prof. Dr. med.*) and ``SALUTE`` (*Herr*, *Frau*) go to **DEMOGRAPHIC**: neither names a person, both
carry attributes of one — academic rank and gender — which is what TAB's DEM category is for.
``PLZ`` and ``ADDR`` go to **LOC** rather than CODE: a postcode locates rather than identifies, and
TAB routes address components to LOC."""

_LLM = _route(
    PERSON="PERSON",
    LOC="LOC",
    ORG="ORG",
    DATETIME="DATETIME",
    CODE="EMAIL PHONE ID",
    DEMOGRAPHIC="PROFESSION",
)
"""The LLM prompt's eight (:data:`pseudonymkit.detectors.prompting.DEFAULT_TYPES`).  Structured
identifiers collapse into CODE, which is TAB's own category for them; PROFESSION is an attribute
rather than an identifier and follows TAB into DEMOGRAPHIC."""

_PRIVACY_TAGGER = _route(
    PERSON="FEMALE MALE FAMILY",
    LOC="STREET STREETNO CITY ZIP",
    ORG="ORG",
    DATETIME="DATE",
    CODE="USER PASS UFID EMAIL URL PHONE",
)
"""CodEAlltag's ``privacy_tagger``, fifteen labels.  FEMALE and MALE both become PERSON: nothing
downstream consumes the distinction (§10)."""

_OBI_DEID = _route(
    PERSON="PATIENT STAFF",
    ORG="HOSP PATORG",
    CODE="EMAIL ID PHONE",
    DEMOGRAPHIC="AGE",
    DATETIME="DATE",
    LOC="LOC",
    MISC="OTHERPHI",
)
"""``obi/deid_roberta_i2b2``, eleven labels.  OTHERPHI routes to MISC *deliberately* — it is the
model's own residual class — so it is a translation and is not counted as an invented category."""

_STANFORD_DEID = _route(
    PERSON="PATIENT HCW",
    ORG="HOSPITAL VENDOR",
    CODE="ID PHONE",
    DATETIME="DATE",
)
"""``StanfordAIMI/stanford-deidentifier-base``, seven labels."""

_XLM_NER_HRL = _route(PERSON="PER", DATETIME="DATE", LOC="LOC", ORG="ORG")
"""``Davlan/xlm-roberta-large-ner-hrl``, four labels."""

_GLINER = dict(_HARMONISED_IDENTITY)
"""GLiNER's label set is ours: it is prompted with the eight harmonised names directly (§10), so the
table is the identity and any other label it returns is an invention and is counted as one."""

_PRESIDIO = _route(
    PERSON="PERSON",
    LOC="LOCATION",
    ORG="ORGANIZATION",
    DATETIME="DATE_TIME",
    DEMOGRAPHIC="NRP",
    CODE=(
        "EMAIL_ADDRESS PHONE_NUMBER IBAN_CODE CREDIT_CARD CRYPTO IP_ADDRESS URL MEDICAL_LICENSE "
        "US_BANK_NUMBER US_DRIVER_LICENSE US_ITIN US_PASSPORT US_SSN UK_NHS UK_NINO "
        "ES_NIF ES_NIE IT_FISCAL_CODE IT_DRIVER_LICENSE IT_VAT_CODE IT_PASSPORT IT_IDENTITY_CARD "
        "PL_PESEL SG_NRIC_FIN SG_UEN AU_ABN AU_ACN AU_TFN AU_MEDICARE "
        "IN_PAN IN_AADHAAR IN_VEHICLE_REGISTRATION IN_VOTER IN_PASSPORT "
        "FI_PERSONAL_IDENTITY_CODE"
    ),
)
"""Presidio's predefined recognisers.

**§10's table does not carry a row for Presidio**, although §7 lists it as a level of axis D and §10
requires every detector to route into the eight.  The table below follows §10's three stated
judgements rather than inventing new ones: structured identifiers — every national identity number,
bank, card, contact and network identifier — go to CODE; ``NRP`` (nationality, religious or political
group) is TAB's DEM and goes to DEMOGRAPHIC; the four named-entity classes are identity.  Any
recogniser not listed here falls through to MISC **and is counted**, which is how a missing entry
announces itself rather than hiding."""

SOURCES: Mapping[str, Mapping[str, str]] = {
    "tab": _TAB,
    "ontonotes": _ONTONOTES,
    "enron": _ENRON,
    "cardiode": _CARDIODE,
    "llm": _LLM,
    "gliner": _GLINER,
    "presidio": _PRESIDIO,
    "privacy_tagger": _PRIVACY_TAGGER,
    "obi/deid_roberta_i2b2": _OBI_DEID,
    "StanfordAIMI/stanford-deidentifier-base": _STANFORD_DEID,
    "Davlan/xlm-roberta-large-ner-hrl": _XLM_NER_HRL,
}
"""Source name -> its label table.  The model-backed sources are keyed by their **model id**, which
is what a result row records, so a row can be traced back to the mapping that produced it."""

_DETECTOR_PREFIXES: tuple[tuple[str, str], ...] = (
    ("llm:", "llm"),
    ("local:", "llm"),
    ("gliner:", "gliner"),
    ("presidio", "presidio"),
    ("privacy_tagger", "privacy_tagger"),
)
"""How a detector *name* resolves to a source table.  ``llm:`` and ``local:`` are the gateway and the
vLLM backend of one prompt (:mod:`pseudonymkit.detectors.prompting`), so they share a table."""


def source_for(detector: str, corpus: str | None = None) -> str:
    """The source table a detector's output should be read through.

    ``gold`` has no table of its own: the gold layer's labels are the corpus's, so the corpus name is
    required and a :class:`KeyError` is raised without one rather than a silent guess.

    An unrecognised detector resolves to itself, so a detector registered by third-party code routes
    through :data:`SOURCES` under its own name if it has an entry there, and otherwise through the
    empty table — where every label is unmapped and counted, which is the honest default.
    """
    if detector == "gold" or detector.startswith("gold:"):
        corpus = corpus or detector.partition(":")[2]
        if not corpus:
            raise KeyError("gold spans carry the corpus's own labels; pass corpus=")
        return corpus
    for prefix, source in _DETECTOR_PREFIXES:
        if detector == prefix or detector.startswith(prefix):
            return source
    if detector.startswith("hf:"):
        return detector[3:]
    return detector


def harmonise(label: str, source: str) -> tuple[str, bool]:
    """Route one raw label into the eight.  Returns ``(harmonised, was_mapped)``.

    ``was_mapped`` is ``False`` only when the label had **no route at all** and fell through to MISC.
    A label the table sends to MISC on purpose — ``OTHERPHI``, OntoNotes' ``LAW`` — comes back
    ``True``, because it was translated rather than invented.
    """
    key = normalise_label(label)
    table = SOURCES.get(source, {})
    mapped = table.get(key)
    if mapped is not None:
        return mapped, True
    already = _HARMONISED_IDENTITY.get(key)
    if already is not None:
        return already, True
    return MISC, False


@dataclass(frozen=True, slots=True)
class TaxonomyMap:
    """One source's table, bound to its name — a value object for a results row."""

    source: str
    table: Mapping[str, str]

    @classmethod
    def for_source(cls, source: str) -> TaxonomyMap:
        return cls(source, SOURCES.get(source, {}))

    def __call__(self, label: str) -> tuple[str, bool]:
        return harmonise(label, self.source)

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(sorted(self.table))


class Harmoniser:
    """Applies the taxonomy to spans and **counts what had no route**.

    Stateful by design, like the engine: the unmapped tally is the measurement.  One instance per
    scoring pass, and its :meth:`report` goes into the results row beside the detection numbers, so a
    detector that invented ``FILENAME``, ``GENE``, ``COPYRIGHT`` or a ``<[PSEUDO] …>`` marker string
    is visible as such rather than silently folded into MISC.
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self._map = TaxonomyMap.for_source(source)
        self._unmapped: Counter[str] = Counter()
        self._seen = 0
        self._routed = 0

    # ------------------------------------------------------------------ mapping

    def label(self, raw: str) -> str:
        """Harmonise one raw label, counting it if it had no route."""
        self._seen += 1
        mapped, was_mapped = self._map(raw)
        if was_mapped:
            self._routed += 1
        else:
            self._unmapped[normalise_label(raw)] += 1
        return mapped

    def span(self, span: Span) -> Span:
        """Return ``span`` with a harmonised ``type`` and the raw label kept in ``type_src``.

        The raw label is taken from ``type_src or type``: a cached record written before this module
        existed has the model's string in ``type``, and one written by a classical detector has it in
        ``type_src``.  Both therefore harmonise correctly, and a second application is a no-op.
        """
        raw = span.type_src or span.type
        return Span(
            start=span.start,
            end=span.end,
            text=span.text,
            type=self.label(raw),
            type_src=raw,
            source=span.source,
            score=span.score,
        )

    def spans(self, spans: Iterable[Span]) -> tuple[Span, ...]:
        return tuple(self.span(s) for s in spans)

    def document(self, document: Document) -> Document:
        """A copy whose mentions carry harmonised types.  Offsets and text are untouched."""
        return document.with_mentions(
            tuple(replace(m, span=self.span(m.span)) for m in document.mentions)
        )

    # ------------------------------------------------------------------ reporting

    @property
    def unmapped(self) -> Mapping[str, int]:
        """Raw label -> how often it had no route into the eight."""
        return dict(self._unmapped)

    @property
    def seen(self) -> int:
        return self._seen

    @property
    def unmapped_spans(self) -> int:
        return int(sum(self._unmapped.values()))

    @property
    def unmapped_rate(self) -> float:
        return self.unmapped_spans / self._seen if self._seen else 0.0

    def report(self) -> dict[str, object]:
        """The row §10 asks for: how much of this detector's output the taxonomy did not recognise."""
        return {
            "source": self.source,
            "spans": self._seen,
            "routed": self._routed,
            "unmapped_spans": self.unmapped_spans,
            "unmapped_labels": len(self._unmapped),
            "unmapped_rate": self.unmapped_rate,
            "unmapped": dict(self._unmapped.most_common()),
        }

    def merge(self, other: Harmoniser) -> None:
        """Fold another pass's tally in — for aggregating over corpora or shards."""
        if other.source != self.source:
            raise ValueError(f"different sources: {self.source!r} vs {other.source!r}")
        self._unmapped.update(other._unmapped)
        self._seen += other._seen
        self._routed += other._routed


def harmonise_spans(
    spans: Sequence[Span], detector: str, corpus: str | None = None
) -> tuple[tuple[Span, ...], Harmoniser]:
    """Convenience: harmonise one detector's spans and hand back the tally with them.

    The tally is returned rather than discarded because §10 requires the unmapped count to be
    reported; a caller that throws it away is dropping a result.
    """
    harmoniser = Harmoniser(source_for(detector, corpus))
    return harmoniser.spans(spans), harmoniser
