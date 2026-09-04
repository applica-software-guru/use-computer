"""Executing a batch: one backend, many actions, one connection.

Opening a VNC connection dominates the cost of a single action, so the backend is constructed
once and every action runs against it. A single action invoked directly is simply a batch of
one and returns the same shape.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from use_computer.actions import (
    Action,
    DoubleClickAction,
    DragAction,
    KeyAction,
    MouseButton,
    MoveAction,
    RightClickAction,
    ScreenshotAction,
    ScrollAction,
    TypeAction,
    resolve,
    with_default_space,
)
from use_computer.backends import Backend, create_backend
from use_computer.compare import ChangeReport, Screenshot, compare
from use_computer.config import (
    BackendProfile,
    ResolvedConfig,
    Settings,
    default_screenshot_dir,
)
from use_computer.config import load as load_config
from use_computer.coordinates import Coordinate, ScreenInfo
from use_computer.errors import UseComputerError


class ErrorInfo(BaseModel):
    """A failure, as the calling agent sees it."""

    model_config = ConfigDict(frozen=True)

    type: str
    message: str

    @classmethod
    def of(cls, exc: BaseException) -> ErrorInfo:
        return cls(type=type(exc).__name__, message=str(exc))


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
    error: ErrorInfo | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


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
    ) -> None:
        self._backend = backend
        self._profile = profile
        self._settings = settings or Settings()
        self._screenshot_dir = self._settings.screenshot_dir or default_screenshot_dir()
        self._screen = backend.screen_info()

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
        self._backend.close()

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
        performed = False
        error: ErrorInfo | None = None

        try:
            target, origin = resolve(action, self._screen)
            if settings.dry_run:
                # Everything above ran: the profile, the scaling, the key parsing. Only the
                # actuation is skipped.
                pass
            else:
                screenshot = self._perform(action, target, origin)
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
            error=error,
        )

    def _perform(
        self, action: Action, target: Coordinate | None, origin: Coordinate | None
    ) -> Screenshot | None:
        backend = self._backend
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
            return self._capture(action)
        else:  # ClickAction, and anything else positional with a button
            backend.click(x, y, getattr(action, "button", MouseButton.LEFT), 1)
        return None

    def _capture(self, action: ScreenshotAction) -> Screenshot:
        shot = self._backend.screenshot()
        return shot.write_to(action.out or self._screenshot_path("screenshot"))

    def _screenshot_path(self, label: str) -> Path:
        """A name that sorts and does not collide."""
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
