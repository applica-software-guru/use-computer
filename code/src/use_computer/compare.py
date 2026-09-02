"""Screenshots, and the before/after comparison that tells an agent whether anything happened.

A click that lands on nothing looks exactly like a click that worked. Comparing a screenshot
taken before and after an action gives the calling agent the feedback signal it needs to
correct a stale coordinate instead of retrying forever.

The question is "did something happen", not "which pixels differ", so comparison runs on
downscaled greyscale images. This module is pure: it takes images and returns a report.
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops
from pydantic import BaseModel, ConfigDict, Field

from use_computer.coordinates import CoordinateSpace

#: Fraction of differing pixels below which a change is noise -- a caret, a clock.
DEFAULT_THRESHOLD = 0.002

#: Longest edge the images are reduced to before comparison.
COMPARE_SIZE = 256

#: Per-pixel greyscale delta counted as a difference.
PIXEL_DELTA = 16


class Screenshot(BaseModel):
    """A captured screen."""

    model_config = ConfigDict(frozen=True)

    path: Path | None = None
    data: bytes | None = Field(default=None, repr=False)
    width: int
    height: int
    space: CoordinateSpace = CoordinateSpace.SCREENSHOT
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_image(self) -> Image.Image:
        """Load the screenshot as a PIL image, from memory or from disk."""
        if self.data is not None:
            return Image.open(io.BytesIO(self.data))
        if self.path is not None:
            return Image.open(self.path)
        raise ValueError("screenshot has neither data nor path")

    def base64(self) -> str:
        """The PNG bytes, base64-encoded, for transport to the calling agent."""
        if self.data is not None:
            return base64.b64encode(self.data).decode("ascii")
        if self.path is not None:
            return base64.b64encode(self.path.read_bytes()).decode("ascii")
        raise ValueError("screenshot has neither data nor path")


class ChangeReport(BaseModel):
    """Whether the screen changed, by how much, and where."""

    model_config = ConfigDict(frozen=True)

    changed: bool
    magnitude: float = Field(description="Fraction of pixels that differ, 0.0 to 1.0.")
    threshold: float
    bbox: tuple[int, int, int, int] | None = Field(
        default=None, description="Bounding box of the change, in screenshot pixels."
    )


def compare(
    before: Screenshot, after: Screenshot, threshold: float = DEFAULT_THRESHOLD
) -> ChangeReport:
    """Compare two screenshots and report whether the screen actually changed.

    The result is advisory: a false result does not fail the action, it tells the agent the
    coordinate was probably stale.
    """
    if (before.width, before.height) != (after.width, after.height):
        # A resolution change is unambiguously a change, and the images are not comparable.
        return ChangeReport(changed=True, magnitude=1.0, threshold=threshold, bbox=None)

    left = _prepare(before.to_image())
    right = _prepare(after.to_image())

    diff = ImageChops.difference(left, right)
    mask = diff.point(lambda value: 255 if value >= PIXEL_DELTA else 0)
    differing = mask.histogram()[255]
    total = mask.width * mask.height
    magnitude = differing / total if total else 0.0
    changed = magnitude > threshold

    bbox = None
    if changed:
        raw = mask.getbbox()
        if raw is not None:
            scale_x = after.width / mask.width
            scale_y = after.height / mask.height
            bbox = (
                int(raw[0] * scale_x),
                int(raw[1] * scale_y),
                int(raw[2] * scale_x),
                int(raw[3] * scale_y),
            )
    return ChangeReport(changed=changed, magnitude=magnitude, threshold=threshold, bbox=bbox)


def _prepare(image: Image.Image) -> Image.Image:
    grey = image.convert("L")
    longest = max(grey.width, grey.height)
    if longest > COMPARE_SIZE:
        ratio = COMPARE_SIZE / longest
        grey = grey.resize(
            (max(1, int(grey.width * ratio)), max(1, int(grey.height * ratio))),
            Image.Resampling.BILINEAR,
        )
    return grey
