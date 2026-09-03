"""Exception hierarchy.

Every error carries what the caller needs to fix it: the extra to install, the OS permission
to grant, the config key to set. A message that only says "failed" costs a debugging session.
"""

from __future__ import annotations


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
