"""Backend selection.

Adding a backend is a module here plus a name in the config file -- never a change to the
action layer.
"""

from __future__ import annotations

from use_computer.backends.base import Backend, BackendNotAvailableError, require
from use_computer.config import BackendProfile
from use_computer.errors import ConfigError

__all__ = ["Backend", "BackendNotAvailableError", "create_backend", "require"]


def create_backend(profile: BackendProfile) -> Backend:
    """Construct the backend a profile names. The module is imported only when selected."""
    if profile.backend == "local":
        from use_computer.backends.local import LocalBackend

        return LocalBackend(allow_local=profile.allow_local, scale=profile.scale)
    if profile.backend == "vnc":
        from use_computer.backends.vnc import VNCBackend

        return VNCBackend(
            host=profile.host,
            port=profile.port,
            password=profile.password,
            scale=profile.scale,
        )
    raise ConfigError(f"unknown backend {profile.backend!r} in profile {profile.name!r}")
