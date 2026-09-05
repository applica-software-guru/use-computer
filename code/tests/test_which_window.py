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
from use_computer.selectors import active_window, sole_active


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
