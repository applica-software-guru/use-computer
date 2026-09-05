"""What a result line claims, and the cases where the claim was not worth anything.

Every test here comes from one agent session that took fifteen commands for work that needed
three. Not one detour came from not knowing a flag; every one came from believing a report.
"""

from __future__ import annotations

import pytest

from tests.fake_backend import FakeBackend
from tests.fake_provider import FakeProvider, node, window
from use_computer.actions import (
    Action,
    ActivateAction,
    ClickAction,
    DragAction,
    KeyAction,
    TreeAction,
    TypeAction,
    check_action_names,
    normalise_action_names,
)
from use_computer.compare import ChangeReport
from use_computer.config import Settings
from use_computer.runner import Session
from use_computer.tree import NodeSelector, TreeScope


def runner_for(provider: FakeProvider) -> Session:
    return Session(
        FakeBackend(), profile="fake", settings=Settings(), provider=provider
    )


def palette() -> FakeProvider:
    """GTK's colour palette: a swatch that advertises `click`, accepts it, and ignores it."""
    return FakeProvider(
        root=node(
            "0",
            "window",
            "Drawing",
            box=(0, 0, 800, 600),
            children=(
                node(
                    "0/0",
                    "radio",
                    "Dark Brown",
                    actions=("click", "focus", "select"),
                    box=(300, 400, 48, 32),
                ),
                node("0/1", "button", "Save", actions=("click", "focus"), box=(10, 10, 60, 24)),
            ),
        )
    )


def test_a_click_on_a_swatch_asks_for_select_not_click() -> None:
    provider = palette()
    runner_for(provider).run(
        [ClickAction(selector=NodeSelector(node_id="0/0", role="radio", name="Dark Brown"))]
    )
    # `actions` is what the platform will accept, not what will work: the swatch returns true from
    # `click` and does nothing with it. `select` is the action that carries its meaning.
    assert provider.calls == [("0/0", "select", None)]


def test_a_click_on_a_button_is_still_a_click() -> None:
    provider = palette()
    runner_for(provider).run(
        [ClickAction(selector=NodeSelector(node_id="0/1", role="button", name="Save"))]
    )
    assert provider.calls == [("0/1", "click", None)]


def test_a_depth_limit_is_not_an_empty_application() -> None:
    # `empty` is a diagnosis about the application, and the skill turns it into "go and look".
    # A limit the caller asked for is not that, and a screenshot attached to it makes the wrong
    # branch convenient.
    provider = palette()
    result = runner_for(provider).run([TreeAction(depth=1)])
    tree = result.results[0].tree
    assert tree is not None
    assert tree.reason is None
    assert tree.screenshot is None
    assert tree.limited_by == "--depth 1"


def test_an_application_that_exposes_nothing_still_says_empty() -> None:
    provider = FakeProvider(root=node("0", "window", "Canvas", box=(0, 0, 800, 600)))
    tree = runner_for(provider).run([TreeAction()]).results[0].tree
    assert tree is not None
    assert tree.reason is not None and tree.reason.value == "empty"


def test_activate_focuses_a_descendant_when_the_platform_has_no_raise() -> None:
    # A window accessible reports no actions of its own on any of the three platforms.
    provider = palette()
    provider.window_list = (window("0", "Drawing"),)
    runner_for(provider).run([ActivateAction(window=TreeScope.parse("0"))])
    assert provider.activated == ["0"]
    assert provider.calls and provider.calls[0][1] == "focus"


def test_activate_stops_at_a_native_raise() -> None:
    provider = palette()
    provider.window_list = (window("0", "Drawing"),)
    provider.native_raise = True
    runner_for(provider).run([ActivateAction(window=TreeScope.parse("0"))])
    assert provider.activated == ["0"]
    assert provider.calls == []  # nothing was focused: the platform raised it itself


def test_activating_a_window_already_in_front_does_nothing() -> None:
    provider = palette()
    provider.window_list = (window("0", "Drawing", active=True),)
    runner_for(provider).run([ActivateAction(window=TreeScope.parse("0"))])
    assert provider.activated == []
    assert provider.calls == []


