"""The backend Protocol, and the lazy-import helper every backend constructs itself through.

Two interchangeable backends sit behind this interface. Coordinates crossing it are always in
*actuation* units -- conversion happens above. A backend's third-party dependency is imported
inside its constructor, never at module import, so the package installs and `--help` works with
no extras present.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Protocol, runtime_checkable

from use_computer.actions import MouseButton, ScrollDirection
from use_computer.compare import Screenshot
from use_computer.coordinates import ScreenInfo
from use_computer.errors import BackendNotAvailableError
from use_computer.keys import KeyCombo


@runtime_checkable
class Backend(Protocol):
    """What every backend implements. The fake backend used in tests satisfies it too."""

    name: str

    def screen_info(self) -> ScreenInfo:
        """Report this backend's own coordinate spaces and screen size."""

    def screenshot(self) -> Screenshot:
        """Capture the current screen."""

    def move(self, x: int, y: int) -> None: ...

    def click(self, x: int | None, y: int | None, button: MouseButton, count: int) -> None: ...

    def drag(
        self, from_x: int, from_y: int, to_x: int, to_y: int, button: MouseButton
    ) -> None: ...

    def scroll(
        self, amount: int, direction: ScrollDirection, x: int | None, y: int | None
    ) -> None: ...

    def type_text(self, text: str, rate: float) -> None: ...

    def key(self, combo: KeyCombo) -> None: ...

    def close(self) -> None:
        """Release whatever the backend holds. Called even when an action failed."""


def require(module: str, *, backend: str, extra: str) -> ModuleType:
    """Import an optional dependency, or say exactly what to install.

    Raises:
        BackendNotAvailableError: naming the extra, not the import error.
    """
    try:
        return import_module(module)
    except ImportError as exc:
        raise BackendNotAvailableError(backend=backend, extra=extra, missing=module) from exc


__all__ = ["Backend", "BackendNotAvailableError", "require"]
