"""The accessibility Protocol, and the lazy import every provider constructs itself through.

This is a second Protocol beside :class:`~use_computer.backends.base.Backend` because the split
is different: the `local` backend has three platform implementations of this one, and the `vnc`
backend can have none at all -- RFB carries pixels and nothing else.

A provider is chosen by the *running platform*, never by configuration. A profile does not get to
claim macOS accessibility on Linux.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Protocol, runtime_checkable

from use_computer.errors import UITreeUnavailableError
from use_computer.tree import TreeScope, UINode, WindowInfo


@runtime_checkable
class AccessibilityProvider(Protocol):
    """What every platform provider implements. The fake provider in tests satisfies it too."""

    name: str

    def windows(self) -> list[WindowInfo]:
        """List what is open: the cheapest question an agent can ask.

        A shallow read, and it must tolerate an application that will not answer on the bus --
        it loses that application, never the list.
        """

    def snapshot(self, scope: TreeScope, depth: int) -> UINode:
        """Read the tree, *unpruned*.

        Pruning and the node budget are applied above this boundary, so ids stay addressable
        and the policy stays testable without a desktop.

        Raises:
            PermissionDeniedError: the OS refused the accessibility permission.
        """

    def perform(self, node_id: str, action: str, value: str | None) -> bool:
        """Operate an element through the platform API.

        Returns whether the platform actually carried it out. A boolean rather than ``None``
        because several of these APIs report failure by returning false rather than raising --
        a provider that only caught exceptions would report success for an action that did
        nothing at all. ``False`` is what makes ``--via auto`` fall back to a coordinate click.
        """

    def close(self) -> None:
        """Release whatever the provider holds."""


def require(module: str, *, extra: str, system: str | None = None) -> ModuleType:
    """Import a platform binding, or say exactly what to install.

    Called inside a provider's constructor, never at module import: otherwise
    ``use-computer --help`` stops working on a machine without the extra.

    Raises:
        UITreeUnavailableError: naming the extra and, where one is needed, the system package.
    """
    try:
        return import_module(module)
    except ImportError as exc:
        raise UITreeUnavailableError(
            f"reading the UI tree needs {module!r}, which is not installed.",
            extra=extra,
            system=system,
        ) from exc


__all__ = ["AccessibilityProvider", "UITreeUnavailableError", "require"]
