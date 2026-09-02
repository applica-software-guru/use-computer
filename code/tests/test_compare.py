"""Change detection: the feedback signal that tells a stale coordinate from a slow app."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw
from tests.fake_backend import png

from use_computer.compare import DEFAULT_THRESHOLD, Screenshot, compare


def shot(colour: tuple[int, int, int], size: tuple[int, int] = (400, 300)) -> Screenshot:
    return Screenshot(data=png(size[0], size[1], colour), width=size[0], height=size[1])


def patched(
    base: tuple[int, int, int],
    colour: tuple[int, int, int],
    patch: tuple[int, int],
    size: tuple[int, int] = (400, 300),
) -> Screenshot:
    """The base colour with a rectangle of ``patch`` size painted in a corner."""
    image = Image.new("RGB", size, base)
    ImageDraw.Draw(image).rectangle((10, 10, 10 + patch[0], 10 + patch[1]), fill=colour)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Screenshot(data=buffer.getvalue(), width=size[0], height=size[1])


def test_identical_screens_report_no_change() -> None:
    report = compare(shot((10, 10, 10)), shot((10, 10, 10)))
    assert report.changed is False
    assert report.magnitude == 0.0


def test_a_repainted_screen_reports_a_change_with_a_bbox() -> None:
    report = compare(shot((0, 0, 0)), shot((255, 255, 255)))
    assert report.changed is True
    assert report.magnitude > 0.9
    assert report.bbox is not None


def test_a_resolution_change_is_unambiguously_a_change() -> None:
    report = compare(shot((0, 0, 0), (400, 300)), shot((0, 0, 0), (800, 600)))
    assert report.changed is True
    assert report.magnitude == 1.0


def test_a_caret_sized_change_stays_below_the_default_threshold() -> None:
    # A blinking caret must not read as a response, or every retry loop believes it worked.
    report = compare(shot((0, 0, 0)), patched((0, 0, 0), (255, 255, 255), (2, 8)))
    assert report.magnitude < DEFAULT_THRESHOLD
    assert report.changed is False


def test_a_dialog_sized_change_clears_the_default_threshold() -> None:
    report = compare(shot((0, 0, 0)), patched((0, 0, 0), (255, 255, 255), (200, 150)))
    assert report.changed is True
    assert report.bbox is not None
