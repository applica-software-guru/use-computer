"""Screenshots, and the before/after comparison that tells an agent whether anything happened.

A click that lands on nothing looks exactly like a click that worked. Comparing a screenshot
taken before and after an action gives the calling agent the feedback signal it needs to
correct a stale coordinate instead of retrying forever.

The question is "did something happen", not "which pixels differ", so comparison runs on
downscaled greyscale images. This module is pure: it takes images and returns a report.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops
from pydantic import BaseModel, ConfigDict, Field

from use_computer.coordinates import CoordinateSpace

#: Fraction of differing pixels below which a change is noise -- a caret, a clock.
DEFAULT_THRESHOLD = 0.002

#: Longest edge the images are reduced to before comparison.
#:
#: 256 was too small, and the two numbers below are one decision with it. At 256 a 1920-wide screen
#: is scaled by 0.13, so a 4 px stroke lands on half a pixel and averages away against the
#: background before anything is counted.
COMPARE_SIZE = 512

#: Per-pixel greyscale delta counted as a difference.
PIXEL_DELTA = 16

#: Longest side, in screenshot pixels, that makes a change real regardless of the fraction.
#:
#: The fraction answers "how much of the screen moved", which is the wrong question for almost
#: everything a UI does in response to a click: at 0.2% of 1920x1080 it ignores the first ~4,000
#: pixels, so a drawn stroke, a ticked checkbox, an incremented spinner and a highlighted row all
#: reported `unchanged` -- and this feature's advice on `unchanged` is to throw the coordinate away
#: and pay for vision. The two errors are not symmetric: a false `changed` costs a look, a false
#: `unchanged` costs the coordinate.
#:
#: Extent rather than a pixel count, because a count means different things on different images and
#: cannot tell a thin wide stroke from a small blob. A caret is 2x8 and stays noise; a 200x4 stroke
#: and a 16x16 checkbox are changes. That is the distinction, stated directly.
MIN_CHANGE_EXTENT = 16


class Screenshot(BaseModel):
    """A captured screen.

    ``data`` is held only while a comparison needs it. It is excluded from serialisation: a
    screenshot that reaches the calling agent is a path, never a megabyte of base64 in its
    context.
    """

    model_config = ConfigDict(frozen=True)

    path: Path | None = None
    of: str | None = Field(default=None, description="The node id this was cropped to.")
    box: tuple[int, int, int, int] | None = Field(
        default=None, description="The crop, in screenshot pixels."
    )
    data: bytes | None = Field(default=None, repr=False, exclude=True)
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

    def write_to(self, path: Path) -> Screenshot:
        """Write the PNG to ``path`` and return the screenshot that knows where it lives."""
        if self.path == path:
            return self
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.data is not None:
            path.write_bytes(self.data)
        elif self.path is not None:
            path.write_bytes(self.path.read_bytes())
        else:
            raise ValueError("screenshot has neither data nor path")
        return self.model_copy(update={"path": path})


class ChangeReport(BaseModel):
    """Whether the screen changed, by how much, and where."""

    model_config = ConfigDict(frozen=True)

    changed: bool
    magnitude: float = Field(description="Fraction of pixels that differ, 0.0 to 1.0.")
    threshold: float
    bbox: tuple[int, int, int, int] | None = Field(
        default=None, description="Bounding box of the change, in screenshot pixels."
    )


def crop(
    shot: Screenshot, box: tuple[int, int, int, int], node_id: str | None = None
) -> Screenshot:
    """A picture of one element, in screenshot pixels, clipped to the screen.

    A node's box can extend past the edge -- a negative origin or an over-wide width must produce
    a smaller picture, never an error.
    """
    left, top, width, height = box
    right = min(left + width, shot.width)
    bottom = min(top + height, shot.height)
    left = max(left, 0)
    top = max(top, 0)
    if right <= left or bottom <= top:
        raise ValueError(f"{node_id or 'that box'} is not on the screen")

    image = Image.open(io.BytesIO(shot.data or b"")).crop((left, top, right, bottom))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Screenshot(
        data=buffer.getvalue(),
        width=right - left,
        height=bottom - top,
        space=shot.space,
        of=node_id,
        box=(left, top, right - left, bottom - top),
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

    # The box is computed first, because it is what decides. It is also the only part of this an
    # agent can act on: a box can be compared against what was expected to happen, a percentage
    # cannot, and a real change of a few thousand pixels renders as `0%`.
    bbox = None
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
    extent = max(bbox[2] - bbox[0], bbox[3] - bbox[1]) if bbox is not None else 0
    changed = magnitude > threshold or extent >= MIN_CHANGE_EXTENT
    return ChangeReport(
        changed=changed,
        magnitude=magnitude,
        threshold=threshold,
        bbox=bbox if changed else None,
    )


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
