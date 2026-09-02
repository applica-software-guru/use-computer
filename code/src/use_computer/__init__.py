"""use-computer: execute input on a screen for computer-use agents.

The acting half of a pair. ui-locator answers where; this performs the action there.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from use_computer.actions import (
    Action,
    ClickAction,
    DoubleClickAction,
    DragAction,
    KeyAction,
    MouseButton,
    MoveAction,
    RightClickAction,
    ScreenshotAction,
    ScrollAction,
    ScrollDirection,
    TypeAction,
)
from use_computer.backends import Backend, create_backend
from use_computer.compare import ChangeReport, Screenshot, compare
from use_computer.config import BackendProfile, ResolvedConfig, Settings
from use_computer.config import load as load_config
from use_computer.coordinates import Coordinate, CoordinateSpace, ScreenInfo, convert
from use_computer.errors import (
    ActionFailedError,
    BackendNotAvailableError,
    ConfigError,
    CoordinateSpaceError,
    KeySyntaxError,
    PermissionDeniedError,
    UseComputerError,
)
from use_computer.keys import KeyCombo, parse_combo
from use_computer.runner import ActionResult, ErrorInfo, RunResult, Session, run_actions

try:
    __version__ = version("use-computer")
except PackageNotFoundError:  # pragma: no cover - source checkout without an install
    __version__ = "0.0.0"

__all__ = [
    "Action",
    "ActionFailedError",
    "ActionResult",
    "Backend",
    "BackendNotAvailableError",
    "BackendProfile",
    "ChangeReport",
    "ClickAction",
    "ConfigError",
    "Coordinate",
    "CoordinateSpace",
    "CoordinateSpaceError",
    "DoubleClickAction",
    "DragAction",
    "ErrorInfo",
    "KeyAction",
    "KeyCombo",
    "KeySyntaxError",
    "MouseButton",
    "MoveAction",
    "PermissionDeniedError",
    "ResolvedConfig",
    "RightClickAction",
    "RunResult",
    "ScreenInfo",
    "Screenshot",
    "ScreenshotAction",
    "ScrollAction",
    "ScrollDirection",
    "Session",
    "Settings",
    "TypeAction",
    "UseComputerError",
    "__version__",
    "compare",
    "convert",
    "create_backend",
    "load_config",
    "parse_combo",
    "run_actions",
]
