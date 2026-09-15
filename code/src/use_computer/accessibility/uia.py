"""Windows: the UI Automation tree, through ``uiautomation``.

Pure Python over comtypes, so there is no compiler in the way -- which is why it is preferred
over the alternatives.
"""

from __future__ import annotations

from typing import Any

from use_computer.accessibility import roles
from use_computer.accessibility.base import require
from use_computer.errors import UITreeUnavailableError
from use_computer.tree import (
    ActiveWindow,
    Box,
    TreeScope,
    TreeScopeKind,
    UINode,
    WindowInfo,
)


class UiaProvider:
    """Reads and operates the UI Automation tree of the local desktop."""

    name = "uia"

    def __init__(self) -> None:
        self._auto = require("uiautomation", extra="tree")
        self._index: dict[str, Any] = {}

    # --- reading -----------------------------------------------------------------------------

    def windows(self) -> list[WindowInfo]:
        foreground = self._foreground()
        found: list[WindowInfo] = []
        for window, handle in self._top_level():
            try:
                found.append(
                    WindowInfo(
                        id=self._window_id(handle),
                        title=window.Name or None,
                        role=roles.uia_role(window.ControlTypeName or ""),
                        # UI Automation reports the process id and not its name, and turning one
                        # into the other needs an API this package does not carry. Left empty
                        # rather than guessed; the pid still tells two windows apart.
                        app=None,
                        pid=int(window.ProcessId),
                        box=self._box(window),
                        # The window manager's answer, not the window's own flag: a top-level
                        # element reports `HasKeyboardFocus` only while the focus sits on the
                        # element itself, which for every XAML application -- Calculator,
                        # Settings, anything modern -- it never does. The flag marked nothing
                        # active, so `--window focused` had no answer and the default `tree`
                        # reported the whole desktop as having no tree at all.
                        active=handle == foreground if foreground else self._focused(window),
                    )
                )
            except Exception:
                continue
        return found

    def _foreground(self) -> int:
        """The handle of the one window the system says is in front, or 0 if it will not say."""
        try:
            return int(self._auto.GetForegroundWindow())
        except Exception:
            return 0

    def _focused(self, control: Any) -> bool:
        """The per-window flag, kept only as the fallback for a desktop with no foreground."""
        try:
            return bool(control.HasKeyboardFocus)
        except Exception:
            return False

    def snapshot(self, scope: TreeScope, depth: int) -> UINode:
        self._index = {}
        return self._build(self._root_for(scope), "0", depth)

    def _root_for(self, scope: TreeScope) -> Any:
        auto = self._auto
        root = auto.GetRootControl()
        if scope.kind is TreeScopeKind.ALL:
            return root
        if scope.kind is TreeScopeKind.FOCUSED:
            control = auto.GetFocusedControl()
            return self._top_window(control) if control else root
        # A title has already been resolved to an id above the Protocol, so only an id or a pid
        # reaches a provider. Keeping the matching in one place is what stops three platforms
        # drifting apart on it.
        for window, handle in self._top_level():
            if scope.kind is TreeScopeKind.ID and scope.value == self._window_id(handle):
                return window
            if scope.kind is TreeScopeKind.PID and str(window.ProcessId) == scope.value:
                return window
        raise UITreeUnavailableError(f"no window matches {scope.value!r}.")

    def _top_level(self) -> list[tuple[Any, int]]:
        """The desktop's windows, each with its own handle, in a fixed order.

        `GetChildren` hands them back in Z-order, which changes every time anything comes forward
        -- `activate` itself does -- and a window opening or closing shifts the rest either way.
        An index into that list is therefore an id that names a different window a second later,
        and a caller that reads `windows` and then acts on one of its ids has nothing else to
        check it against: it silently activates, reads or clicks the wrong window. The handle is
        the window's own identity for as long as it exists, so it *is* the id rather than
        something the id is derived from. Ordering by it as well only keeps the listing steady
        between two reads.

        A child with no handle is left out: there is no id that would still name it next time,
        and nothing can be brought forward or read without one.
        """
        try:
            children = self._auto.GetRootControl().GetChildren()
        except Exception:
            return []
        found = [(child, self._handle(child)) for child in children]
        return sorted((pair for pair in found if pair[1]), key=lambda pair: pair[1])

    @staticmethod
    def _window_id(handle: int) -> str:
        return f"0/{handle}"

    def _handle(self, control: Any) -> int:
        try:
            return int(control.NativeWindowHandle)
        except Exception:
            return 0

    def _top_window(self, control: Any) -> Any:
        """Walk up to the window the focused control lives in."""
        node = control
        while node is not None:
            parent = node.GetParentControl()
            if parent is None or parent.ControlTypeName == "PaneControl" and parent.Name == "":
                return node
            if node.ControlTypeName == "WindowControl":
                return node
            node = parent
        return control

    def _states(self, control: Any) -> tuple[str, ...]:
        found = set()
        for attribute, name in (
            ("IsEnabled", "enabled"),
            ("IsKeyboardFocusable", "focusable"),
            ("HasKeyboardFocus", "focused"),
            ("IsOffscreen", "offscreen"),
        ):
            try:
                if bool(getattr(control, attribute)):
                    found.add(name)
            except Exception:
                continue
        if roles.SET_VALUE in self._actions(control):
            found.add("editable")
        return tuple(sorted(found))

    def _box(self, control: Any) -> Box:
        try:
            rect = control.BoundingRectangle
            return Box(
                x=int(rect.left),
                y=int(rect.top),
                width=int(rect.right - rect.left),
                height=int(rect.bottom - rect.top),
            )
        except Exception:
            return Box(x=0, y=0, width=0, height=0)

    def _pattern(self, control: Any, name: str) -> Any:
        getter = getattr(control, f"Get{name}Pattern", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:
            return None

    def _actions(self, control: Any) -> tuple[str, ...]:
        found = {roles.FOCUS}
        if self._pattern(control, "Invoke"):
            found.add(roles.CLICK)
        if self._pattern(control, "Toggle"):
            found.add(roles.TOGGLE)
        if self._pattern(control, "ExpandCollapse"):
            found.update({roles.EXPAND, roles.COLLAPSE})
        if self._pattern(control, "Value"):
            found.add(roles.SET_VALUE)
        if self._pattern(control, "SelectionItem"):
            found.add(roles.SELECT)
        return tuple(sorted(found))

    def _value(self, control: Any) -> str | None:
        pattern = self._pattern(control, "Value")
        if pattern is None:
            return None
        try:
            return str(pattern.Value)
        except Exception:
            return None

    def _build(self, control: Any, node_id: str, depth: int) -> UINode:
        self._index[node_id] = control
        children: tuple[UINode, ...] = ()
        if depth > 0:
            try:
                raw = control.GetChildren()
            except Exception:
                raw = []
            children = tuple(
                self._build(child, f"{node_id}/{index}", depth - 1)
                for index, child in enumerate(raw)
            )
        return UINode(
            id=node_id,
            role=roles.uia_role(control.ControlTypeName or ""),
            name=control.Name or None,
            value=self._value(control),
            states=self._states(control),
            actions=self._actions(control),
            box=self._box(control),
            children=children,
        )

    # --- acting ------------------------------------------------------------------------------

    def active_window(self) -> ActiveWindow | None:
        """`windows` already asks the window manager itself, so there is no hint left to add."""
        return None

    def activate(self, window_id: str) -> bool:
        """Windows has a native raise: `SetActive` on the top-level control."""
        control = self._index.get(window_id)
        if control is None:
            return False
        try:
            return bool(control.SetActive())
        except Exception:
            # Not every control exposes it, and the caller has a working fallback.
            return False

    def perform(self, node_id: str, action: str, value: str | None) -> bool:
        control = self._index.get(node_id)
        if control is None:
            return False
        try:
            if action == roles.FOCUS:
                control.SetFocus()
                return True
            if action == roles.CLICK:
                pattern = self._pattern(control, "Invoke")
                if pattern is None:
                    return False
                pattern.Invoke()
                return True
            if action == roles.TOGGLE:
                pattern = self._pattern(control, "Toggle")
                if pattern is None:
                    return False
                pattern.Toggle()
                return True
            if action in (roles.EXPAND, roles.COLLAPSE):
                pattern = self._pattern(control, "ExpandCollapse")
                if pattern is None:
                    return False
                pattern.Expand() if action == roles.EXPAND else pattern.Collapse()
                return True
            if action == roles.SET_VALUE:
                pattern = self._pattern(control, "Value")
                if pattern is None:
                    return False
                pattern.SetValue(value or "")
                return True
            if action == roles.SELECT:
                pattern = self._pattern(control, "SelectionItem")
                if pattern is None:
                    return False
                pattern.Select()
                return True
        except Exception:
            return False
        # show_menu has no UIA pattern: there is no way to ask for it, so say so rather than
        # synthesising a right-click and calling it the same thing.
        return False

    def close(self) -> None:
        self._index = {}
