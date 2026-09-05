"""Windows: the UI Automation tree, through ``uiautomation``.

Pure Python over comtypes, so there is no compiler in the way -- which is why it is preferred
over the alternatives.
"""

from __future__ import annotations

from typing import Any

from use_computer.accessibility import roles
from use_computer.accessibility.base import require
from use_computer.errors import UITreeUnavailableError
from use_computer.tree import Box, TreeScope, TreeScopeKind, UINode, WindowInfo


class UiaProvider:
    """Reads and operates the UI Automation tree of the local desktop."""

    name = "uia"

    def __init__(self) -> None:
        self._auto = require("uiautomation", extra="tree")
        self._index: dict[str, Any] = {}

    # --- reading -----------------------------------------------------------------------------

    def windows(self) -> list[WindowInfo]:
        found: list[WindowInfo] = []
        for index, window in enumerate(self._auto.GetRootControl().GetChildren()):
            try:
                found.append(
                    WindowInfo(
                        id=f"0/{index}",
                        title=window.Name or None,
                        role=roles.uia_role(window.ControlTypeName or ""),
                        # UI Automation reports the process id and not its name, and turning one
                        # into the other needs an API this package does not carry. Left empty
                        # rather than guessed; the pid still tells two windows apart.
                        app=None,
                        pid=int(window.ProcessId),
                        box=self._box(window),
                        active=bool(window.HasKeyboardFocus),
                    )
                )
            except Exception:
                continue
        return found

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
        for index, window in enumerate(root.GetChildren()):
            if scope.kind is TreeScopeKind.ID and scope.value == f"0/{index}":
                return window
            if scope.kind is TreeScopeKind.PID and str(window.ProcessId) == scope.value:
                return window
        raise UITreeUnavailableError(f"no window matches {scope.value!r}.")

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
