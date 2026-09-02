"""Batching, scaling at the boundary, dry-run, verification, and stopping at the first failure."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.fake_backend import FakeBackend
from use_computer.actions import (
    ClickAction,
    DoubleClickAction,
    DragAction,
    KeyAction,
    MoveAction,
    RightClickAction,
    ScreenshotAction,
    ScrollAction,
    TypeAction,
)
from use_computer.config import Settings
from use_computer.coordinates import CoordinateSpace
from use_computer.runner import Session, as_json


def session(backend: FakeBackend, **settings: object) -> Session:
    return Session(backend, profile="fake", settings=Settings(**settings))  # type: ignore[arg-type]


def test_one_batch_uses_one_backend_and_records_every_action() -> None:
    backend = FakeBackend()
    result = session(backend).run(
        [
            ClickAction(x=120, y=340),
            TypeAction(text="hello"),
            KeyAction(combo="enter"),
        ]
    )
    assert result.ok is True
    assert [name for name, _ in backend.calls] == ["click", "type_text", "key"]
    assert len(result.results) == 3


def test_coordinates_reach_the_backend_in_actuation_units() -> None:
    backend = FakeBackend()  # 2560x1600 screenshot over 1280x800 actuation
    result = session(backend).run([ClickAction(x=120, y=340, space=CoordinateSpace.SCREENSHOT)])
    assert backend.calls[0][1][:2] == (60, 170)
    assert result.results[0].resolved is not None
    assert result.results[0].resolved.space is CoordinateSpace.ACTUATION


def test_an_action_already_in_actuation_units_is_not_scaled_again() -> None:
    backend = FakeBackend()
    session(backend).run([ClickAction(x=60, y=170, space=CoordinateSpace.ACTUATION)])
    assert backend.calls[0][1][:2] == (60, 170)


def test_an_unknown_scale_fails_the_action_instead_of_guessing() -> None:
    backend = FakeBackend(scale=None)
    result = session(backend).run([ClickAction(x=120, y=340)])
    assert result.ok is False
    assert result.results[0].error is not None
    assert result.results[0].error.type == "CoordinateSpaceError"
    assert backend.calls == []


def test_a_drag_reports_both_ends_resolved() -> None:
    backend = FakeBackend()
    result = session(backend).run(DRAG := [DragAction(from_x=10, from_y=20, to_x=300, to_y=400)])
    assert backend.calls[0][1] == (5, 10, 150, 200, "left")
    assert result.results[0].resolved_from is not None
    assert result.results[0].resolved_from.x == 5
    assert result.results[0].resolved is not None
    assert result.results[0].resolved.x == 150
    assert DRAG  # the action list is untouched


def test_double_click_and_right_click_are_distinct_at_the_boundary() -> None:
    backend = FakeBackend()
    session(backend).run([DoubleClickAction(x=0, y=0), RightClickAction(x=0, y=0)])
    assert backend.calls[0] == ("click", (0, 0, "left", 2))
    assert backend.calls[1] == ("click", (0, 0, "right", 1))


def test_move_and_scroll_reach_the_backend() -> None:
    backend = FakeBackend()
    session(backend).run([MoveAction(x=200, y=100), ScrollAction(amount=3)])
    assert backend.calls[0] == ("move", (100, 50))
    assert backend.calls[1] == ("scroll", (3, "down", None, None))


def test_dry_run_resolves_everything_and_performs_nothing() -> None:
    backend = FakeBackend()
    result = session(backend, dry_run=True).run(
        [ClickAction(x=120, y=340), KeyAction(combo="ctrl+s")]
    )
    assert backend.calls == []
    assert all(item.performed is False for item in result.results)
    # Resolution still happened: the agent can inspect exactly what would occur.
    assert result.results[0].resolved is not None
    assert result.results[0].resolved.x == 60
    assert result.ok is True


def test_a_batch_stops_at_the_first_failure_and_names_the_index() -> None:
    backend = FakeBackend(fail_on="type_text")
    result = session(backend).run(
        [ClickAction(x=0, y=0), TypeAction(text="x"), KeyAction(combo="enter")]
    )
    assert result.ok is False
    assert result.failed_index == 1
    assert len(result.results) == 2
    assert "key" not in [name for name, _ in backend.calls]


def test_continue_on_error_runs_the_remainder() -> None:
    backend = FakeBackend(fail_on="type_text")
    result = session(backend, continue_on_error=True).run(
        [ClickAction(x=0, y=0), TypeAction(text="x"), KeyAction(combo="enter")]
    )
    assert result.ok is False
    assert result.failed_index == 1
    assert len(result.results) == 3
    assert ("key", "enter") in backend.calls


def test_verify_reports_a_screen_that_did_not_change() -> None:
    backend = FakeBackend(colours=[(0, 0, 0), (0, 0, 0)])
    result = session(backend, verify=True).run([ClickAction(x=10, y=10)])
    change = result.results[0].change
    assert change is not None
    assert change.changed is False


def test_verify_reports_a_screen_that_changed() -> None:
    backend = FakeBackend(colours=[(0, 0, 0), (255, 255, 255)])
    result = session(backend, verify=True).run([ClickAction(x=10, y=10)])
    change = result.results[0].change
    assert change is not None
    assert change.changed is True
    assert change.magnitude > 0.9


def test_verification_is_off_unless_asked_for() -> None:
    backend = FakeBackend()
    result = session(backend).run([ClickAction(x=10, y=10)])
    assert result.results[0].change is None


def test_a_screenshot_action_returns_the_capture() -> None:
    backend = FakeBackend()
    result = session(backend).run([ScreenshotAction(base64=True)])
    payload = as_json(result)
    shot = payload["results"][0]["screenshot"]
    assert shot is not None
    assert shot["width"] == 2560
    assert shot["base64"]


def test_a_screenshot_action_writes_the_file_it_was_given(tmp_path: Path) -> None:
    backend = FakeBackend()
    out = tmp_path / "shots" / "screen.png"
    result = session(backend).run([ScreenshotAction(out=out)])
    assert out.is_file()
    assert result.results[0].screenshot is not None


def test_the_backend_is_closed_even_when_an_action_failed() -> None:
    backend = FakeBackend(fail_on="click")
    with session(backend) as open_session:
        open_session.run([ClickAction(x=0, y=0)])
    assert backend.closed is True


def test_results_are_frozen() -> None:
    backend = FakeBackend()
    result = session(backend).run([ClickAction(x=0, y=0)])
    with pytest.raises(ValidationError):
        result.results[0].performed = False


def test_the_run_payload_has_the_documented_shape() -> None:
    backend = FakeBackend()
    payload = as_json(session(backend).run([ClickAction(x=120, y=340)]))
    assert set(payload) == {"profile", "backend", "screen", "ok", "failed_index", "results"}
    item = payload["results"][0]
    assert item["action"]["action"] == "click"
    assert item["resolved"] == {"x": 60, "y": 170, "space": "actuation"}
    assert item["performed"] is True
    assert item["error"] is None
