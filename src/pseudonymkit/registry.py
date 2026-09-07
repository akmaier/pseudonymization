"""A tiny name -> factory registry.

Every axis of the study (key normaliser, policy, technique, surrogate form, detector,
combination rule) is a pluggable strategy looked up by name.  That is what lets a whole
experimental cell be described by a small dict of strings and reconstructed exactly, which
in turn is what makes the factorial cheap to run and cheap to reproduce.

Third-party code extends an axis by registering into the same registry; nothing in this
package needs to be edited to add a technique or a detector.
"""

from __future__ import annotations

from typing import Callable, Generic, Iterator, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """Maps a stable string name to a factory for that strategy."""

    def __init__(self, axis: str) -> None:
        self._axis = axis
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator: register a factory under ``name``."""

        def decorator(factory: Callable[..., T]) -> Callable[..., T]:
            if name in self._factories:
                raise ValueError(f"{self._axis}: {name!r} is already registered")
            self._factories[name] = factory
            return factory

        return decorator

    def create(self, name: str, **kwargs: object) -> T:
        """Instantiate the strategy registered under ``name``."""
        try:
            factory = self._factories[name]
        except KeyError:
            raise KeyError(
                f"unknown {self._axis} {name!r}; available: {', '.join(sorted(self._factories))}"
            ) from None
        return factory(**kwargs)

    def names(self) -> list[str]:
        """All registered names, sorted — the levels of this axis."""
        return sorted(self._factories)

    def __contains__(self, name: object) -> bool:
        return name in self._factories

    def __iter__(self) -> Iterator[str]:
        return iter(self.names())

    def __len__(self) -> int:
        return len(self._factories)
