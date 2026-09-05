"""Linux: the AT-SPI 2 tree, through PyGObject.

There is no ``pyatspi`` on PyPI. The bindings ship as a distro package -- ``gir1.2-atspi-2.0``,
plus ``python3-pyatspi`` on Debian and Ubuntu -- and PyGObject reaches them through GObject
Introspection, so ``pip install`` alone cannot finish the job here. Both halves are named in the
error, because the agent reading it is the one that has to get unstuck.
"""

from __future__ import annotations

import sys
from contextlib import suppress
from glob import glob
from pathlib import Path
from typing import Any

from use_computer.accessibility import roles
from use_computer.accessibility.base import require
from use_computer.errors import UITreeUnavailableError, UseComputerError
from use_computer.tree import Box, TreeScope, TreeScopeKind, UINode, WindowInfo

#: Where a distro puts PyGObject. The compiled part carries the Python version it was built for,
#: which is the fact that decides whether any of the advice below will work.
DISTRO_PATHS = (
    "/usr/lib/python3/dist-packages/gi",
    "/usr/lib/python3*/site-packages/gi",
    "/usr/lib64/python3*/site-packages/gi",
)

#: What actually gets AT-SPI working on Linux. Not an extra: PyGObject has no Linux wheel, so
#: asking pip for it builds from source and fails. The distro has it; a virtualenv only has to be
#: allowed to see it -- and has to be the same Python it was built for.
INSTALL_HINT = (
    "install the distro packages and let the virtualenv see them: "
    "`sudo apt install python3-gi gir1.2-atspi-2.0` then "
    "`python3 -m venv --system-site-packages .venv`"
)


def distro_python() -> str | None:
    """The Python version the installed PyGObject was built for, or None if none is installed.

    `gi` is a compiled extension and its shared object names the version:
    ``_gi.cpython-310-x86_64-linux-gnu.so``. Reading it is what turns "install these packages"
    -- advice that is useless to someone who already has them -- into the reason it is not working.
    """
    for pattern in DISTRO_PATHS:
        for directory in glob(pattern):
            for shared_object in glob(f"{directory}/_gi.cpython-*.so"):
                tag = Path(shared_object).name.split(".")[1]  # cpython-310-x86_64-linux-gnu
                digits = tag.split("-")[1] if "-" in tag else ""
                if digits.isdigit() and len(digits) >= 2:
                    return f"{digits[0]}.{digits[1:]}"
    return None


def system_hint() -> str:
    """Say what is actually wrong here, not what is usually wrong."""
    built_for = distro_python()
    running = f"{sys.version_info.major}.{sys.version_info.minor}"
    if built_for is None:
        return INSTALL_HINT
    if built_for == running:
        # It is installed for this interpreter, so the virtualenv simply cannot see it.
        return (
            f"the distro's PyGObject is installed for Python {built_for}, but this environment "
            "cannot see it. Recreate it with: "
            f"`python{built_for} -m venv --system-site-packages .venv`"
        )
    return (
        f"the distro's PyGObject is built for Python {built_for}, but this interpreter is "
        f"{running}, so --system-site-packages would expose a module it cannot import. Create the "
        f"environment with the matching interpreter: "
        f"`python{built_for} -m venv --system-site-packages .venv`"
    )

#: Milliseconds any single AT-SPI call may take. AT-SPI is D-Bus, and every property read is a
#: round trip into another process: one application that is wedged, or merely slow to answer,
#: otherwise stalls the whole snapshot until the default timeout of many seconds. A short bound
#: with per-application recovery turns "the desktop hung" into "that one app was skipped".
CALL_TIMEOUT_MS = 800

BUS_HINT = (
    "The accessibility bus does not appear to be running, so applications expose nothing over "
    "AT-SPI. Enable it with: gsettings set org.gnome.desktop.interface toolkit-accessibility true"
)


