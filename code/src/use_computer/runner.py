"""Executing a batch: one backend, many actions, one connection.

Opening a VNC connection dominates the cost of a single action, so the backend is constructed
once and every action runs against it. A single action invoked directly is simply a batch of
one and returns the same shape.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from use_computer import render
from use_computer.accessibility import AccessibilityProvider, create_provider
from use_computer.accessibility import roles as canonical
from use_computer.actions import (
    ELEMENT_ONLY,
    Action,
    ActivateAction,
    DoubleClickAction,
    DragAction,
    KeyAction,
    MouseButton,
    MoveAction,
    RightClickAction,
    ScreenshotAction,
    ScrollAction,
    TreeAction,
    TypeAction,
    WindowsAction,
    resolve,
    selector_of,
    with_default_space,
)
from use_computer.backends import Backend, create_backend
from use_computer.compare import ChangeReport, Screenshot, compare, crop
from use_computer.config import (
    PROJECT_DIR,
    BackendProfile,
    ResolvedConfig,
    Settings,
    default_screenshot_dir,
    ensure_gitignore,
)
from use_computer.config import load as load_config
from use_computer.coordinates import Coordinate, ScreenInfo
from use_computer.errors import (
    ActionFailedError,
    ActionNotSupportedError,
    AmbiguousNodeError,
    AmbiguousWindowError,
    CoordinateSpaceError,
    NodeNotFoundError,
    PermissionDeniedError,
    UITreeUnavailableError,
    UseComputerError,
)
from use_computer.selectors import (
    active_window,
    budget,
    clamp_text,
    count,
    find,
    mark_unexposed,
    notable_states,
    prune,
    resolve_one,
    resolve_window,
    sole_active,
    subtree,
    summarise_offscreen,
    walk,
)
from use_computer.tree import (
    Box,
    NodeSelector,
    OutputFormat,
    TreeReason,
    TreeResult,
    TreeScope,
    TreeScopeKind,
    UINode,
    Via,
    WindowInfo,
    WindowsResult,
)

#: Which canonical accessibility action each member of the action set asks the platform for.
#: `double_click`, `right_click` and `scroll` are deliberately absent: the accessibility API has
#: no double-click, no secondary click and no scroll-by-an-amount, so they address an element to
#: find *where* and then act with a real pointer.
#: Roles for which selecting *is* pressing.
#:
#: `actions` is what the platform will accept, not what will work. GTK's colour swatch advertises
#: `[click,focus,select]`, accepts `click`, returns true from `do_action` and does nothing with it;
#: `select` is the action that carries the widget's meaning. True from an accessibility API means
#: "I invoked that", never "the application did something", and no platform offers the second
#: answer -- so where a role makes the choice obvious, take the action that means it.
SELECTION_ROLES = frozenset(
    {"radio", "listitem", "option", "treeitem", "tab", "menuitem"}
)

#: How long to let a window come forward before a coordinate is sent into it.
ACTIVATE_SETTLE = 0.25

API_ACTION = {
    "click": canonical.CLICK,
    "focus": canonical.FOCUS,
    "toggle": canonical.TOGGLE,
    "expand": canonical.EXPAND,
    "collapse": canonical.COLLAPSE,
    "select": canonical.SELECT,
    "set_value": canonical.SET_VALUE,
    "show_menu": canonical.SHOW_MENU,
}


class Candidate(BaseModel):
    """One of several nodes a selector matched. Enough to choose between them."""

    model_config = ConfigDict(frozen=True)

    id: str
    role: str
    name: str | None = None
    box: Box

    @classmethod
    def of(cls, node: UINode) -> Candidate:
        return cls(id=node.id, role=node.role, name=node.name, box=node.box)


class ErrorInfo(BaseModel):
    """A failure, as the calling agent sees it."""

    model_config = ConfigDict(frozen=True)

    type: str
    message: str
    candidates: tuple[Candidate, ...] | None = Field(
        default=None, description="For an ambiguous selector: what to choose between."
    )
    screenshot: Screenshot | None = Field(
        default=None, description="For a selector that matched nothing: the picture to look at."
    )
    windows: tuple[WindowInfo, ...] | None = Field(
        default=None, description="For an ambiguous window: the ones that matched."
    )

    @classmethod
    def of(cls, exc: BaseException) -> ErrorInfo:
        candidates = None
        screenshot = None
        if isinstance(exc, AmbiguousNodeError):
            # The candidate list is the useful part of this error: it saves the agent a second
            # round trip to work out how to narrow the selector.
            candidates = tuple(Candidate.of(node) for node in exc.candidates)
        if isinstance(exc, NodeNotFoundError):
            screenshot = exc.screenshot
        windows = None
        if isinstance(exc, AmbiguousWindowError):
            windows = tuple(w for w in exc.candidates if isinstance(w, WindowInfo))
        return cls(
            type=type(exc).__name__,
            message=str(exc),
            candidates=candidates,
            screenshot=screenshot,
            windows=windows,
        )


class ActionResult(BaseModel):
    """What one action did. Frozen: once it has run, what it did does not change."""

    model_config = ConfigDict(frozen=True)

    action: Action
    resolved: Coordinate | None = Field(
        default=None, description="The target, in actuation units."
    )
    resolved_from: Coordinate | None = Field(
        default=None, description="A drag's origin, in actuation units."
    )
    performed: bool
    duration_ms: float
    change: ChangeReport | None = None
    screenshot: Screenshot | None = None
    tree: TreeResult | None = Field(default=None, description="What `tree` read.")
    windows: WindowsResult | None = Field(default=None, description="What `windows` listed.")
    matched: UINode | None = Field(default=None, description="The node a selector resolved to.")
    via: Via | None = Field(
        default=None, description="The rung actually taken; never `auto`."
    )
    activated: str | None = Field(
        default=None, description="The window `activate` brought forward."
    )
    error: ErrorInfo | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class _Outcome(NamedTuple):
    """What performing one action produced, beyond the fact that it ran."""

    screenshot: Screenshot | None = None
    tree: TreeResult | None = None
    windows: WindowsResult | None = None
    via: Via | None = None
    resolved: Coordinate | None = None
    activated: str | None = None


class RunResult(BaseModel):
    """One invocation. This is what the CLI serialises to stdout."""

    model_config = ConfigDict(frozen=True)

    profile: str
    backend: str
    screen: ScreenInfo
    ok: bool
    failed_index: int | None = None
    results: list[ActionResult] = Field(default_factory=list)


class Session:
    """A backend held open across a batch of actions."""

    def __init__(
        self,
        backend: Backend,
        *,
        profile: str,
        settings: Settings | None = None,
        provider: AccessibilityProvider | None = None,
    ) -> None:
        self._backend = backend
        self._profile = profile
        self._settings = settings or Settings()
        self._screenshot_dir = self._settings.screenshot_dir or default_screenshot_dir()
        self._screen = backend.screen_info()
        #: Built on the first action that needs it, so a run of pure coordinate actions never
        #: touches an accessibility API -- and never pays for one that is not installed.
        self._provider_instance = provider
        self._provider_built = provider is not None

    @classmethod
    def from_profile(
        cls, name: str | None = None, *, config: ResolvedConfig | None = None
    ) -> Session:
        """Open a session from a named profile in the project config."""
        resolved = config or load_config(profile=name)
        profile: BackendProfile = resolved.profile
        return cls(
            create_backend(profile), profile=profile.name, settings=resolved.settings
        )

    # --- context manager ---------------------------------------------------------------------

    def __enter__(self) -> Session:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._provider_instance is not None:
            self._provider_instance.close()
        self._backend.close()

    def _provider(self) -> AccessibilityProvider:
        if not self._provider_built:
            self._provider_instance = create_provider(self._backend.name)
            self._provider_built = True
        assert self._provider_instance is not None
        return self._provider_instance

    # --- running -----------------------------------------------------------------------------

    @property
    def screen(self) -> ScreenInfo:
        return self._screen

    def run(self, actions: Sequence[Action]) -> RunResult:
        """Perform every action in order against the open backend.

        Stops at the first failure unless ``continue_on_error`` is set: a later action usually
        depends on the state the failed one was meant to produce.
        """
        settings = self._settings
        results: list[ActionResult] = []
        failed_index: int | None = None
        carried: Screenshot | None = None

        for index, raw in enumerate(actions):
            action = with_default_space(raw, settings.space)
            verify = action.verify or settings.verify
            before = carried if verify else None
            if verify and before is None:
                before = self._safe_screenshot()

            result = self._run_one(action, before=before, verify=verify)
            results.append(result)
            carried = result.screenshot if verify else None

            if not result.ok:
                failed_index = index
                if not settings.continue_on_error:
                    break

        return RunResult(
            profile=self._profile,
            backend=self._backend.name,
            screen=self._screen,
            ok=failed_index is None,
            failed_index=failed_index,
            results=results,
        )

    def _run_one(
        self, action: Action, *, before: Screenshot | None, verify: bool
    ) -> ActionResult:
        settings = self._settings
        started = time.perf_counter()
        target: Coordinate | None = None
        origin: Coordinate | None = None
        screenshot: Screenshot | None = None
        change: ChangeReport | None = None
        tree: TreeResult | None = None
        windows: WindowsResult | None = None
        matched: UINode | None = None
        via: Via | None = None
        activated: str | None = None
        performed = False
        error: ErrorInfo | None = None

        try:
            target, origin = resolve(action, self._screen)
            selector = selector_of(action)
            if selector is not None:
                # Resolution happens now, against a tree read now. That is what makes a handle
                # from an earlier run safe to carry: nothing is trusted from the old snapshot.
                # Matching sees the full text; only what is reported back is clamped.
                matched = clamp_text(
                    notable_states(self._resolve_node(selector)), settings.tree_max_text
                )
            if settings.dry_run:
                # Everything above ran: the profile, the scaling, the key parsing, and the
                # selector. A dry run that skipped resolution would tell the agent nothing it
                # did not already know.
                if matched is not None:
                    via = self._plan_via(action, matched)
                    if via is Via.COORDINATE:
                        target = matched.center
            else:
                outcome = self._perform(action, target, origin, matched)
                screenshot, tree, via = outcome.screenshot, outcome.tree, outcome.via
                windows = outcome.windows
                activated = outcome.activated
                if outcome.resolved is not None:
                    target = outcome.resolved
                performed = True

            delay = action.delay if action.delay is not None else settings.delay
            if performed and delay:
                time.sleep(delay)

            if verify and performed:
                after = self._safe_screenshot()
                if before is not None and after is not None:
                    change = compare(before, after, settings.verify_threshold)
                if isinstance(action, ScreenshotAction):
                    # The action already captured and wrote one; do not write it twice.
                    pass
                elif after is not None:
                    # The capture is paid for either way. Writing it down is what saves the
                    # calling agent a round trip for a screen it already has.
                    screenshot = after.write_to(
                        self._screenshot_path(action.action)
                    )
        except UseComputerError as exc:
            error = ErrorInfo.of(exc)
        except Exception as exc:  # a backend can fail in its own vocabulary
            error = ErrorInfo.of(exc)

        return ActionResult(
            action=action,
            resolved=target,
            resolved_from=origin,
            performed=performed,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            change=change,
            screenshot=screenshot,
            tree=tree,
            windows=windows,
            matched=matched,
            via=via,
            activated=activated,
            error=error,
        )

    def _perform(
        self,
        action: Action,
        target: Coordinate | None,
        origin: Coordinate | None,
        matched: UINode | None,
    ) -> _Outcome:
        backend = self._backend
        via: Via | None = None
        resolved: Coordinate | None = None

        if isinstance(action, TreeAction):
            return _Outcome(tree=self._tree(action))

        if isinstance(action, WindowsAction):
            found = tuple(sole_active(self._provider().windows()))
            if action.format is OutputFormat.JSON:
                return _Outcome(windows=WindowsResult(windows=found))
            return _Outcome(windows=WindowsResult(text=render.windows(found)))

        if isinstance(action, ActivateAction):
            return _Outcome(activated=self._activate(action.window))

        if matched is not None:
            via = self._plan_via(action, matched)
            if via is Via.ACTION:
                wanted = self._api_action(action, matched)
                done = self._provider().perform(
                    matched.id, wanted, getattr(action, "value", None)
                )
                if done:
                    return _Outcome(via=Via.ACTION)
                requested = getattr(action, "via", Via.AUTO)
                if requested is Via.ACTION or isinstance(action, ELEMENT_ONLY):
                    # Asked for rung one and only rung one. Several of these APIs report failure
                    # by returning false, so this is a real failure, not an absent exception.
                    raise ActionFailedError(
                        f"the platform refused {wanted!r} on {matched.describe()}"
                    )
                via = Via.COORDINATE
            # Rung two: the tree found it, the platform will not operate it, so click its centre.
            resolved = matched.center
            target = resolved

        self._bring_forward(action, matched, via)

        x, y = (target.x, target.y) if target else (None, None)

        if isinstance(action, MoveAction):
            assert x is not None and y is not None
            backend.move(x, y)
        elif isinstance(action, DoubleClickAction):
            backend.click(x, y, action.button, 2)
        elif isinstance(action, RightClickAction):
            backend.click(x, y, MouseButton.RIGHT, 1)
        elif isinstance(action, DragAction):
            assert origin is not None and target is not None
            backend.drag(origin.x, origin.y, target.x, target.y, action.button)
        elif isinstance(action, ScrollAction):
            backend.scroll(action.amount, action.direction, x, y)
        elif isinstance(action, TypeAction):
            rate = action.rate if action.rate is not None else self._settings.typing_rate
            backend.type_text(action.text, rate)
        elif isinstance(action, KeyAction):
            backend.key(action.key_combo)
        elif isinstance(action, ScreenshotAction):
            return _Outcome(screenshot=self._capture(action))
        else:  # ClickAction, and anything else positional with a button
            backend.click(x, y, getattr(action, "button", MouseButton.LEFT), 1)
        return _Outcome(via=via, resolved=resolved)

    # --- the tree, and the elements in it ------------------------------------------------------

    def _bring_forward(self, action: Action, matched: UINode | None, via: Via | None) -> None:
        """Put the named window in front before a coordinate goes into it.

        A coordinate lands on whatever is on top. Without this, a click aimed at one application
        presses a button in another and reports a plausible success; `--verify` then confirms the
        wrong action against the wrong window, consistently.
        """
        if isinstance(action, (ScreenshotAction, ActivateAction)):
            return  # cropping raises its own window; activate *is* this
        if matched is not None:
            if via is not Via.COORDINATE:
                return  # rung one aims nothing, so there is nothing to raise
            selector = selector_of(action)
            scope = selector.window if selector is not None else None
        else:
            scope = getattr(action, "window", None)
        if scope is not None:
            self._activate(scope)

    def _activate(self, scope: TreeScope) -> str:
        """Bring a window forward and give it keyboard focus. Returns how to name it.

        A window object exposes no actions of its own on any of the three platforms -- AT-SPI
        answers `It supports: none` for a window -- so the general form is to focus a descendant,
        which raises the top-level window everywhere. A platform with a native raise (AXRaise on
        macOS, SetForegroundWindow on Windows) says so by returning true from `activate`.
        """
        provider = self._provider()
        resolved = self._scope(scope)
        known = self._window_for(resolved)
        if known is not None and known.active:
            return self._name_window(known)  # already in front: activation is a no-op

        root = provider.snapshot(resolved, self._settings.tree_depth)
        if not provider.activate(root.id):
            focused = False
            for node in walk(root):
                if (
                    node.id != root.id
                    and canonical.FOCUS in node.actions
                    and provider.perform(node.id, canonical.FOCUS, None)
                ):
                    focused = True
                    break
            if not focused:
                raise ActionFailedError(
                    f"cannot bring {root.describe()} forward: the platform offers no raise for a "
                    "window, and nothing inside it will take keyboard focus"
                )
        # A settle skipped here reintroduces exactly the bug this exists to remove.
        time.sleep(ACTIVATE_SETTLE)
        again = self._window_for(resolved)
        return self._name_window(again) if again is not None else root.describe()

    def _window_for(self, scope: TreeScope) -> WindowInfo | None:
        """The entry in `windows` this scope names, when it names exactly one."""
        entries = sole_active(self._provider().windows())
        if scope.kind is TreeScopeKind.FOCUSED:
            return next((entry for entry in entries if entry.active), None)
        if scope.kind is TreeScopeKind.ID:
            return next((entry for entry in entries if entry.id == scope.value), None)
        if scope.kind is TreeScopeKind.PID and scope.value:
            return next((entry for entry in entries if str(entry.pid) == scope.value), None)
        return None

    @staticmethod
    def _name_window(entry: WindowInfo) -> str:
        title = f" {entry.title!r}" if entry.title else ""
        return f"window{title} {entry.id}"

    def _api_action(self, action: Action, node: UINode) -> str:
        """Which platform action carries this command's meaning against this node.

        Almost always the obvious one. The exception is a `click` on a widget where selecting is
        how it is pressed: those advertise both, accept `click`, and do nothing with it.
        """
        wanted = API_ACTION[action.action]
        if (
            wanted == canonical.CLICK
            and node.role in SELECTION_ROLES
            and canonical.SELECT in node.actions
        ):
            return canonical.SELECT
        return wanted

    def _plan_via(self, action: Action, node: UINode) -> Via:
        """Which rung this action takes against this node, or why it cannot take one.

        Never a silent substitution: an action the platform does not offer is an error naming
        what the node *does* offer, and an action with no coordinate form never quietly becomes
        a click at a centre.
        """
        wanted = API_ACTION.get(action.action)
        requested = getattr(action, "via", Via.AUTO)

        if isinstance(action, ELEMENT_ONLY):
            assert wanted is not None
            if wanted not in node.actions:
                raise ActionNotSupportedError(wanted, node.describe(), node.actions)
            return Via.ACTION

        if wanted is None:
            # double_click, right_click, scroll: the element says where, the pointer does it.
            if requested is Via.ACTION:
                raise ActionNotSupportedError(action.action, node.describe(), node.actions)
            self._require_position(action.action, node)
            return Via.COORDINATE

        if requested is Via.COORDINATE:
            self._require_position(action.action, node)
            return Via.COORDINATE
        if wanted in node.actions:
            return Via.ACTION
        if requested is Via.ACTION:
            raise ActionNotSupportedError(wanted, node.describe(), node.actions)
        self._require_position(action.action, node)
        return Via.COORDINATE

    @staticmethod
    def _require_position(action: str, node: UINode) -> None:
        """Rung two needs somewhere to click, and not every node is anywhere.

        A node the platform reports without a position -- an item of a closed menu -- has a
        centre that is arithmetic, not a place. Clicking it is the exact failure this tool
        exists to prevent, so it refuses instead.
        """
        if not node.box.positioned:
            raise ActionNotSupportedError(
                action,
                node.describe(),
                node.actions,
                reason="It has no on-screen position, so it can only be operated through the "
                "platform API.",
            )

    def _scope(self, scope: TreeScope) -> TreeScope:
        """Turn a title into the id of exactly one window, or refuse.

        Done here rather than in each provider: it is policy, three platforms would drift on it,
        and two of them cannot be exercised on any one machine.
        """
        if scope.kind is TreeScopeKind.FOCUSED:
            # Resolved here, not in each provider, and refused rather than guessed: several
            # windows claiming to be active is not an answer, and picking the first is how an
            # agent reads, clicks and verifies inside the wrong application, consistently.
            return TreeScope(
                kind=TreeScopeKind.ID,
                value=active_window(sole_active(self._provider().windows())).id,
            )
        if scope.kind is not TreeScopeKind.TITLE or not scope.value:
            return scope
        found = resolve_window(self._provider().windows(), scope.value)
        return TreeScope(kind=TreeScopeKind.ID, value=found.id)

    def _resolve_node(self, selector: NodeSelector) -> UINode:
        """One node, from a tree read right now.

        Resolution runs against the *unpruned* tree: pruning is a reading convenience, and a
        selector must still be able to name something pruning would have dropped.
        """
        root = self._provider().snapshot(
            self._scope(selector.window), self._settings.tree_depth
        )
        try:
            return resolve_one(root, selector)
        except NodeNotFoundError as exc:
            # Nothing matched is precisely the signal to drop to vision, so hand over the
            # picture with the error rather than making the agent ask for it.
            shot = self._fallback_screenshot("nomatch") if self._settings.tree_fallback else None
            raise NodeNotFoundError(exc.description, screenshot=shot) from exc

    def _tree(self, action: TreeAction) -> TreeResult:
        """Read the tree, or say why there is none and hand over a screenshot instead."""
        settings = self._settings
        depth = action.depth if action.depth is not None else settings.tree_depth
        fallback = action.fallback if action.fallback is not None else settings.tree_fallback

        try:
            root = self._provider().snapshot(self._scope(action.window), depth)
        except PermissionDeniedError:
            return self._no_tree(TreeReason.DENIED, fallback)
        except UITreeUnavailableError:
            return self._no_tree(TreeReason.UNAVAILABLE, fallback)

        # On the raw snapshot, before anything of ours removes a child: a region hidden by our
        # own pruning is not a region the platform failed to describe.
        root = mark_unexposed(root)
        exposed_children = bool(root.children)

        if action.of is not None:
            found = subtree(root, action.of)
            if found is None:
                raise NodeNotFoundError(f"id={action.of}")
            root = found

        if action.role is not None or action.name is not None:
            # A filter answers "only buttons": the scope root carrying the matches, flat.
            selector = NodeSelector(role=action.role, name=action.name, window=action.window)
            matches = tuple(
                node.model_copy(update={"children": ()}) for node in find(root, selector)
            )
            root = root.model_copy(update={"children": matches})
        elif not action.full:
            root = prune(root)

        if not action.full:
            # Shape before size: dropping the states that say nothing, and counting what is off
            # screen instead of expanding it, is what made a tree affordable -- the budget only
            # ever bounded the worst case. Both decide what to *report*; a selector still resolves
            # against everything, so `click --name "Preferences"` works with the menu closed.
            root = summarise_offscreen(notable_states(root))

        truncated = False
        cut: tuple[str, ...] = ()
        if action.full:
            total = count(root)
        else:
            root, total, truncated, cut = budget(root, settings.tree_max_nodes)

        limited_by: str | None = None
        if not root.children:
            # A limit the caller asked for is never a property of the application. `empty` is a
            # diagnosis -- the skill turns it into "go and look" and attaches a screenshot to make
            # that branch convenient -- and `--depth 1` is not a diagnosis about anything.
            if exposed_children:
                limited_by = "the node budget" if truncated else "pruning"
            elif depth <= 1:
                limited_by = f"--depth {depth}"
            else:
                # The provider works and there is nothing here to act on. Saying "empty" and
                # handing over the picture is the useful answer; an empty tree on its own is not.
                return self._no_tree(TreeReason.EMPTY, fallback)

        root = clamp_text(root, settings.tree_max_text)

        if action.out is not None:
            action.out.parent.mkdir(parents=True, exist_ok=True)
            action.out.write_text(
                json.dumps(root.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return TreeResult(
                node_count=total,
                truncated=truncated,
                truncated_ids=cut,
                path=action.out,
                limited_by=limited_by,
            )

        if action.format is OutputFormat.JSON:
            return TreeResult(
                root=root,
                node_count=total,
                truncated=truncated,
                truncated_ids=cut,
                limited_by=limited_by,
            )
        return TreeResult(
            text=render.tree(root),
            node_count=total,
            truncated=truncated,
            truncated_ids=cut,
            limited_by=limited_by,
        )

    def _no_tree(self, reason: TreeReason, fallback: bool) -> TreeResult:
        shot = self._fallback_screenshot("tree") if fallback else None
        return TreeResult(reason=reason, screenshot=shot)

    def _fallback_screenshot(self, label: str) -> Screenshot | None:
        shot = self._safe_screenshot()
        if shot is None:
            return None
        try:
            return shot.write_to(self._screenshot_path(label))
        except OSError:
            return None

    def _capture(self, action: ScreenshotAction) -> Screenshot:
        label = "screenshot"
        if action.of is not None:
            # Before the capture, not after it. The tree says where a node is; it says nothing
            # about what is drawn on top. Cropping a desktop capture at those coordinates while
            # another application covers them yields a picture of the wrong program at the right
            # size, with the right node id and an `ok` -- the one failure here that produces no
            # signal at all, in the step whose whole job is to be the trustworthy one.
            self._activate(action.window)
            shot = self._crop_to_node(
                self._backend.screenshot(), action.of, action.window, action.pad
            )
            label = "node"
        else:
            shot = self._backend.screenshot()
        return shot.write_to(action.out or self._screenshot_path(label))

    def _crop_to_node(
        self, shot: Screenshot, node_id: str, scope: TreeScope, pad: int
    ) -> Screenshot:
        """A picture of one element rather than of the screen.

        The tree already knows exactly where; only *what* is missing. Cropping turns a rung-three
        answer from two million pixels into a few thousand, with the thing being asked about
        filling the frame instead of being a fraction of a percent of it.
        """
        root = self._provider().snapshot(self._scope(scope), self._settings.tree_depth)
        node = subtree(root, node_id)
        if node is None:
            raise NodeNotFoundError(f"id={node_id}")
        if not node.box.positioned:
            # Same refusal as a coordinate click on such a node, and for the same reason: the box
            # is arithmetic, not a place.
            raise ActionNotSupportedError(
                "screenshot --of", node.describe(), node.actions,
                reason="It has no on-screen position, so there is nothing to crop to.",
            )

        # The box is in actuation units and the crop is in screenshot pixels. This is the one
        # place a box crosses that boundary, so it is the one place the scale must be applied
        # rather than assumed: unscaled on a HiDPI display it is off by two and looks plausible.
        scale = self._screen.scale
        if scale is None:
            raise CoordinateSpaceError(
                "the screenshot scale is unknown, so a node's box cannot be turned into a crop. "
                "Set `scale` in the profile, or take a full screenshot."
            )
        box = node.box
        left = round(box.x * scale) - pad
        top = round(box.y * scale) - pad
        width = round(box.width * scale) + pad * 2
        height = round(box.height * scale) + pad * 2
        return crop(shot, (left, top, width, height), node_id)

    def _screenshot_path(self, label: str) -> Path:
        """A name that sorts and does not collide -- and which `prune` recognises as ours."""
        if self._screenshot_dir.parent.name == PROJECT_DIR:
            ensure_gitignore(self._screenshot_dir.parent)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f")[:-3] + "Z"
        return self._screenshot_dir / f"{stamp}-{label}.png"

    def _safe_screenshot(self) -> Screenshot | None:
        """Change detection is advisory; a capture that fails must not fail the action."""
        try:
            return self._backend.screenshot()
        except Exception:
            return None


def run_actions(
    actions: Sequence[Action],
    *,
    profile: str | None = None,
    config: ResolvedConfig | None = None,
) -> RunResult:
    """Open a session, run a batch, close it -- including when an action failed."""
    session = Session.from_profile(profile, config=config)
    try:
        return session.run(actions)
    finally:
        session.close()


def as_json(result: RunResult) -> dict[str, Any]:
    """The run payload. A screenshot is a path here, never bytes."""
    payload: dict[str, Any] = result.model_dump(mode="json")
    return payload
