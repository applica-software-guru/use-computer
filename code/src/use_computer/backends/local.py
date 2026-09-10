"""The local backend: drives the display of the machine use-computer runs on.

Input via pynput, capture via mss. pyautogui is deliberately not used -- its last release,
0.9.54, dates from 2023.

This backend types on the user's own keyboard and moves their own pointer, so it refuses to act
without an explicit opt-in, and it checks the macOS permissions that would otherwise make every
action silently do nothing.
"""

from __future__ import annotations

import io
import sys
import time
from typing import Any

from use_computer.actions import MouseButton, ScrollDirection
from use_computer.backends.base import require
from use_computer.compare import Screenshot
from use_computer.coordinates import CoordinateSpace, ScreenInfo, derive_scale
from use_computer.errors import ActionFailedError, ConfigError, PermissionDeniedError
from use_computer.keys import PYNPUT_KEYS, KeyCombo

#: Seconds held between press and release, and between the two clicks of a double-click.
PRESS_HOLD = 0.02
DOUBLE_CLICK_GAP = 0.08
#: Steps a drag is interpolated over, so the application sees movement rather than a teleport.
DRAG_STEPS = 24

#: macOS warps the pointer asynchronously: a press posted right after `position` is set can still
#: be stamped with the point the pointer is *leaving*, because the window server has not adopted
#: the new one yet. Measured: with no wait at all the stamped location was still the old one; a
#: two-digit number of milliseconds was consistently enough. This backend is the only place that
#: needs it -- a VNC server adopts a move synchronously with the packet that requested it.
MACOS_MOVE_SETTLE = 0.03


class LocalBackend:
    """Drives this machine's display."""

    name = "local"

    def __init__(self, *, allow_local: bool = False, scale: float | None = None) -> None:
        if not allow_local:
            raise ConfigError(
                "the local backend controls this machine's own keyboard and pointer and is "
                "disabled by default. Enable it explicitly with `allow-local = true` in the "
                "profile, or USE_COMPUTER_ALLOW_LOCAL=1."
            )
        self._explicit_scale = scale
        pynput_mouse = require("pynput.mouse", backend=self.name, extra="local")
        pynput_keyboard = require("pynput.keyboard", backend=self.name, extra="local")
        mss = require("mss", backend=self.name, extra="local")

        _check_macos_permissions()

        self._mouse_module = pynput_mouse
        self._key_module = pynput_keyboard
        self._mouse = pynput_mouse.Controller()
        self._keyboard = pynput_keyboard.Controller()
        self._sct = mss.mss()
        self._screen: ScreenInfo | None = None

    # --- reporting ---------------------------------------------------------------------------

    def screen_info(self) -> ScreenInfo:
        if self._screen is not None:
            return self._screen
        monitor = self._sct.monitors[1]
        width, height = int(monitor["width"]), int(monitor["height"])
        shot = self._sct.grab(monitor)
        # On a HiDPI display mss reports the monitor in points and grabs in pixels. That
        # difference is the whole reason coordinates carry their space.
        scale = self._explicit_scale
        if scale is None:
            scale = derive_scale(width, height, shot.width, shot.height)
        self._screen = ScreenInfo(
            width=width,
            height=height,
            screenshot_width=shot.width,
            screenshot_height=shot.height,
            scale=scale,
        )
        return self._screen

    def screenshot(self) -> Screenshot:
        monitor = self._sct.monitors[1]
        shot = self._sct.grab(monitor)
        image = _to_png(shot)
        return Screenshot(
            data=image,
            width=shot.width,
            height=shot.height,
            space=CoordinateSpace.SCREENSHOT,
        )

    # --- acting ------------------------------------------------------------------------------

    def move(self, x: int, y: int) -> None:
        self._mouse.position = (x, y)

    def click(self, x: int | None, y: int | None, button: MouseButton, count: int) -> None:
        if x is not None and y is not None:
            self.move(x, y)
            _settle_after_move()
        pynput_button = self._button(button)
        for index in range(count):
            if index:
                time.sleep(DOUBLE_CLICK_GAP)
            self._mouse.press(pynput_button)
            time.sleep(PRESS_HOLD)
            self._mouse.release(pynput_button)

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, button: MouseButton) -> None:
        pynput_button = self._button(button)
        self.move(from_x, from_y)
        _settle_after_move()
        self._mouse.press(pynput_button)
        try:
            for step in range(1, DRAG_STEPS + 1):
                ratio = step / DRAG_STEPS
                self.move(
                    round(from_x + (to_x - from_x) * ratio),
                    round(from_y + (to_y - from_y) * ratio),
                )
                time.sleep(PRESS_HOLD / 2)
        finally:
            self._mouse.release(pynput_button)

    def scroll(
        self, amount: int, direction: ScrollDirection, x: int | None, y: int | None
    ) -> None:
        if x is not None and y is not None:
            self.move(x, y)
            _settle_after_move()
        dx, dy = _scroll_vector(amount, direction)
        self._mouse.scroll(dx, dy)

    def type_text(self, text: str, rate: float) -> None:
        # Typing as fast as the API allows loses characters in real applications.
        for char in text:
            self._keyboard.type(char)
            if rate:
                time.sleep(rate)

    def key(self, combo: KeyCombo) -> None:
        modifiers = [self._key(name) for name in combo.modifiers]
        key = self._key(combo.key)
        for modifier in modifiers:
            self._keyboard.press(modifier)
        try:
            self._keyboard.press(key)
            time.sleep(PRESS_HOLD)
            self._keyboard.release(key)
        finally:
            for modifier in reversed(modifiers):
                self._keyboard.release(modifier)

    def close(self) -> None:
        self._sct.close()

    # --- mapping -----------------------------------------------------------------------------

    def _button(self, button: MouseButton) -> Any:
        return getattr(self._mouse_module.Button, button.value)

    def _key(self, name: str) -> Any:
        """Canonical key name -> pynput key. Single characters are themselves."""
        attribute = PYNPUT_KEYS.get(name)
        if attribute is None:
            if len(name) == 1:
                return name
            raise ActionFailedError(f"the local backend has no mapping for key {name!r}")
        return getattr(self._key_module.Key, attribute)


