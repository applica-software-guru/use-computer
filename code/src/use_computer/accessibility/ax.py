"""macOS: the AXUIElement tree, through pyobjc.

This needs the same Accessibility permission that input synthesis already needs, and the API
reports its absence as an error code rather than by failing loudly -- so the code checks and
raises, instead of returning an empty tree that means "you have it switched off".

It will also act on an application that is not frontmost. That is a genuine advantage and a
genuine footgun: nothing visibly comes forward when it happens.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any, NamedTuple

from use_computer.accessibility import roles
from use_computer.accessibility.base import require
from use_computer.errors import (
    PermissionDeniedError,
    UITreeUnavailableError,
    UseComputerError,
)
from use_computer.tree import (
    ActiveWindow,
    Box,
    TreeScope,
    TreeScopeKind,
    UINode,
    WindowInfo,
)

#: kAXErrorAPIDisabled -- the process is not trusted for accessibility.
API_DISABLED = -25211

PERMISSION_HINT = (
    "Grant it in System Settings > Privacy & Security > Accessibility, then run this again."
)

#: Seconds any single AX call may take. Every one of them is IPC into another process, and a
#: listing now asks every application on the desktop: one wedged application would otherwise
#: stall the whole list behind a default timeout of many seconds. A short bound with
#: per-application recovery is what turns "the desktop hung" into "that one app was skipped".
CALL_TIMEOUT = 0.8

#: The role of the root that ``--window all`` hangs the applications under. macOS has no desktop
#: element to read one from, so it is named here rather than left to a platform string.
DESKTOP_ROLE = "desktop"


class Application(NamedTuple):
    """One running application that can have a window: what AX needs, and what a window reports."""

    element: Any
    pid: int
    name: str | None


class AxProvider:
    """Reads and operates the macOS accessibility tree."""

    name = "ax"

    def __init__(self) -> None:
        self._api = require("ApplicationServices", extra="tree")
        if not self._api.AXIsProcessTrusted():
            raise PermissionDeniedError("Accessibility", PERMISSION_HINT)
        # NSWorkspace, for the one thing the accessibility API cannot do: name the running
        # processes. It ships in pyobjc-framework-Cocoa, which pyobjc-framework-ApplicationServices
        # already depends on, so the `tree` extra installs it and there is no new dependency here.
        self._appkit = require("AppKit", extra="tree")
        self._index: dict[str, Any] = {}

    # --- reading -----------------------------------------------------------------------------

    def windows(self) -> list[WindowInfo]:
        """What is open, across every application on the desktop.

        **It reads the desktop once**, and everything a caller needs about a window comes out of
        that pass, including the mark that says which one ``--window focused`` resolves to.
        """
        front = self._frontmost()
        found: list[WindowInfo] = []
        for app_index, application in enumerate(self._applications()):
            try:
                # `active` here means "the focused window of the application that is in front",
                # which is one window on the whole desktop. Every other application has a focused
                # window too and none of them is it, so only the frontmost one is asked -- asking
                # each would mark several, which is exactly the answer BUG-010 removed.
                focused = (
                    self._attr(application.element, "AXFocusedWindow")
                    if application.pid == front
                    else None
                )
                windows = self._attr(application.element, "AXWindows") or []
                for index, window in enumerate(windows):
                    title = self._attr(window, "AXTitle")
                    found.append(
                        WindowInfo(
                            id=f"0/{app_index}/{index}",
                            title=str(title) if title else None,
                            role=roles.ax_role(str(self._attr(window, "AXRole") or "")),
                            app=application.name,
                            pid=application.pid,
                            box=self._box(window),
                            active=bool(focused is not None and window == focused),
                        )
                    )
            except UseComputerError:
                # A revoked permission is not "that app is quiet". It says what to do; pass it on.
                raise
            except Exception:
                # One application that will not answer costs its own windows, never the list.
                continue
        return found

    def _applications(self) -> list[Application]:
        """Every application that can have a window, in an order two calls agree on.

        The accessibility API cannot enumerate processes -- ``AXUIElementCreateSystemWide`` has no
        children, and an AX element exists only for a pid you already know. NSWorkspace knows
        them, so the list comes from there and each pid is turned into an AX element. Reading only
        the frontmost application, which is all AX alone can offer, answered "what is open?" with
        the terminal that ran the command.

        Sorted by pid rather than left in NSWorkspace's own undocumented order: an id is an index
        into this list and has to mean the same window to the `tree` call that follows the
        `windows` call. Pids only grow, so an application started between the two lands at the end
        instead of shifting every index below it.
        """
        workspace = self._appkit.NSWorkspace.sharedWorkspace()
        prohibited = self._appkit.NSApplicationActivationPolicyProhibited
        found: list[Application] = []
        for application in workspace.runningApplications() or []:
            try:
                if application.activationPolicy() == prohibited:
                    # Apple's own definition of that policy is "may not create windows", so this
                    # loses nothing and saves a round trip per background daemon -- which is half
                    # of what is running on an ordinary Mac.
                    continue
                pid = int(application.processIdentifier())
                name = application.localizedName()
                found.append(
                    Application(self._application(pid), pid, str(name) if name else None)
                )
            except Exception:
                continue
        return sorted(found, key=lambda entry: entry.pid)

    def _application(self, pid: int) -> Any:
        """The AX element for a pid, bounded so one wedged application cannot stall a listing."""
        element = self._api.AXUIElementCreateApplication(pid)
        # Older bindings do not expose it, and then the default bound applies.
        with suppress(Exception):
            self._api.AXUIElementSetMessagingTimeout(element, CALL_TIMEOUT)
        return element

    def _frontmost(self) -> int | None:
        """The pid of the application in front, as the window server has it.

        This is the whole of `active`: AX reports a focused window per *application*, and it is
        the frontmost application that turns one of them into the single answer `--window focused`
        needs. ``None`` means nothing could be determined, and then no window is marked rather
        than all of them.
        """
        try:
            application = self._appkit.NSWorkspace.sharedWorkspace().frontmostApplication()
        except Exception:
            return None
        return int(application.processIdentifier()) if application is not None else None

    def snapshot(self, scope: TreeScope, depth: int) -> UINode:
        self._index = {}
        if scope.kind is TreeScopeKind.ALL:
            return self._desktop(depth)
        return self._build(self._root_for(scope), "0", depth)

    def _desktop(self, depth: int) -> UINode:
        """Every application, under a root of our own.

        ``--window all`` means every window, and on the other two platforms a real element holds
        the applications: the AT-SPI desktop, the UIA root. macOS has neither, so the root is
        synthesised and the applications hang under it -- which also makes an id here the same
        shape it has on Linux, ``0/APP/WINDOW/...``, the path `windows` already reports.

        Measured on one desktop at the default depth of 20: an unpruned walk of 8,629 nodes in
        9.2 s, reported as 257 after pruning, and most of the difference is menu bars. That is
        why the docs pair ``--window all`` with a shallow ``--depth``.
        """
        children: tuple[UINode, ...] = ()
        if depth > 0:
            children = tuple(
                self._build(application.element, f"0/{index}", depth - 1)
                for index, application in enumerate(self._applications())
            )
        return UINode(
            id="0",
            role=DESKTOP_ROLE,
            box=Box(x=0, y=0, width=0, height=0),
            children=children,
        )

    def _attr(self, element: Any, name: str) -> Any:
        try:
            code, value = self._api.AXUIElementCopyAttributeValue(element, name, None)
        except Exception:
            return None
        # kAXErrorAPIDisabled is the answer a *process* gives as well as the session: measured on
        # this desktop, `ChatGPTHelper` returns it for AXWindows while the grant is in place. So
        # the process that can actually say whether accessibility is off is asked, rather than
        # letting one helper turn "that app does not answer" into "you have it switched off" --
        # which, now that every application is asked, lost the whole listing to one of them.
        if code == API_DISABLED and not self._api.AXIsProcessTrusted():
            raise PermissionDeniedError("Accessibility", PERMISSION_HINT)
        return value if code == 0 else None

    def _root_for(self, scope: TreeScope) -> Any:
        if scope.kind is TreeScopeKind.PID and scope.value:
            return self._application(int(scope.value))
        # A title is resolved to an id above the Protocol, so a provider only ever sees an id.
        if scope.kind is TreeScopeKind.ID and scope.value:
            return self._by_path(scope.value)

        system = self._api.AXUIElementCreateSystemWide()
        app = self._attr(system, "AXFocusedApplication")
        focused = self._attr(app, "AXFocusedWindow") if app is not None else None
        return focused or app or system

    def _by_path(self, path: str) -> Any:
        """The window an id from `windows` names. An id is an index path, so this is a walk.

        The leading ``0`` is the desktop root, which macOS has no element for, so the walk starts
        at the application list the same id was numbered against.
        """
        steps = path.split("/")[1:]
        if len(steps) != 2 or not all(step.isdigit() for step in steps):
            raise UITreeUnavailableError(f"no window at {path!r}.")
        app_index, window_index = (int(step) for step in steps)
        applications = self._applications()
        if not 0 <= app_index < len(applications):
            raise UITreeUnavailableError(f"no window at {path!r}.")
        windows = self._attr(applications[app_index].element, "AXWindows") or []
        if not 0 <= window_index < len(windows):
            raise UITreeUnavailableError(f"no window at {path!r}.")
        return windows[window_index]

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

    def active_window(self) -> ActiveWindow | None:
        """Nothing to add: `windows` already marks one window, and only one.

        The flag is not a per-application one here -- it is the focused window *of the frontmost
        application*, which is a single window on the desktop. So `mark_active` is handed a
        decision to pass through rather than several claims to arbitrate.
        """
        return None

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
