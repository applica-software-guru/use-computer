"""Choosing an accessibility provider.

By the *running platform*, never by configuration: a profile does not get to claim macOS
accessibility on Linux. And only for a backend that can have one at all -- RFB carries pixels,
so a vnc profile gets a clear error and the calling agent uses coordinates.
"""

from __future__ import annotations

import sys

from use_computer.accessibility.base import AccessibilityProvider, require
from use_computer.errors import UITreeUnavailableError

#: Backends that drive a display this machine can also inspect. Everything else is remote
#: pixels, and no accessibility API reaches across RFB.
LOCAL_BACKENDS = frozenset({"local"})


def create_provider(backend: str) -> AccessibilityProvider:
    """Build the provider for this platform, or say why there cannot be one.

    Raises:
        UITreeUnavailableError: wrong backend, unsupported platform, or a missing binding.
        PermissionDeniedError: the OS refused the accessibility permission.
    """
    if backend not in LOCAL_BACKENDS:
        raise UITreeUnavailableError(
            f"the {backend!r} backend drives a remote framebuffer, which carries pixels and no "
            "accessibility information. Use a screenshot and coordinates instead."
        )

    if sys.platform.startswith("linux"):
        from use_computer.accessibility.atspi import AtspiProvider  # noqa: PLC0415

        return AtspiProvider()
    if sys.platform == "win32":
        from use_computer.accessibility.uia import UiaProvider  # noqa: PLC0415

        return UiaProvider()
    if sys.platform == "darwin":
        from use_computer.accessibility.ax import AxProvider  # noqa: PLC0415

        return AxProvider()

    raise UITreeUnavailableError(
        f"no accessibility provider for platform {sys.platform!r}."
    )


__all__ = ["AccessibilityProvider", "UITreeUnavailableError", "create_provider", "require"]
