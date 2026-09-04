"""Exception hierarchy.

Every error carries what the caller needs to fix it: the extra to install, the OS permission
to grant, the config key to set. A message that only says "failed" costs a debugging session.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # errors is imported by coordinates, which tree imports -- annotations only.
    from use_computer.compare import Screenshot
    from use_computer.tree import UINode


class UseComputerError(Exception):
    """Base class for every error raised by use-computer."""


class BackendNotAvailableError(UseComputerError):
    """A backend's optional dependency is not installed."""

    def __init__(self, backend: str, extra: str, missing: str) -> None:
        self.backend = backend
        self.extra = extra
        self.missing = missing
        super().__init__(
            f"backend {backend!r} needs {missing!r}, which is not installed. "
            f'Install it with: pip install "use-computer-cli[{extra}]"'
        )


class PermissionDeniedError(UseComputerError):
    """The host denied a permission the backend needs.

    Without this error the underlying libraries typically do nothing at all, and a click that
    never happened is reported as a click that worked.
    """

    def __init__(self, permission: str, hint: str) -> None:
        self.permission = permission
        self.hint = hint
        super().__init__(f"{permission} permission denied. {hint}")


class CoordinateSpaceError(UseComputerError):
    """A coordinate cannot be converted because the scale is unknown or inconsistent."""


class KeySyntaxError(UseComputerError):
    """A key combination could not be parsed."""


class ConfigError(UseComputerError):
    """Configuration is missing, malformed, or forbids the requested operation."""


class ActionFailedError(UseComputerError):
    """The backend failed to perform an action."""


class UITreeUnavailableError(UseComputerError):
    """No accessibility provider can be built here.

    Names both halves of the fix, because on Linux the Python binding alone is not enough: the
    AT-SPI bindings ship as a distro package and pip cannot finish the job.
    """

    def __init__(self, reason: str, *, extra: str | None = None, system: str | None = None) -> None:
        self.reason = reason
        self.extra = extra
        self.system = system
        parts = [reason]
        if extra:
            parts.append(f'Install it with: pip install "use-computer-cli[{extra}]"')
        if system:
            parts.append(f"On this platform you also need the system package: {system}")
        super().__init__(" ".join(parts))


class NodeNotFoundError(UseComputerError):
    """A selector matched nothing.

    Carries the fallback screenshot when one was taken: a selector that matched nothing is
    exactly the signal for the calling agent to switch to vision.
    """

    def __init__(self, description: str, *, screenshot: Screenshot | None = None) -> None:
        self.description = description
        self.screenshot = screenshot
        hint = " A screenshot was captured; locate it visually instead." if screenshot else ""
        super().__init__(f"no node matches {description}.{hint}")


class AmbiguousNodeError(UseComputerError):
    """A selector matched more than one node.

    Never resolved by picking the first: two buttons named "OK" in two dialogs is the ordinary
    case, and a silent choice fails a hundred runs later in a way nobody can reproduce. The
    candidates travel on the error as objects, so the CLI renders them and the API hands them over.
    """

    def __init__(self, description: str, candidates: Sequence[UINode]) -> None:
        self.description = description
        self.candidates = tuple(candidates)
        super().__init__(
            f"{len(self.candidates)} nodes match {description}; "
            "narrow the selector or pass --nth"
        )


class ActionNotSupportedError(UseComputerError):
    """The matched node does not support the requested action."""

    def __init__(self, action: str, node: str, supported: tuple[str, ...]) -> None:
        self.action = action
        self.node = node
        self.supported = supported
        offer = ", ".join(supported) if supported else "none"
        super().__init__(f"{node} does not support {action!r}. It supports: {offer}")
