"""Coordinate spaces: the factor of two that makes every click land in the wrong place."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from use_computer.coordinates import (
    Coordinate,
    CoordinateSpace,
    ScreenInfo,
    convert,
    derive_scale,
)
from use_computer.errors import CoordinateSpaceError

HIDPI = ScreenInfo(
    width=1280, height=800, screenshot_width=2560, screenshot_height=1600, scale=2.0
)
UNKNOWN = ScreenInfo(width=1280, height=800, screenshot_width=2560, screenshot_height=1601)


def test_screenshot_to_actuation_halves_on_a_hidpi_display() -> None:
    point = Coordinate(x=120, y=340, space=CoordinateSpace.SCREENSHOT)
    assert convert(point, CoordinateSpace.ACTUATION, HIDPI) == Coordinate(
        x=60, y=170, space=CoordinateSpace.ACTUATION
    )


def test_actuation_to_screenshot_is_the_inverse() -> None:
    point = Coordinate(x=60, y=170, space=CoordinateSpace.ACTUATION)
    assert convert(point, CoordinateSpace.SCREENSHOT, HIDPI).x == 120


def test_same_space_is_returned_untouched() -> None:
    point = Coordinate(x=7, y=9, space=CoordinateSpace.ACTUATION)
    assert convert(point, CoordinateSpace.ACTUATION, UNKNOWN) is point


def test_unknown_scale_refuses_instead_of_guessing() -> None:
    point = Coordinate(x=120, y=340, space=CoordinateSpace.SCREENSHOT)
    with pytest.raises(CoordinateSpaceError) as excinfo:
        convert(point, CoordinateSpace.ACTUATION, UNKNOWN)
    assert "scale" in str(excinfo.value)


def test_derive_scale_reads_a_consistent_pair() -> None:
    assert derive_scale(1280, 800, 2560, 1600) == pytest.approx(2.0)
    assert derive_scale(1920, 1080, 1920, 1080) == pytest.approx(1.0)


def test_derive_scale_reports_an_inconsistent_pair_as_unknown() -> None:
    # Averaging two disagreeing ratios into a plausible number is exactly the failure mode
    # this project refuses.
    assert derive_scale(1280, 800, 2560, 900) is None
    assert derive_scale(0, 800, 2560, 1600) is None


def test_a_coordinate_is_frozen() -> None:
    point = Coordinate(x=1, y=2, space=CoordinateSpace.SCREENSHOT)
    with pytest.raises(ValidationError):
        point.x = 5