class AtspiProvider:
    """Reads and operates the AT-SPI tree of the local display."""

    name = "atspi"

    def __init__(self) -> None:
        gi = require("gi", extra=None, system=system_hint())
        try:
            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi  # noqa: PLC0415 - deliberately not at module import
        except (ImportError, ValueError) as exc:
            raise UITreeUnavailableError(
                "the Atspi typelib is not installed.", system=system_hint()
            ) from exc
        # GLib talks over our stderr from inside the C library, about a stale socket it then
        # recovers from. An agent reading stderr to understand a failure would see it immediately
        # before output that is entirely fine. A log handler, not a redirect of fd 2: a redirect
        # would swallow our own errors during the same window.
        with suppress(Exception):
            from gi.repository import GLib  # noqa: PLC0415

            GLib.log_set_handler(
                "dbind",
                GLib.LogLevelFlags.LEVEL_MASK
                | GLib.LogLevelFlags.FLAG_FATAL
                | GLib.LogLevelFlags.FLAG_RECURSION,
                lambda *_: None,
                None,
            )
        self._atspi = Atspi
        # Older bindings do not expose it; the default timeout then applies.
        with suppress(Exception):
            Atspi.set_timeout(CALL_TIMEOUT_MS, CALL_TIMEOUT_MS)
        #: node id -> accessible, filled by the last snapshot. `perform` looks up here, and the
        #: runner always snapshots immediately before acting, so the mapping is never stale.
        self._index: dict[str, Any] = {}

    # --- reading -----------------------------------------------------------------------------

    def windows(self) -> list[WindowInfo]:
        return [info for info, _ in self._window_pairs()]

    def _window_pairs(self) -> list[tuple[WindowInfo, Any]]:
        """Every window, with the accessible it describes, so a match can be acted on."""
        desktop = self._desktop()
        found: list[tuple[WindowInfo, Any]] = []
        for app_index, app in enumerate(self._children(desktop)):
            try:
                pid = self._pid(app)
                app_name = app.get_name() or None
                for index, window in enumerate(self._children(app)):
                    states = set(self._states(window))
                    found.append(
                        (
                            WindowInfo(
                                id=f"0/{app_index}/{index}",
                                title=window.get_name() or None,
                                role=roles.atspi_role(window.get_role_name() or ""),
                                app=app_name,
                                pid=pid if pid > 0 else None,
                                box=self._box(window),
                                active="active" in states or "focused" in states,
                            ),
                            window,
                        )
                    )
            except Exception:
                # One client that will not answer costs its own windows, never the list.
                continue
        return found

    def snapshot(self, scope: TreeScope, depth: int) -> UINode:
        self._index = {}
        try:
            root = self._root_for(scope)
            return self._build(root, "0", depth)
        except UseComputerError:
            # Our own errors already say what to do. Relabelling one as "AT-SPI did not answer"
            # would hide an ambiguous window behind a transport failure it has nothing to do with.
            raise
        except Exception as exc:
            # A GLib/dbind failure is not a Python error the caller can act on. Turning it into
            # the tool's own vocabulary is what lets `tree` keep its promise: either structure,
            # or a stated reason and the screenshot to fall back to.
            raise UITreeUnavailableError(
                f"AT-SPI did not answer: {exc}. An application on this desktop is not responding "
                "on the accessibility bus; try --window with a title, or use a screenshot."
            ) from exc

    def _desktop(self) -> Any:
        try:
            desktop = self._atspi.get_desktop(0)
        except Exception as exc:  # the bus is not there at all
            raise UITreeUnavailableError(BUS_HINT) from exc
        if desktop is None or desktop.get_child_count() == 0:
            # An empty tree here means "you have it switched off", which is the worst possible
            # answer to return as an empty result.
            raise UITreeUnavailableError(BUS_HINT)
        return desktop

    def _root_for(self, scope: TreeScope) -> Any:
        desktop = self._desktop()
        if scope.kind is TreeScopeKind.ALL:
            return desktop

        if scope.kind is TreeScopeKind.ID and scope.value:
            return self._by_path(desktop, scope.value)

        for app in self._children(desktop):
            # One unresponsive application must not cost the whole snapshot. Skipping it loses
            # that application; letting it raise loses the desktop.
            try:
                if scope.kind is TreeScopeKind.PID and str(self._pid(app)) != scope.value:
                    continue
                for window in self._children(app):
                    if scope.kind is TreeScopeKind.FOCUSED and self._is_active(window):
                        return window
                    if scope.kind is TreeScopeKind.PID:
                        return window
            except Exception:
                continue

        if scope.kind is TreeScopeKind.FOCUSED:
            # Nothing claimed to be active. The desktop is a worse answer than a stated reason,
            # because it looks like a tree and is not the window the agent meant.
            raise UITreeUnavailableError(
                "no window reports itself as active. Name one with --window TITLE or @PID, or "
                "use --window all."
            )
        raise UITreeUnavailableError(f"no window matches {scope.value!r}.")

    def _by_path(self, desktop: Any, path: str) -> Any:
        """The window an id names. Ids are index paths, so this is a walk."""
        node = desktop
        for step in path.split("/")[1:]:
            children = self._children(node)
            index = int(step) if step.isdigit() else -1
            if not 0 <= index < len(children):
                raise UITreeUnavailableError(f"no window at {path!r}.")
            node = children[index]
        return node

    def _children(self, obj: Any) -> list[Any]:
        try:
            total = obj.get_child_count()
        except Exception:
            return []
        out = []
        for index in range(total):
            try:
                child = obj.get_child_at_index(index)
            except Exception:
                continue
            if child is not None:
                out.append(child)
        return out

    def _pid(self, obj: Any) -> int:
        try:
            return int(obj.get_process_id())
        except Exception:
            return -1

    def _states(self, obj: Any) -> tuple[str, ...]:
        try:
            state_set = obj.get_state_set()
        except Exception:
            return ()
        names = []
        for value in state_set.get_states():
            name = getattr(value, "value_nick", None) or str(value)
            names.append(roles.state(name))
        return tuple(sorted(set(names)))

    def _is_active(self, window: Any) -> bool:
        states = set(self._states(window))
        return "active" in states or "focused" in states

    #: AT-SPI reports an element that is not currently rendered at INT_MIN with a 1x1 size --
    #: the items of a closed menu, for instance. That is a sentinel, not a position, and letting
    #: it through would hand an agent a coordinate that clicks somewhere absurd.
    UNPOSITIONED = -(2**31)

    def _box(self, obj: Any) -> Box:
        try:
            component = obj.get_component_iface()
            extents = component.get_extents(self._atspi.CoordType.SCREEN)
        except Exception:
            return Box(x=0, y=0, width=0, height=0)
        if extents.x <= self.UNPOSITIONED or extents.y <= self.UNPOSITIONED:
            return Box(x=0, y=0, width=0, height=0)
        return Box(x=extents.x, y=extents.y, width=extents.width, height=extents.height)

    def _value(self, obj: Any) -> str | None:
        try:
            text = obj.get_text_iface()
            if text is not None:
                return str(text.get_text(0, -1))
        except Exception:
            pass
        try:
            value = obj.get_value_iface()
            if value is not None:
                return str(value.get_current_value())
        except Exception:
            pass
        return None

    def _actions(self, obj: Any) -> tuple[str, ...]:
        found: set[str] = set()
        try:
            action = obj.get_action_iface()
            if action is not None:
                for index in range(action.get_n_actions()):
                    canonical = roles.atspi_action(action.get_action_name(index) or "")
                    if canonical:
                        found.add(canonical)
        except Exception:
            pass

        states = set(self._states(obj))
        if "focusable" in states:
            found.add(roles.FOCUS)
        if "editable" in states:
            found.add(roles.SET_VALUE)
        if "selectable" in states:
            found.add(roles.SELECT)
        if "expandable" in states:
            found.update({roles.EXPAND, roles.COLLAPSE})
        return tuple(sorted(found))

    def _build(self, obj: Any, node_id: str, depth: int) -> UINode:
        self._index[node_id] = obj
        children: tuple[UINode, ...] = ()
        if depth > 0:
            built = []
            for index, child in enumerate(self._children(obj)):
                try:
                    built.append(self._build(child, f"{node_id}/{index}", depth - 1))
                except Exception:
                    # One client that will not answer on the bus costs its own subtree, not the
                    # whole desktop. The guard is per child, not around the loop: around it, one
                    # failure would still take every sibling after it.
                    continue
            children = tuple(built)
        return UINode(
            id=node_id,
            role=roles.atspi_role(obj.get_role_name() or ""),
            name=obj.get_name() or None,
            value=self._value(obj),
            states=self._states(obj),
            actions=self._actions(obj),
            box=self._box(obj),
            children=children,
        )

    # --- acting ------------------------------------------------------------------------------

    def perform(self, node_id: str, action: str, value: str | None) -> bool:
        obj = self._index.get(node_id)
        if obj is None:
            return False

        if action == roles.FOCUS:
            component = obj.get_component_iface()
            return bool(component is not None and component.grab_focus())

        if action == roles.SET_VALUE:
            editable = obj.get_editable_text_iface()
            if editable is None:
                return False
            return bool(editable.set_text_contents(value or ""))

        if action == roles.SELECT:
            parent = obj.get_parent()
            selection = parent.get_selection_iface() if parent is not None else None
            if selection is None:
                return self._do_named(obj, action)
            return bool(selection.select_child(obj.get_index_in_parent()))

        return self._do_named(obj, action)

    def _do_named(self, obj: Any, action: str) -> bool:
        """Run whichever toolkit-named action maps onto the canonical one we were asked for."""
        interface = obj.get_action_iface()
        if interface is None:
            return False
        for index in range(interface.get_n_actions()):
            if roles.atspi_action(interface.get_action_name(index) or "") == action:
                return bool(interface.do_action(index))
        return False

    def close(self) -> None:
        self._index = {}

