"""pseudonymkit — composable text pseudonymisation and its evaluation.

The package exists to make the *pseudonymisation function and policy* an experimental variable
rather than a fixed implementation detail.  The axes are pluggable strategies looked up by name:

===============  ==========================================  ================================
axis             levels                                      module
===============  ==========================================  ================================
key normaliser   N0 - N4                                     :mod:`pseudonymkit.keys`
policy           deterministic, document, full               :mod:`pseudonymkit.policies`
technique        counter, table, hash, hmac, aes_siv         :mod:`pseudonymkit.techniques`
surrogate        tag, placeholder, realistic,                 :mod:`pseudonymkit.surrogates`
                 attribute_matched
D detector       gold, presidio, gliner, finetuned,          :mod:`pseudonymkit.detectors`
                 privacy_tagger, llm, plus combinators
===============  ==========================================  ================================

``experiment_plan.md`` §7 fixes those axes into **three conditions** — A full data, B pseudonymised,
C de-identified — and :mod:`pseudonymkit.conditions` is where that configuration lives.  The axes
themselves stay, so a fourth condition is a configuration rather than a rewrite.

:mod:`pseudonymkit.taxonomy` routes every gold layer and every detector into the harmonised eight
(§10), at scoring time, counting whatever had no route.
"""

from .conditions import SPECS as CONDITIONS
from .conditions import ConditionSpec, Unmodified
from .conditions import build as build_condition
from .domain import Assignment, Corpus, Document, Mention, PseudonymMapping, Span
from .engine import (
    OffsetMap,
    PseudonymisedCorpus,
    PseudonymisedDocument,
    Pseudonymiser,
    replacements,
)
from .keys import NORMALISERS
from .policies import POLICIES
from .surrogates import SURROGATES
from .taxonomy import HARMONISED, Harmoniser
from .techniques import TECHNIQUES

__version__ = "0.1.0"

__all__ = [
    "Span", "Mention", "Document", "Corpus", "Assignment", "PseudonymMapping",
    "Pseudonymiser", "PseudonymisedDocument", "PseudonymisedCorpus",
    "OffsetMap", "replacements",
    "NORMALISERS", "POLICIES", "TECHNIQUES", "SURROGATES",
    "CONDITIONS", "ConditionSpec", "Unmodified", "build_condition",
    "HARMONISED", "Harmoniser",
    "__version__",
]
