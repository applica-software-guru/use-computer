"""One walk of the desktop per `windows`, whichever branch it takes.

The rule this exists to hold: nothing reads the desktop twice for something the first pass already
had. The regression it exists to catch cost 879 D-Bus calls against 145, on the branch taken while
an application is starting up -- when calls are least likely to be answered and each unanswered one
costs the full 800 ms bound.

The provider itself cannot be constructed here: no CI runner has a session bus. It is built without
`__init__` and given stub accessibles, which is enough to count the walks.
"""

from __future__ import annotations

from typing import Any

import pytest

from use_computer.accessibility.atspi import AtspiProvider


class FakeAccessible:
    def __init__(self, name: str, role: str = "frame", children: tuple[Any, ...] = ()) -> None:
        self.name = name
        self.role = role
        self.children = children

    def get_name(self) -> str:
        return self.name

    def get_role_name(self) -> str:
        return self.role


def provider(states: tuple[str, ...]) -> tuple[AtspiProvider, dict[str, int]]:
    """A provider whose desktop is two applications of one window each."""
    counts = {"desktop": 0}
    desktop = FakeAccessible(
        "desktop",
        children=(
            FakeAccessible("App One", children=(FakeAccessible("One"),)),
            FakeAccessible("App Two", children=(FakeAccessible("Two"),)),
        ),
    )

    made = object.__new__(AtspiProvider)

    def _desktop() -> Any:
        counts["desktop"] += 1
        return desktop

    made._desktop = _desktop  # type: ignore[method-assign]
    made._children = lambda obj: list(getattr(obj, "children", ()))  # type: ignore[method-assign]
    made._states = lambda obj: states  # type: ignore[method-assign]
    made._pid = lambda obj: 7  # type: ignore[method-assign]
    made._box = lambda obj: __import__(  # type: ignore[method-assign]
        "use_computer.tree", fromlist=["Box"]
    ).Box(x=0, y=0, width=10, height=10)
    return made, counts


@pytest.mark.parametrize(
    ("states", "why"),
    [
        (("active", "showing"), "a window claims active"),
        (("focused", "showing"), "nothing claims active, so the focused fallback runs"),
        (("showing",), "nothing claims anything"),
    ],
)
def test_windows_reads_the_desktop_exactly_once(states: tuple[str, ...], why: str) -> None:
    made, counts = provider(states)
    made.windows()
    assert counts["desktop"] == 1, f"walked the desktop {counts['desktop']} times when {why}"


def test_the_focused_fallback_comes_from_the_pass_that_read_the_states() -> None:
    made, _ = provider(("focused", "showing"))
    assert [entry.active for entry in made.windows()] == [True, True]


def test_active_still_wins_over_focused() -> None:
    made, _ = provider(("active", "showing"))
    assert all(entry.active for entry in made.windows())
