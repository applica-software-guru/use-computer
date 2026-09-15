"""Windows: which window is in front, and an id that still names it a second later.

The provider cannot be constructed here -- UI Automation exists on one of the three platforms
and CI runs on another -- so it is built without ``__init__`` and handed a fake ``uiautomation``
with the same call shape. That is enough to hold the two rules that matter: the mark follows the
window manager rather than a per-window flag, and an id survives everything that reorders the
desktop.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from use_computer.accessibility.uia import UiaProvider
from use_computer.errors import UITreeUnavailableError
from use_computer.tree import TreeScope, TreeScopeKind


class FakeControl:
    """A UI Automation element, reduced to what the provider reads off one."""

    def __init__(
        self,
        name: str,
        *,
        kind: str = "WindowControl",
        pid: int = 1,
        handle: int = 0,
        focused: bool = False,
        children: list[FakeControl] | None = None,
    ) -> None:
        self.Name = name
        self.ControlTypeName = kind
        self.ProcessId = pid
        self.NativeWindowHandle = handle
        self.HasKeyboardFocus = focused
        self.BoundingRectangle = SimpleNamespace(left=0, top=0, right=100, bottom=50)
        self._children = children or []

    def GetChildren(self) -> list[FakeControl]:
        return list(self._children)


def desktop(children: list[FakeControl], foreground: int = 0) -> UiaProvider:
    root = FakeControl("Desktop", kind="PaneControl", children=children)
    made = object.__new__(UiaProvider)
    # The provider holds the binding as a module; here it is a stand-in with the same call shape.
    made._auto = SimpleNamespace(  # type: ignore[assignment]
        GetRootControl=lambda: root,
        GetForegroundWindow=lambda: foreground,
        GetFocusedControl=lambda: None,
    )
    made._index = {}
    return made


def a_desktop(foreground: int = 0) -> UiaProvider:
    return desktop(
        [
            FakeControl("Calculator", pid=100, handle=30),
            FakeControl("Notepad", pid=200, handle=10),
            FakeControl("Taskbar", kind="PaneControl", pid=300, handle=20),
        ],
        foreground=foreground,
    )


def test_the_window_in_front_carries_the_mark_though_its_own_flag_says_otherwise() -> None:
    """Measured on Calculator: the foreground window reports HasKeyboardFocus false.

    Every XAML application does -- the focus sits on a descendant -- so the flag alone marked
    nothing at all, and `--window focused` had no window to answer with.
    """
    listed = a_desktop(foreground=30).windows()
    assert [entry.title for entry in listed if entry.active] == ["Calculator"]


def test_the_per_window_flag_is_the_fallback_when_there_is_no_foreground() -> None:
    made = desktop(
        [
            FakeControl("Calculator", handle=30),
            FakeControl("Notepad", handle=10, focused=True),
        ],
        foreground=0,
    )
    assert [entry.title for entry in made.windows() if entry.active] == ["Notepad"]


def test_nothing_is_marked_when_the_window_in_front_is_not_one_of_these() -> None:
    assert [entry.active for entry in a_desktop(foreground=999).windows()] == [False] * 3


def test_an_id_does_not_move_when_the_z_order_does() -> None:
    """`activate` reorders the desktop itself, so an id that counted positions named the window
    that had just been pushed down -- reported as activated, read from, clicked."""
    before = a_desktop(foreground=10).windows()
    shuffled = desktop(
        [
            FakeControl("Taskbar", kind="PaneControl", pid=300, handle=20),
            FakeControl("Calculator", pid=100, handle=30),
            FakeControl("Notepad", pid=200, handle=10),
        ],
        foreground=30,
    ).windows()
    assert {entry.id: entry.title for entry in before} == {
        entry.id: entry.title for entry in shuffled
    }


def test_an_id_does_not_move_when_another_window_opens() -> None:
    before = a_desktop().windows()
    after = desktop(
        [
            FakeControl("Save changes?", pid=100, handle=40),
            FakeControl("Calculator", pid=100, handle=30),
            FakeControl("Notepad", pid=200, handle=10),
            FakeControl("Taskbar", kind="PaneControl", pid=300, handle=20),
        ]
    ).windows()
    named = {entry.id: entry.title for entry in after}
    assert all(named[entry.id] == entry.title for entry in before)


def test_the_listing_reads_the_same_way_twice() -> None:
    """Z-order is what the platform hands back; a fixed order is what a caller can diff."""
    assert [entry.title for entry in a_desktop().windows()] == [
        "Notepad",
        "Taskbar",
        "Calculator",
    ]


def test_an_id_from_windows_resolves_back_to_the_window_it_named() -> None:
    made = a_desktop(foreground=30)
    for entry in made.windows():
        root = made.snapshot(TreeScope(kind=TreeScopeKind.ID, value=entry.id), depth=0)
        assert root.name == entry.title, f"{entry.id} resolved to {root.name!r}"


def test_a_pid_still_resolves_to_its_window() -> None:
    made = a_desktop()
    root = made.snapshot(TreeScope(kind=TreeScopeKind.PID, value="200"), depth=0)
    assert root.name == "Notepad"


@pytest.mark.parametrize("wanted", ["0/99", "0", "0/30/0", "0/x"])
def test_an_id_that_names_no_window_is_an_error_and_not_a_neighbour(wanted: str) -> None:
    made = a_desktop()
    with pytest.raises(UITreeUnavailableError, match="no window matches"):
        made.snapshot(TreeScope(kind=TreeScopeKind.ID, value=wanted), depth=0)


def test_a_child_with_no_handle_is_left_out_because_no_id_would_name_it_twice() -> None:
    made = desktop([FakeControl("Calculator", handle=30), FakeControl("nameless", handle=0)])
    assert [entry.title for entry in made.windows()] == ["Calculator"]


def test_one_window_that_will_not_answer_costs_its_own_entry_never_the_listing() -> None:
    broken: Any = FakeControl("broken", handle=5)
    del broken.ProcessId
    made = desktop([broken, FakeControl("Calculator", handle=30)])
    assert [entry.title for entry in made.windows()] == ["Calculator"]
