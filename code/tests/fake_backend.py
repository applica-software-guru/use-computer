"""A backend that records the actions it was asked to perform.

It satisfies the same Protocol as the real ones, so everything above the backend boundary --
scaling, key normalisation, batching, verification, dry-run -- is testable without a screen.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from use_computer.actions import MouseButton, ScrollDirection
from use_computer.compare import Screenshot
from use_computer.coordinates import CoordinateSpace, ScreenInfo
from use_computer.keys import KeyCombo


def png(width: int, height: int, colour: tuple[int, int, int] = (0, 0, 0)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


@dataclass
class FakeBackend:
    """Records calls; optionally fails on demand."""

    name: str = "fake"
    width: int = 1280
    height: int = 800
    screenshot_width: int = 2560
    screenshot_height: int = 1600
    scale: float | None = 2.0
    calls: list[tuple[str, Any]] = field(default_factory=list)
    fail_on: str | None = None
    closed: bool = False
    #: Each capture returns the next colour, so before/after differ when asked to.
    colours: list[tuple[int, int, int]] = field(
        default_factory=lambda: [(0, 0, 0), (0, 0, 0)]
    )
    _captures: int = 0

    def screen_info(self) -> ScreenInfo:
        return ScreenInfo(
            width=self.width,
            height=self.height,
            screenshot_width=self.screenshot_width,
            screenshot_height=self.screenshot_height,
            scale=self.scale,
        )

    def screenshot(self) -> Screenshot:
        colour = self.colours[min(self._captures, len(self.colours) - 1)]
        self._captures += 1
        return Screenshot(
            data=png(self.screenshot_width, self.screenshot_height, colour),
            width=self.screenshot_width,
            height=self.screenshot_height,
            space=CoordinateSpace.SCREENSHOT,
        )

    def _record(self, name: str, payload: Any) -> None:
        if self.fail_on == name:
            raise RuntimeError(f"fake backend refused to {name}")
        self.calls.append((name, payload))

    def move(self, x: int, y: int) -> None:
        self._record("move", (x, y))

    def click(self, x: int | None, y: int | None, button: MouseButton, count: int) -> None:
        self._record("click", (x, y, button.value, count))

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, button: MouseButton) -> None:
        self._record("drag", (from_x, from_y, to_x, to_y, button.value))

    def scroll(
        self, amount: int, direction: ScrollDirection, x: int | None, y: int | None
    ) -> None:
        self._record("scroll", (amount, direction.value, x, y))

    def type_text(self, text: str, rate: float) -> None:
        self._record("type_text", (text, rate))

    def key(self, combo: KeyCombo) -> None:
        self._record("key", str(combo))

    def close(self) -> None:
        self.closed = True
