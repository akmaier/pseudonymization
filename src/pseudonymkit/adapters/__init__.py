"""Corpus adapters: source formats in, :mod:`pseudonymkit.domain` out.

Everything corpus-specific lives here, so adding a corpus never changes the engine, the metrics or
the attacks.
"""

from . import tab

__all__ = ["tab"]
