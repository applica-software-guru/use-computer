"""Which window is the active one, and what happens when the platform cannot say.

Measured on a real desktop: three windows carried the mark at once, because AT-SPI reports
`active` per *application*. Neither that flag, nor `focused`, nor looking for a focused
descendant identified the window actually on top.
"""

from __future__ import annotations

import pytest

from tests.fake_provider import window
from use_computer.errors import AmbiguousWindowError, UITreeUnavailableError
from use_computer.render import windows_for_a_reader
from use_computer.selectors import active_window, mark_active, sole_active
from use_computer.tree import ActiveWindow


def test_one_claim_is_left_alone() -> None:
    marked = sole_active([window("0/1", "A", active=True), window("0/2", "B")])
    assert [entry.active for entry in marked] == [True, False]


def test_several_claims_leave_no_mark_at_all() -> None:
    # Saying nothing is worth more than a mark that is wrong two times in three, and this column
    # is the first thing an agent is told to read.
    marked = sole_active(
        [
            window("0/19", "", active=True),
            window("0/34", "ChatGPT", active=True),
            window("0/37", "Drawing", active=True),
        ]
    )
    assert [entry.active for entry in marked] == [False, False, False]


def test_the_column_then_shows_no_star() -> None:
    text = windows_for_a_reader(
        sole_active([window("0/1", "A", active=True), window("0/2", "B", active=True)])
    )
    assert "*" not in text.replace("active", "")


def test_focused_refuses_rather_than_taking_the_first() -> None:
    # Picking the first match is how an agent reads, clicks and verifies inside the wrong
    # application, consistently and with no sign anything went wrong.
    with pytest.raises(AmbiguousWindowError) as excinfo:
        active_window([window("0/34", "ChatGPT", active=True), window("0/37", "Draw", active=True)])
    assert {entry.id for entry in excinfo.value.candidates} == {"0/34", "0/37"}
    assert "--window" in str(excinfo.value)


def test_no_claim_at_all_says_how_to_name_one() -> None:
    with pytest.raises(UITreeUnavailableError) as excinfo:
        active_window([window("0/1", "A"), window("0/2", "B")])
    assert "--window" in str(excinfo.value)


def test_one_claim_resolves() -> None:
    assert active_window([window("0/1", "A"), window("0/2", "B", active=True)]).id == "0/2"


# --- what the window manager says --------------------------------------------------------------


def test_the_window_manager_settles_what_the_flags_could_not() -> None:
    # Three windows claimed `active`; `_NET_ACTIVE_WINDOW` names one, by pid and title.
    entries = [
        window("0/19", "", active=True),
        window("0/29", "a terminal", active=True),
        window("0/37", "Drawing", active=True),
    ]
    entries[1] = entries[1].model_copy(update={"pid": 2379})
    marked = mark_active(entries, ActiveWindow(pid=2379, title="a terminal"))
    assert [entry.active for entry in marked] == [False, True, False]


def test_the_hint_wins_over_a_flag_that_disagrees() -> None:
    entries = [
        window("0/29", "a terminal", active=True).model_copy(update={"pid": 1}),
        window("0/37", "Drawing").model_copy(update={"pid": 2}),
    ]
    marked = mark_active(entries, ActiveWindow(pid=2, title="Drawing"))
    assert [entry.active for entry in marked] == [False, True]


def test_one_pid_with_several_windows_is_settled_by_the_title() -> None:
    entries = [
        window("0/34/0", "ChatGPT").model_copy(update={"pid": 9}),
        window("0/34/1", "Notes").model_copy(update={"pid": 9}),
    ]
    marked = mark_active(entries, ActiveWindow(pid=9, title="Notes"))
    assert [entry.active for entry in marked] == [False, True]


def test_a_hint_that_matches_nothing_leaves_the_flags_alone() -> None:
    # Wayland, a renamed window, a pid the tree does not know: never invent a mark.
    entries = [window("0/1", "A", active=True), window("0/2", "B")]
    assert [e.active for e in mark_active(entries, ActiveWindow(pid=999))] == [True, False]


def test_no_hint_at_all_behaves_exactly_as_before() -> None:
    entries = [window("0/1", "A", active=True), window("0/2", "B", active=True)]
    assert [entry.active for entry in mark_active(entries, None)] == [False, False]


def test_an_ambiguous_hint_does_not_guess() -> None:
    entries = [
        window("0/34/0", "ChatGPT").model_copy(update={"pid": 9}),
        window("0/34/1", "ChatGPT").model_copy(update={"pid": 9}),
    ]
    marked = mark_active(entries, ActiveWindow(pid=9, title="ChatGPT"))
    assert [entry.active for entry in marked] == [False, False]
