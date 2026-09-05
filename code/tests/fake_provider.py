"""An accessibility provider that answers from a canned tree and records what it was asked to do.

No CI runner has a session bus, a logged-in desktop or an Accessibility grant, so the three
platform providers are unreachable there by construction. Everything worth testing -- pruning,
the budget, id paths, selector resolution, the rungs and the fallback -- sits above them, and
this is what it is tested against.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from use_computer.errors import PermissionDeniedError, UITreeUnavailableError
from use_computer.tree import Box, TreeScope, UINode, WindowInfo


def node(
    node_id: str,
    role: str,
    name: str | None = None,
    *,
    actions: tuple[str, ...] = (),
    states: tuple[str, ...] = ("showing",),
    children: tuple[UINode, ...] = (),
    box: tuple[int, int, int, int] = (0, 0, 10, 10),
    value: str | None = None,
) -> UINode:
    x, y, width, height = box
    return UINode(
        id=node_id,
        role=role,
        name=name,
        value=value,
        states=states,
        actions=actions,
        box=Box(x=x, y=y, width=width, height=height),
        children=children,
    )


def dialog() -> UINode:
    """A small window: a filler that collapses, a text field, and two buttons."""
    return node(
        "0",
        "dialog",
        "Conferma",
        box=(300, 200, 400, 180),
        children=(
            node(
                "0/0",
                "filler",
                children=(
                    node(
                        "0/0/0",
                        "text",
                        "Destinatario",
                        actions=("focus", "set_value"),
                        states=("showing", "focusable", "editable"),
                        box=(320, 240, 200, 24),
                    ),
                ),
            ),
            node(
                "0/1",
                "panel",
                children=(
                    node(
                        "0/1/0",
                        "button",
                        "Invia",
                        actions=("click", "focus"),
                        states=("showing", "focusable", "enabled"),
                        box=(412, 260, 88, 32),
                    ),
                    node(
                        "0/1/1",
                        "button",
                        "Annulla",
                        box=(520, 260, 88, 32),
                    ),
                ),
            ),
        ),
    )


@dataclass
class FakeProvider:
    """Satisfies the AccessibilityProvider Protocol."""

    name: str = "fake"
    root: UINode = field(default_factory=dialog)
    calls: list[tuple[str, str, str | None]] = field(default_factory=list)
    #: Canonical actions the platform will refuse, so the fallback to a coordinate is exercised.
    refuse: frozenset[str] = frozenset()
    raises: Exception | None = None
    snapshots: int = 0
    closed: bool = False
    #: Windows this provider reports, when the default single-window list is not the point.
    window_list: tuple[WindowInfo, ...] | None = None
    #: Whether this platform has a native raise. AT-SPI does not; Windows and macOS do.
    native_raise: bool = False
    activated: list[str] = field(default_factory=list)

    def windows(self) -> list[WindowInfo]:
        if self.raises is not None:
            raise self.raises
        if self.window_list is not None:
            return list(self.window_list)
        return [
            WindowInfo(
                id="0",
                title=self.root.name,
                role=self.root.role,
                app="Fake App",
                pid=4711,
                box=self.root.box,
                active=True,
            )
        ]

    def snapshot(self, scope: TreeScope, depth: int) -> UINode:
        self.snapshots += 1
        if self.raises is not None:
            raise self.raises
        # Honoured, because the real providers honour it and because a tree cut to nothing by the
        # caller's own limit must not be reported as an application that exposes nothing.
        return _trim(self.root, depth)

    def perform(self, node_id: str, action: str, value: str | None) -> bool:
        self.calls.append((node_id, action, value))
        return action not in self.refuse

    def activate(self, window_id: str) -> bool:
        self.activated.append(window_id)
        return self.native_raise

    def close(self) -> None:
        self.closed = True


def _trim(node: UINode, depth: int) -> UINode:
    """`depth 1` is the root alone, as on every platform."""
    if depth <= 1:
        return node.model_copy(update={"children": ()})
    return node.model_copy(
        update={"children": tuple(_trim(child, depth - 1) for child in node.children)}
    )


def unavailable() -> FakeProvider:
    return FakeProvider(raises=UITreeUnavailableError("no provider here."))


def denied() -> FakeProvider:
    return FakeProvider(raises=PermissionDeniedError("Accessibility", "Grant it."))


def empty() -> FakeProvider:
    return FakeProvider(root=node("0", "window", "Canvas", box=(0, 0, 800, 600)))


def window(window_id: str, title: str, *, active: bool = False, app: str = "App") -> WindowInfo:
    """One entry of a window list, for the rules that are about the list rather than the tree."""
    return WindowInfo(
        id=window_id,
        title=title,
        role="window",
        app=app,
        pid=1,
        box=Box(x=0, y=0, width=100, height=100),
        active=active,
    )


__all__: list[str] = [
    "FakeProvider",
    "denied",
    "dialog",
    "empty",
    "node",
    "unavailable",
    "window",
]
