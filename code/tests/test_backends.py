"""Backends: one Protocol, optional extras, and an explicit opt-in for the local one."""

from __future__ import annotations

import pytest
from PIL import Image

from tests.fake_backend import FakeBackend
from use_computer.actions import MouseButton, ScrollDirection
from use_computer.backends import create_backend
from use_computer.backends.base import Backend, require
from use_computer.backends.vnc import VNCBackend
from use_computer.config import BackendProfile
from use_computer.errors import BackendNotAvailableError, ConfigError
from use_computer.keys import parse_combo


def test_the_fake_backend_satisfies_the_protocol() -> None:
    assert isinstance(FakeBackend(), Backend)


def test_a_missing_extra_names_what_to_install() -> None:
    with pytest.raises(BackendNotAvailableError) as excinfo:
        require("no_such_module_at_all", backend="vnc", extra="vnc")
    message = str(excinfo.value)
    assert 'use-computer-cli[vnc]' in message


def test_the_local_backend_refuses_without_an_explicit_opt_in() -> None:
    # This backend types on the user's own keyboard. Off by default is the whole point.
    with pytest.raises(ConfigError) as excinfo:
        create_backend(BackendProfile(name="laptop", backend="local"))
    assert "allow-local" in str(excinfo.value)


def test_the_vnc_backend_requires_a_host() -> None:
    with pytest.raises((ConfigError, BackendNotAvailableError)):
        create_backend(BackendProfile(name="staging", backend="vnc"))


def test_importing_a_backend_module_needs_no_extras() -> None:
    # The dependency is imported inside the constructor, so `--help` works with nothing
    # installed.
    import use_computer.backends.local  # noqa: F401
    import use_computer.backends.vnc  # noqa: F401


def test_the_vnc_backend_speaks_rfb_through_an_injected_client() -> None:
    """The client is injectable so the RFB vocabulary is testable without a server."""
    client = _FakeVNCClient()
    backend = VNCBackend(host=None, client=client)

    screen = backend.screen_info()
    # A framebuffer has one coordinate space: what is captured is what is clicked.
    assert screen.scale == 1.0
    assert (screen.width, screen.screenshot_width) == (1024, 1024)

    backend.key(parse_combo("ctrl+shift+t"))
    backend.click(10, 20, MouseButton.RIGHT, 1)
    backend.scroll(2, ScrollDirection.DOWN, None, None)
    backend.drag(0, 0, 10, 10, MouseButton.LEFT)
    backend.close()

    assert client.keys == ["ctrl-shift-t"]
    assert client.presses[0] == 3  # right button
    assert client.presses[1:] == [5, 5]  # wheel down, twice
    assert client.moves[0] == (10, 20)
    assert client.disconnected is True


def test_the_vnc_backend_normalises_the_same_key_names_as_the_local_one() -> None:
    client = _FakeVNCClient()
    backend = VNCBackend(host=None, client=client)
    backend.key(parse_combo("cmd+space"))
    backend.key(parse_combo("enter"))
    assert client.keys == ["super-space", "return"]


def test_typing_paces_itself_one_character_at_a_time() -> None:
    # Typing as fast as the API allows loses characters in real applications.
    client = _FakeVNCClient()
    backend = VNCBackend(host=None, client=client)
    backend.type_text("a b", rate=0.0001)
    assert client.keys == ["a", "space", "b"]


class _FakeVNCClient:
    """The slice of vncdotool's client that this backend uses."""

    def __init__(self) -> None:
        self.keys: list[str] = []
        self.presses: list[int] = []
        self.moves: list[tuple[int, int]] = []
        self.downs: list[int] = []
        self.ups: list[int] = []
        self.disconnected = False

    def captureScreen(self, path: str) -> None:  # noqa: N802 - vncdotool's spelling
        Image.new("RGB", (1024, 768), (0, 0, 0)).save(path)

    def keyPress(self, key: str) -> None:  # noqa: N802 - vncdotool's spelling
        self.keys.append(key)

    def mousePress(self, button: int) -> None:  # noqa: N802 - vncdotool's spelling
        self.presses.append(button)

    def mouseDown(self, button: int) -> None:  # noqa: N802 - vncdotool's spelling
        self.downs.append(button)

    def mouseUp(self, button: int) -> None:  # noqa: N802 - vncdotool's spelling
        self.ups.append(button)

    def mouseMove(self, x: int, y: int) -> None:  # noqa: N802 - vncdotool's spelling
        self.moves.append((x, y))

    def disconnect(self) -> None:
        self.disconnected = True
