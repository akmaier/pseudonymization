"""Corpus adapters: source formats in, :mod:`pseudonymkit.domain` out.

Everything corpus-specific lives here, so adding a corpus never changes the engine, the metrics or
the attacks.  Adapters also record how their annotations were obtained -- TAB's and OntoNotes' are
human gold, Enron's are derived from message headers, CodEAlltag's release carries none -- so a
result can never silently conflate the two.
"""

from . import cardiode, codealltag, enron, ontonotes, tab

__all__ = ["cardiode", "codealltag", "enron", "ontonotes", "tab"]