def _settle_after_move() -> None:
    """Give macOS a moment to adopt a pointer warp before the next event is stamped with it.

    Only macOS needs this -- BUG-017. `sys.platform` rather than a capability check: the race is
    a property of the OS receiving the event, not of anything this process can detect from here.
    """
    if sys.platform == "darwin":  # pragma: no cover - platform specific
        time.sleep(MACOS_MOVE_SETTLE)


def _scroll_vector(amount: int, direction: ScrollDirection) -> tuple[int, int]:
    if direction is ScrollDirection.UP:
        return 0, amount
    if direction is ScrollDirection.DOWN:
        return 0, -amount
    if direction is ScrollDirection.LEFT:
        return -amount, 0
    return amount, 0


def _to_png(shot: Any) -> bytes:
    from PIL import Image

    image = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _check_macos_permissions() -> None:
    """Fail loudly when macOS has denied what pynput and mss need.

    Without the permission the libraries typically do nothing at all -- a click that never
    happens and never errors, which is the worst possible failure for a calling agent.
    """
    if sys.platform != "darwin":  # pragma: no cover - platform specific
        return
    try:  # pragma: no cover - requires macOS
        from ApplicationServices import AXIsProcessTrusted
    except ImportError:  # pragma: no cover - pyobjc absent; let the action fail instead
        return
    if not AXIsProcessTrusted():  # pragma: no cover - requires macOS
        raise PermissionDeniedError(
            "Accessibility",
            "Grant it in System Settings > Privacy & Security > Accessibility for the "
            "terminal or application running use-computer, then start it again.",
        )
    try:  # pragma: no cover - requires macOS
        from Quartz import CGPreflightScreenCaptureAccess
    except ImportError:  # pragma: no cover
        return
    if not CGPreflightScreenCaptureAccess():  # pragma: no cover - requires macOS
        raise PermissionDeniedError(
            "Screen Recording",
            "Grant it in System Settings > Privacy & Security > Screen Recording, then start "
            "use-computer again.",
        )
