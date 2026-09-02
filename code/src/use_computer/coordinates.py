"""Coordinate spaces and the conversion between them.

A screenshot on a HiDPI display is larger than the space the operating system clicks in. An
unhandled factor of two makes every click land in the wrong place, and nothing about the
failure looks like a scaling bug -- so every coordinate carries the space it belongs to, and a
conversion whose ratio is unknown raises instead of guessing.

This module is pure: it knows nothing about backends.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from use_computer.errors import CoordinateSpaceError

#: Relative disagreement tolerated between the horizontal and vertical ratios before the two
#: reported screen sizes are called inconsistent.
SCALE_TOLERANCE = 0.02


class CoordinateSpace(str, Enum):
    """The space a coordinate is expressed in."""

    SCREENSHOT = "screenshot"
    """Pixels of the captured image -- what ui-locator returns, because it looked at the image."""

    ACTUATION = "actuation"
    """The units the backend moves the pointer in."""


class Coordinate(BaseModel):
    """A point, together with the space it belongs to.

    A bare pair of numbers is not a coordinate; the space is part of the value.
    """

    model_config = ConfigDict(frozen=True)

    x: int
    y: int
    space: CoordinateSpace


class ScreenInfo(BaseModel):
    """What a backend reports about its own screen."""

    model_config = ConfigDict(frozen=True)

    width: int = Field(description="Screen width in actuation units.")
    height: int = Field(description="Screen height in actuation units.")
    screenshot_width: int = Field(description="Screenshot width in pixels.")
    screenshot_height: int = Field(description="Screenshot height in pixels.")
    scale: float | None = Field(
        default=None,
        description=(
            "Screenshot pixels per actuation unit. None means unknown -- conversion refuses."
        ),
    )

    def size(self, space: CoordinateSpace) -> tuple[int, int]:
        if space is CoordinateSpace.SCREENSHOT:
            return self.screenshot_width, self.screenshot_height
        return self.width, self.height


def derive_scale(
    width: int, height: int, screenshot_width: int, screenshot_height: int
) -> float | None:
    """Derive the screenshot/actuation ratio from two reported sizes.

    Returns ``None`` when it cannot be derived -- a zero dimension, or horizontal and vertical
    ratios that disagree by more than :data:`SCALE_TOLERANCE`. An inconsistent pair is not
    averaged into a plausible-looking number; it is reported as unknown.
    """
    if width <= 0 or height <= 0 or screenshot_width <= 0 or screenshot_height <= 0:
        return None
    ratio_x = screenshot_width / width
    ratio_y = screenshot_height / height
    if abs(ratio_x - ratio_y) > SCALE_TOLERANCE * max(ratio_x, ratio_y):
        return None
    return (ratio_x + ratio_y) / 2


def convert(coord: Coordinate, target: CoordinateSpace, screen: ScreenInfo) -> Coordinate:
    """Convert ``coord`` into ``target`` space.

    Raises:
        CoordinateSpaceError: when the scale is unknown, so the conversion would be a guess.
    """
    if coord.space is target:
        return coord
    if screen.scale is None or screen.scale <= 0:
        raise CoordinateSpaceError(
            f"cannot convert {coord.x},{coord.y} from {coord.space.value} to {target.value}: "
            f"the backend reports {screen.width}x{screen.height} actuation units and "
            f"{screen.screenshot_width}x{screen.screenshot_height} screenshot pixels, from which "
            "no consistent scale can be derived. Capture a screenshot to establish the ratio, or "
            "set `scale` explicitly in the profile."
        )
    factor = 1 / screen.scale if coord.space is CoordinateSpace.SCREENSHOT else screen.scale
    return Coordinate(x=round(coord.x * factor), y=round(coord.y * factor), space=target)
