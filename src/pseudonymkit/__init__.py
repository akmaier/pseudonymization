"""pseudonymkit — composable text pseudonymisation and its evaluation.

The package exists to make the *pseudonymisation function and policy* an experimental variable
rather than a fixed implementation detail.  Five axes are pluggable strategies looked up by name:

===============  ==========================================  =========================
axis             levels                                      module
===============  ==========================================  =========================
key normaliser   N0 - N4                                     :mod:`pseudonymkit.keys`
A policy         deterministic, document, full               :mod:`pseudonymkit.policies`
B technique      counter, table, hash, hmac, aes_siv         :mod:`pseudonymkit.techniques`
C surrogate      tag, realistic, attribute_matched           :mod:`pseudonymkit.surrogates`
D detector       gold, plus adapters, plus combinators       :mod:`pseudonymkit.detectors`
===============  ==========================================  =========================

A cell of the design is a dict of names; :class:`pseudonymkit.engine.Pseudonymiser` composes them.
"""

from .domain import Assignment, Corpus, Document, Mention, PseudonymMapping, Span
from .engine import Pseudonymiser, PseudonymisedCorpus, PseudonymisedDocument
from .keys import NORMALISERS
from .policies import POLICIES
from .surrogates import SURROGATES
from .techniques import TECHNIQUES

__version__ = "0.1.0"

__all__ = [
    "Span", "Mention", "Document", "Corpus", "Assignment", "PseudonymMapping",
    "Pseudonymiser", "PseudonymisedDocument", "PseudonymisedCorpus",
    "NORMALISERS", "POLICIES", "TECHNIQUES", "SURROGATES",
    "__version__",
]
