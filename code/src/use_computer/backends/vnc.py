"""The VNC backend: drives a remote framebuffer over RFB, through vncdotool.

Opening the connection dominates the cost of a single action, which is why a run performs a
whole batch over one connection. This class holds that connection open until it is closed.
"""

from __future__ import annotations

import contextlib
import tempfile
import time
from pathlib import Path
from typing import Any

from use_computer.actions import MouseButton, ScrollDirection
from use_computer.backends.base import require
from use_computer.compare import Screenshot
from use_computer.coordinates import CoordinateSpace, ScreenInfo
from use_computer.errors import ActionFailedError, ConfigError
from use_computer.keys import VNC_KEYS, KeyCombo

#: RFB button numbers. 4/5 are wheel up/down, 6/7 wheel left/right.
_BUTTONS = {MouseButton.LEFT: 1, MouseButton.MIDDLE: 2, MouseButton.RIGHT: 3}
_WHEEL = {
    ScrollDirection.UP: 4,
    ScrollDirection.DOWN: 5,
    ScrollDirection.LEFT: 6,
    ScrollDirection.RIGHT: 7,
}

DRAG_STEPS = 24
STEP_PAUSE = 0.01


class VNCBackend:
    """Drives a remote screen over RFB."""

    name = "vnc"

    def __init__(
        self,
        *,
        host: str | None,
        port: int = 5900,
        password: str | None = None,
        scale: float | None = None,
        client: Any | None = None,
    ) -> None:
        if client is None and not host:
            raise ConfigError(
                "the vnc backend needs a host: set `host` in the profile, or "
                "USE_COMPUTER_PROFILES__<PROFILE>__HOST."
            )
        self._explicit_scale = scale
        self._screen: ScreenInfo | None = None
        if client is not None:
            self._client = client
            self._api = None
            return
        api = require("vncdotool.api", backend=self.name, extra="vnc")
        self._api = api
        # vncdotool addresses a server as host::port.
        self._client = api.connect(f"{host}::{port}", password=password)

    # --- reporting ---------------------------------------------------------------------------

    def screen_info(self) -> ScreenInfo:
        if self._screen is not None:
            return self._screen
        shot = self.screenshot()
        # A framebuffer has one coordinate space: what is captured is what is clicked.
        self._screen = ScreenInfo(
            width=shot.width,
            height=shot.height,
            screenshot_width=shot.width,
            screenshot_height=shot.height,
            scale=self._explicit_scale if self._explicit_scale is not None else 1.0,
        )
        return self._screen

    def screenshot(self) -> Screenshot:
        with tempfile.TemporaryDirectory(prefix="use-computer-") as tmp:
            path = Path(tmp) / "screen.png"
            self._client.captureScreen(str(path))
            data = path.read_bytes()
        with _open(data) as image:
            width, height = image.size
        return Screenshot(
            data=data, width=width, height=height, space=CoordinateSpace.SCREENSHOT
        )

    # --- acting ------------------------------------------------------------------------------

    def move(self, x: int, y: int) -> None:
        self._client.mouseMove(x, y)

    def click(self, x: int | None, y: int | None, button: MouseButton, count: int) -> None:
        if x is not None and y is not None:
            self.move(x, y)
        number = _BUTTONS[button]
        for index in range(count):
            if index:
                time.sleep(STEP_PAUSE)
            self._client.mousePress(number)

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, button: MouseButton) -> None:
        number = _BUTTONS[button]
        self.move(from_x, from_y)
        self._client.mouseDown(number)
        try:
            for step in range(1, DRAG_STEPS + 1):
                ratio = step / DRAG_STEPS
                self.move(
                    round(from_x + (to_x - from_x) * ratio),
                    round(from_y + (to_y - from_y) * ratio),
                )
                time.sleep(STEP_PAUSE)
        finally:
            self._client.mouseUp(number)

    def scroll(
        self, amount: int, direction: ScrollDirection, x: int | None, y: int | None
    ) -> None:
        if x is not None and y is not None:
            self.move(x, y)
        number = _WHEEL[direction]
        for _ in range(max(1, abs(amount))):
            self._client.mousePress(number)
            time.sleep(STEP_PAUSE)

    def type_text(self, text: str, rate: float) -> None:
        # vncdotool grew a `type` helper; where it is missing, one keyPress per character does
        # the same thing at the same rate.
        typer = getattr(self._client, "type", None)
        if callable(typer) and not rate:
            typer(text)
            return
        for char in text:
            self._client.keyPress(_char_key(char))
            if rate:
                time.sleep(rate)

    def key(self, combo: KeyCombo) -> None:
        parts = [_vnc_name(name) for name in combo.modifiers]
        parts.append(_vnc_name(combo.key))
        # vncdotool spells a combination with dashes: ctrl-shift-t.
        self._client.keyPress("-".join(parts))

    def close(self) -> None:
        # The connection may already be gone; closing must never mask the real failure.
        with contextlib.suppress(Exception):
            self._client.disconnect()


def _open(data: bytes) -> Any:
    import io

    from PIL import Image

    return Image.open(io.BytesIO(data))


def _vnc_name(name: str) -> str:
    mapped = VNC_KEYS.get(name)
    if mapped is not None:
        return mapped
    if len(name) == 1:
        return _char_key(name)
    raise ActionFailedError(f"the vnc backend has no mapping for key {name!r}")


#: Characters vncdotool spells by X11 keysym name rather than literally.
_CHAR_KEYS = {
    " ": "space",
    "-": "minus",
    "+": "plus",
    "=": "equal",
    ".": "period",
    ",": "comma",
    "\t": "tab",
    "\n": "return",
}


def _char_key(char: str) -> str:
    return _CHAR_KEYS.get(char, char)
