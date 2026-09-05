"""use-computer: execute input on a screen for computer-use agents.

The acting half of a pair. ui-locator answers where; this performs the action there.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from use_computer.accessibility import AccessibilityProvider, create_provider
from use_computer.actions import (
    Action,
    ClickAction,
    CollapseAction,
    DoubleClickAction,
    DragAction,
    ExpandAction,
    FocusAction,
    KeyAction,
    MouseButton,
    MoveAction,
    RightClickAction,
    ScreenshotAction,
    ScrollAction,
    ScrollDirection,
    SelectAction,
    SetValueAction,
    ShowMenuAction,
    ToggleAction,
    TreeAction,
    TypeAction,
    WindowsAction,
)
from use_computer.backends import Backend, create_backend
from use_computer.compare import ChangeReport, Screenshot, compare
from use_computer.config import BackendProfile, ResolvedConfig, Settings
from use_computer.config import load as load_config
from use_computer.coordinates import Coordinate, CoordinateSpace, ScreenInfo, convert
from use_computer.errors import (
    ActionFailedError,
    ActionNotSupportedError,
    AmbiguousNodeError,
    BackendNotAvailableError,
    ConfigError,
    CoordinateSpaceError,
    KeySyntaxError,
    NodeNotFoundError,
    PermissionDeniedError,
    UITreeUnavailableError,
    UseComputerError,
)
from use_computer.keys import KeyCombo, parse_combo
from use_computer.runner import ActionResult, ErrorInfo, RunResult, Session, run_actions
from use_computer.tree import (
    Box,
    NodeSelector,
    OutputFormat,
    TreeReason,
    TreeResult,
    TreeScope,
    UINode,
    Via,
    WindowInfo,
    WindowsResult,
)

#: The distribution name on PyPI, which differs from the import package: `use-computer` was
#: already taken there. importlib.metadata is keyed by the distribution, so this is the name
#: that must appear here.
DISTRIBUTION = "use-computer-cli"

try:
    __version__ = version(DISTRIBUTION)
except PackageNotFoundError:  # pragma: no cover - source checkout without an install
    __version__ = "0.0.0"

__all__ = [
    "DISTRIBUTION",
    "AccessibilityProvider",
    "Action",
    "ActionFailedError",
    "ActionNotSupportedError",
    "ActionResult",
    "AmbiguousNodeError",
    "Backend",
    "BackendNotAvailableError",
    "BackendProfile",
    "Box",
    "ChangeReport",
    "ClickAction",
    "CollapseAction",
    "ConfigError",
    "Coordinate",
    "CoordinateSpace",
    "CoordinateSpaceError",
    "DoubleClickAction",
    "DragAction",
    "ErrorInfo",
    "ExpandAction",
    "FocusAction",
    "KeyAction",
    "KeyCombo",
    "KeySyntaxError",
    "MouseButton",
    "MoveAction",
    "NodeNotFoundError",
    "NodeSelector",
    "OutputFormat",
    "PermissionDeniedError",
    "ResolvedConfig",
    "RightClickAction",
    "RunResult",
    "ScreenInfo",
    "Screenshot",
    "ScreenshotAction",
    "ScrollAction",
    "ScrollDirection",
    "SelectAction",
    "Session",
    "SetValueAction",
    "Settings",
    "ShowMenuAction",
    "ToggleAction",
    "TreeAction",
    "TreeReason",
    "TreeResult",
    "TreeScope",
    "TypeAction",
    "UINode",
    "UITreeUnavailableError",
    "UseComputerError",
    "Via",
    "WindowInfo",
    "WindowsAction",
    "WindowsResult",
    "__version__",
    "compare",
    "convert",
    "create_backend",
    "create_provider",
    "load_config",
    "parse_combo",
    "run_actions",
]
