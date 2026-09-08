"""macOS: `windows` answers for the whole desktop, not for the application in front.

The provider cannot be constructed here -- no CI runner has an Accessibility grant, and two of
the three platforms cannot be exercised on any one machine at all. So it is built without
`__init__` and handed a fake AX API and a fake NSWorkspace, which is enough to hold the rules
that matter: every application is asked, exactly one window carries the mark, one wedged
application costs only its own windows, and an id resolves back to the window it named.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from use_computer.accessibility.ax import API_DISABLED, CALL_TIMEOUT, AxProvider
from use_computer.errors import PermissionDeniedError, UITreeUnavailableError
from use_computer.tree import TreeScope, TreeScopeKind

REGULAR = 0
ACCESSORY = 1
PROHIBITED = 2


class FakeElement:
    """An AX element: a bag of attributes, and whether it answers at all."""

    def __init__(self, attributes: dict[str, Any] | None = None, *, wedged: bool = False) -> None:
        self.attributes: dict[str, Any] = attributes or {}
        self.wedged = wedged
        self.timeout: float | None = None
        #: Attributes this element answers kAXErrorAPIDisabled for, as a helper process does.
        self.disabled: set[str] = set()


def a_window(title: str) -> FakeElement:
    return FakeElement(
        {
            "AXTitle": title,
            "AXRole": "AXWindow",
            "AXPosition": ("point", 10, 20),
            "AXSize": ("size", 100, 50),
        }
    )


class FakeAx:
    """Enough of the AX C API to read attributes, reach an application by pid, and bound a call."""

    kAXValueCGPointType = "point"
    kAXValueCGSizeType = "size"

    def __init__(self, applications: dict[int, FakeElement]) -> None:
        self.applications = applications
        self.asked: list[int] = []
        self.trusted = True

    def AXIsProcessTrusted(self) -> bool:
        return self.trusted

    def AXUIElementCreateApplication(self, pid: int) -> FakeElement:
        self.asked.append(int(pid))
        return self.applications.get(int(pid), FakeElement())

    def AXUIElementCreateSystemWide(self) -> FakeElement:
        return FakeElement()

    def AXUIElementSetMessagingTimeout(self, element: FakeElement, seconds: float) -> int:
        element.timeout = seconds
        return 0

    def AXUIElementCopyAttributeValue(
        self, element: FakeElement, name: str, _: None
    ) -> tuple[int, Any]:
        if element.wedged:
            raise RuntimeError("this application is not answering")
        if name in element.disabled:
            return API_DISABLED, None
        if name in element.attributes:
            return 0, element.attributes[name]
        return -25205, None  # kAXErrorAttributeUnsupported

    def AXUIElementIsAttributeSettable(
        self, element: FakeElement, name: str, _: None
    ) -> tuple[int, bool]:
        return 0, False

    def AXUIElementCopyActionNames(self, element: FakeElement, _: None) -> tuple[int, list[str]]:
        return 0, []

    def AXValueGetValue(self, value: Any, kind: str, _: None) -> tuple[bool, Any]:
        if not isinstance(value, tuple) or value[0] != kind:
            return False, None
        if kind == "point":
            return True, SimpleNamespace(x=value[1], y=value[2])
        return True, SimpleNamespace(width=value[1], height=value[2])


def fake_appkit(running: list[Any], front: Any | None) -> Any:
    """NSWorkspace, reduced to the two questions the provider asks it."""
    return SimpleNamespace(
        NSApplicationActivationPolicyProhibited=PROHIBITED,
        NSWorkspace=SimpleNamespace(
            sharedWorkspace=lambda: SimpleNamespace(
                runningApplications=lambda: running,
                frontmostApplication=lambda: front,
            )
        ),
    )


def running(pid: int, name: str, policy: int = REGULAR) -> Any:
    return SimpleNamespace(
        processIdentifier=lambda: pid,
        localizedName=lambda: name,
        activationPolicy=lambda: policy,
    )


def desktop(
    applications: list[tuple[int, str, int, list[FakeElement]]],
    front: int | None = None,
    focused: FakeElement | None = None,
) -> tuple[AxProvider, FakeAx]:
    """A provider over the given applications, each with its own windows.

    ``focused`` is what the frontmost application reports as `AXFocusedWindow` -- the one thing
    that decides which window carries the mark.
    """
    elements: dict[int, FakeElement] = {}
    for pid, _, _, windows in applications:
        attributes: dict[str, Any] = {"AXWindows": windows, "AXChildren": windows}
        if pid == front and focused is not None:
            attributes["AXFocusedWindow"] = focused
        elements[pid] = FakeElement(attributes)

    api = FakeAx(elements)
    made = object.__new__(AxProvider)
    # The provider holds the binding as a module; here it is a stand-in with the same call shape.
    made._api = api  # type: ignore[assignment]
    made._appkit = fake_appkit(
        [running(pid, name, policy) for pid, name, policy, _ in applications],
        running(front, "front") if front is not None else None,
    )
    made._index = {}
    return made, api


def two_applications(front: int | None = 200, focused: FakeElement | None = None) -> Any:
    return desktop(
        [
            (100, "Terminal", REGULAR, [a_window("zsh")]),
            (200, "Safari", REGULAR, [a_window("Inbox"), a_window("Docs")]),
        ],
        front=front,
        focused=focused,
    )


def test_windows_lists_every_application_not_only_the_one_in_front() -> None:
    made, _ = two_applications()
    listed = made.windows()
    assert [(entry.app, entry.title) for entry in listed] == [
        ("Terminal", "zsh"),
        ("Safari", "Inbox"),
        ("Safari", "Docs"),
    ]
    assert [entry.id for entry in listed] == ["0/0/0", "0/1/0", "0/1/1"]
    assert [entry.pid for entry in listed] == [100, 200, 200]


def test_the_mark_goes_on_the_focused_window_of_the_application_in_front() -> None:
    docs = a_window("Docs")
    made, _ = desktop(
        [
            (100, "Terminal", REGULAR, [a_window("zsh")]),
            (200, "Safari", REGULAR, [a_window("Inbox"), docs]),
        ],
        front=200,
        focused=docs,
    )
    listed = made.windows()
    assert [entry.active for entry in listed] == [False, False, True]


def test_no_window_is_marked_when_the_application_in_front_cannot_be_named() -> None:
    made, _ = two_applications(front=None)
    assert [entry.active for entry in made.windows()] == [False, False, False]


def test_a_focused_window_in_an_application_that_is_not_in_front_is_not_the_mark() -> None:
    """Every application has one. Only the frontmost application's is the answer."""
    zsh = a_window("zsh")
    made, api = desktop(
        [
            (100, "Terminal", REGULAR, [zsh]),
            (200, "Safari", REGULAR, [a_window("Inbox")]),
        ],
        front=200,
    )
    api.applications[100].attributes["AXFocusedWindow"] = zsh
    assert [entry.active for entry in made.windows()] == [False, False]