def test_a_coordinate_with_a_window_brings_it_forward_first() -> None:
    # Two drags aimed at a canvas selected text in a terminal instead, and `--verify` then
    # confirmed the wrong action against the wrong window.
    provider = palette()
    provider.window_list = (window("0", "Drawing"),)
    runner_for(provider).run(
        [DragAction(from_x=10, from_y=20, to_x=30, to_y=40, window=TreeScope.parse("0"))]
    )
    assert provider.activated == ["0"]


def test_a_bare_coordinate_raises_nothing() -> None:
    provider = palette()
    runner_for(provider).run([DragAction(from_x=10, from_y=20, to_x=30, to_y=40)])
    assert provider.activated == []


@pytest.mark.parametrize(
    ("spelled", "meant"),
    [("set-value", "set_value"), ("double-click", "double_click"), ("right-click", "right_click")],
)
def test_a_batch_accepts_the_spelling_the_cli_uses(spelled: str, meant: str) -> None:
    assert normalise_action_names([{"action": spelled}]) == [{"action": meant}]


def test_an_unknown_action_is_a_sentence_with_the_nearest_match() -> None:
    with pytest.raises(ValueError) as excinfo:
        check_action_names([{"action": "click"}, {"action": "set-valeu"}])
    message = str(excinfo.value)
    assert "index 1" in message
    assert "'set-value'" in message
    assert "tagged-union" not in message  # not the internal union, four hundred characters of it


# --- what the line says it did -----------------------------------------------------------------


def line_for(action: Action, provider: FakeProvider | None = None) -> str:
    from use_computer.cli import _text_lines

    session = Session(
        FakeBackend(), profile="fake", settings=Settings(), provider=provider or palette()
    )
    return _text_lines(session.run([action])).splitlines()[0]


def test_a_key_line_names_the_combination() -> None:
    assert line_for(KeyAction(combo="ctrl+z")).startswith("key ctrl+z")


def test_a_type_line_carries_the_text_and_its_length() -> None:
    # The count is what catches a truncated or a doubled paste; the text is what identifies it.
    line = line_for(TypeAction(text="/home/you/Desktop/albero.png"))
    assert "28 chars" in line
    assert "albero.png" in line


def test_a_long_typed_string_is_clamped_like_a_node_value() -> None:
    line = line_for(TypeAction(text="x" * 400))
    assert "400 chars" in line
    assert "…" in line
    assert len(line) < 120


def test_a_drag_line_carries_both_of_its_points() -> None:
    # A drag is defined by two points, and reporting one of them is reporting none of it.
    # The fake backend halves coordinates, which is the point of the next test.
    line = line_for(DragAction(from_x=666, from_y=660, to_x=666, to_y=545))
    assert "(333, 330) \u2192 (333, 272)" in line


def test_a_coordinate_line_reports_what_was_actually_sent() -> None:
    # After scaling, not as typed: on a HiDPI display the two differ, and the converted number is
    # the one a coordinate-space bug turns on. The fake backend scales by half.
    assert "(60, 170)" in line_for(ClickAction(x=120, y=340))


def test_a_tree_emptied_by_a_limit_says_so_in_the_text() -> None:
    from use_computer.cli import _text_lines

    session = Session(
        FakeBackend(), profile="fake", settings=Settings(), provider=palette()
    )
    text = _text_lines(session.run([TreeAction(depth=1)]))
    assert "--depth 1" in text
    assert "not the application" in text


def test_verify_reports_where_the_screen_changed() -> None:
    from use_computer.cli import _changed

    report = ChangeReport(changed=True, magnitude=0.0004, threshold=0.002, bbox=(40, 120, 640, 432))
    # `changed 0%` is what this used to say, and it reads as a denial.
    assert _changed(report) == "changed 600x312 at 40,120"
    assert _changed(ChangeReport(changed=False, magnitude=0.0, threshold=0.002)) == "unchanged"
