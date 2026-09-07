"""Corpus adapters: source formats in, :mod:`pseudonymkit.domain` out.

Everything corpus-specific lives here, so adding a corpus never changes the engine, the metrics or
the attacks.  Adapters also record how their annotations were obtained -- TAB's are human gold,
Enron's are derived from message headers -- so a result can never silently conflate the two.
"""

from . import enron, tab

__all__ = ["enron", "tab"]