def test_one_application_that_will_not_answer_costs_its_own_windows_never_the_list() -> None:
    made, api = two_applications()
    api.applications[100].wedged = True
    assert [entry.title for entry in made.windows()] == ["Inbox", "Docs"]


def test_applications_are_ordered_by_pid_so_an_id_means_one_thing_twice() -> None:
    """NSWorkspace's own order is undocumented, and an id is an index into this list."""
    made, _ = desktop(
        [
            (900, "Safari", REGULAR, [a_window("Inbox")]),
            (100, "Terminal", REGULAR, [a_window("zsh")]),
        ]
    )
    assert [(entry.id, entry.app) for entry in made.windows()] == [
        ("0/0/0", "Terminal"),
        ("0/1/0", "Safari"),
    ]


def test_a_process_that_may_not_create_windows_is_not_asked() -> None:
    made, api = desktop(
        [
            (100, "Terminal", REGULAR, [a_window("zsh")]),
            (300, "com.apple.someagent", PROHIBITED, []),
        ]
    )
    assert [entry.app for entry in made.windows()] == ["Terminal"]
    assert 300 not in api.asked, "a background daemon costs a round trip and has no windows"


def test_a_menu_bar_application_is_asked_because_it_can_still_have_a_window() -> None:
    made, _ = desktop(
        [
            (100, "Terminal", REGULAR, [a_window("zsh")]),
            (200, "Rectangle", ACCESSORY, [a_window("Settings")]),
        ]
    )
    assert [entry.title for entry in made.windows()] == ["zsh", "Settings"]


def test_every_application_is_asked_under_a_call_bound() -> None:
    """One wedged application must not stall the listing behind the default AX timeout."""
    made, api = two_applications()
    made.windows()
    assert [element.timeout for element in api.applications.values()] == [
        CALL_TIMEOUT,
        CALL_TIMEOUT,
    ]


def test_an_id_from_windows_resolves_back_to_the_window_it_named() -> None:
    made, _ = two_applications()
    listed = made.windows()
    for entry in listed:
        root = made.snapshot(TreeScope(kind=TreeScopeKind.ID, value=entry.id), depth=0)
        assert root.name == entry.title, f"{entry.id} resolved to {root.name!r}"


@pytest.mark.parametrize("wanted", ["0/9/0", "0/0/9", "0/0", "0/0/0/0", "0/x/0"])
def test_an_id_that_names_no_window_is_an_error_and_not_a_neighbour(wanted: str) -> None:
    made, _ = two_applications()
    with pytest.raises(UITreeUnavailableError, match="no window at"):
        made.snapshot(TreeScope(kind=TreeScopeKind.ID, value=wanted), depth=0)


def test_window_all_roots_at_a_desktop_that_holds_every_application() -> None:
    made, _ = two_applications()
    root = made.snapshot(TreeScope(kind=TreeScopeKind.ALL), depth=3)
    assert root.id == "0"
    assert root.role == "desktop"
    assert [child.id for child in root.children] == ["0/0", "0/1"]
    assert [window.name for child in root.children for window in child.children] == [
        "zsh",
        "Inbox",
        "Docs",
    ]


def test_one_process_saying_the_api_is_disabled_does_not_speak_for_the_session() -> None:
    """Measured: `ChatGPTHelper` answers kAXErrorAPIDisabled for AXWindows with the grant in place.

    Taken at face value it turned one helper process into "accessibility is switched off" and
    lost every window on the desktop.
    """
    made, api = two_applications()
    api.applications[100].disabled.add("AXWindows")
    assert [entry.title for entry in made.windows()] == ["Inbox", "Docs"]


def test_a_revoked_grant_is_still_reported_and_not_an_empty_desktop() -> None:
    made, api = two_applications()
    api.applications[100].disabled.add("AXWindows")
    api.trusted = False
    with pytest.raises(PermissionDeniedError):
        made.windows()
