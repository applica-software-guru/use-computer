"""macOS: the AXUIElement tree, through pyobjc.

This needs the same Accessibility permission that input synthesis already needs, and the API
reports its absence as an error code rather than by failing loudly -- so the code checks and
raises, instead of returning an empty tree that means "you have it switched off".

It will also act on an application that is not frontmost. That is a genuine advantage and a
genuine footgun: nothing visibly comes forward when it happens.
"""

from __future__ import annotations

from typing import Any

from use_computer.accessibility import roles
from use_computer.accessibility.base import require
from use_computer.errors import PermissionDeniedError
from use_computer.tree import Box, TreeScope, TreeScopeKind, UINode, WindowInfo

#: kAXErrorAPIDisabled -- the process is not trusted for accessibility.
API_DISABLED = -25211

PERMISSION_HINT = (
    "Grant it in System Settings > Privacy & Security > Accessibility, then run this again."
)


class AxProvider:
    """Reads and operates the macOS accessibility tree."""

    name = "ax"

    def __init__(self) -> None:
        self._api = require("ApplicationServices", extra="tree")
        if not self._api.AXIsProcessTrusted():
            raise PermissionDeniedError("Accessibility", PERMISSION_HINT)
        self._index: dict[str, Any] = {}

    # --- reading -----------------------------------------------------------------------------

    def windows(self) -> list[WindowInfo]:
        """The windows of the frontmost application.

        Not every application's: the accessibility API has no way to enumerate processes, and
        the window-server list that would (`CGWindowListCopyWindowInfo`) is a different framework
        and a dependency this does not carry. Said plainly here and in the docs rather than
        quietly returning less than the other platforms do.
        """
        system = self._api.AXUIElementCreateSystemWide()
        app = self._attr(system, "AXFocusedApplication")
        if app is None:
            return []
        focused = self._attr(app, "AXFocusedWindow")
        app_name = self._attr(app, "AXTitle")
        found: list[WindowInfo] = []
        for index, window in enumerate(self._attr(app, "AXWindows") or []):
            title = self._attr(window, "AXTitle")
            found.append(
                WindowInfo(
                    id=f"0/{index}",
                    title=str(title) if title else None,
                    role=roles.ax_role(str(self._attr(window, "AXRole") or "")),
                    app=str(app_name) if app_name else None,
                    pid=None,
                    box=self._box(window),
                    active=bool(focused is not None and window == focused),
                )
            )
        return found

    def snapshot(self, scope: TreeScope, depth: int) -> UINode:
        self._index = {}
        return self._build(self._root_for(scope), "0", depth)

    def _attr(self, element: Any, name: str) -> Any:
        try:
            code, value = self._api.AXUIElementCopyAttributeValue(element, name, None)
        except Exception:
            return None
        if code == API_DISABLED:
            raise PermissionDeniedError("Accessibility", PERMISSION_HINT)
        return value if code == 0 else None

    def _root_for(self, scope: TreeScope) -> Any:
        api = self._api
        system = api.AXUIElementCreateSystemWide()
        if scope.kind is TreeScopeKind.PID and scope.value:
            return api.AXUIElementCreateApplication(int(scope.value))

        app = self._attr(system, "AXFocusedApplication")
        if scope.kind is TreeScopeKind.ALL:
            return app or system
        # A title is resolved to an id above the Protocol, so a provider only ever sees an id.
        if scope.kind is TreeScopeKind.ID and scope.value and app is not None:
            for index, window in enumerate(self._attr(app, "AXWindows") or []):
                if scope.value == f"0/{index}":
                    return window
        focused = self._attr(app, "AXFocusedWindow") if app is not None else None
        return focused or app or system

    def _box(self, element: Any) -> Box:
        api = self._api
        position = self._attr(element, "AXPosition")
        size = self._attr(element, "AXSize")
        if position is None or size is None:
            return Box(x=0, y=0, width=0, height=0)
        try:
            ok_p, point = api.AXValueGetValue(position, api.kAXValueCGPointType, None)
            ok_s, extent = api.AXValueGetValue(size, api.kAXValueCGSizeType, None)
            if not (ok_p and ok_s):
                return Box(x=0, y=0, width=0, height=0)
            return Box(
                x=int(point.x), y=int(point.y), width=int(extent.width), height=int(extent.height)
            )
        except Exception:
            return Box(x=0, y=0, width=0, height=0)

    def _states(self, element: Any) -> tuple[str, ...]:
        found = set()
        if self._attr(element, "AXEnabled"):
            found.add("enabled")
        if self._attr(element, "AXFocused"):
            found.add("focused")
        settable = self._settable(element, "AXFocused")
        if settable:
            found.add("focusable")
        if self._settable(element, "AXValue"):
            found.add("editable")
        box = self._box(element)
        if box.width > 0 and box.height > 0:
            found.add("showing")
        return tuple(sorted(found))

    def _settable(self, element: Any, attribute: str) -> bool:
        try:
            code, settable = self._api.AXUIElementIsAttributeSettable(element, attribute, None)
        except Exception:
            return False
        return bool(code == 0 and settable)

    def _actions(self, element: Any) -> tuple[str, ...]:
        found = set()
        try:
            code, names = self._api.AXUIElementCopyActionNames(element, None)
        except Exception:
            code, names = 1, []
        if code == 0:
            for raw in names or []:
                canonical = roles.ax_action(str(raw))
                if canonical:
                    found.add(canonical)
        if self._settable(element, "AXFocused"):
            found.add(roles.FOCUS)
        if self._settable(element, "AXValue"):
            found.add(roles.SET_VALUE)
        if self._settable(element, "AXSelected"):
            found.add(roles.SELECT)
        return tuple(sorted(found))

    def _value(self, element: Any) -> str | None:
        value = self._attr(element, "AXValue")
        if value is None:
            return None
        if isinstance(value, (str, int, float)):
            return str(value)
        return None

    def _build(self, element: Any, node_id: str, depth: int) -> UINode:
        self._index[node_id] = element
        children: tuple[UINode, ...] = ()
        if depth > 0:
            raw = self._attr(element, "AXChildren") or []
            children = tuple(
                self._build(child, f"{node_id}/{index}", depth - 1)
                for index, child in enumerate(raw)
            )
        title = self._attr(element, "AXTitle") or self._attr(element, "AXDescription")
        return UINode(
            id=node_id,
            role=roles.ax_role(str(self._attr(element, "AXRole") or "")),
            name=str(title) if title else None,
            value=self._value(element),
            states=self._states(element),
            actions=self._actions(element),
            box=self._box(element),
            children=children,
        )

    # --- acting ------------------------------------------------------------------------------

    #: Canonical action -> the AX action that performs it.
    _NAMED = {
        roles.CLICK: "AXPress",
        roles.TOGGLE: "AXPress",
        roles.SHOW_MENU: "AXShowMenu",
        roles.EXPAND: "AXPress",
        roles.COLLAPSE: "AXPress",
    }

    def activate(self, window_id: str) -> bool:
        """macOS windows do accept a raise of their own: AXRaise."""
        element = self._index.get(window_id)
        if element is None:
            return False
        try:
            status = self._api.AXUIElementPerformAction(element, "AXRaise")
        except Exception:
            return False
        return bool(status == 0)

    def perform(self, node_id: str, action: str, value: str | None) -> bool:
        element = self._index.get(node_id)
        if element is None:
            return False

        if action == roles.FOCUS:
            return self._set(element, "AXFocused", True)
        if action == roles.SET_VALUE:
            return self._set(element, "AXValue", value or "")
        if action == roles.SELECT:
            return self._set(element, "AXSelected", True)

        named = self._NAMED.get(action)
        if named is None:
            return False
        try:
            return bool(self._api.AXUIElementPerformAction(element, named) == 0)
        except Exception:
            return False

    def _set(self, element: Any, attribute: str, value: Any) -> bool:
        try:
            return bool(self._api.AXUIElementSetAttributeValue(element, attribute, value) == 0)
        except Exception:
            return False

    def close(self) -> None:
        self._index = {}
