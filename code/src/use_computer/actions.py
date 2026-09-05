"""The action models, and the resolution that happens before a backend sees them.

The action set is the whole surface of what use-computer does to a screen. Coordinate scaling
and key parsing are applied here, so that everything crossing the backend boundary is already
in actuation units and canonical key names.
"""

from __future__ import annotations

from difflib import get_close_matches
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from use_computer.coordinates import Coordinate, CoordinateSpace, ScreenInfo, convert
from use_computer.keys import KeyCombo, canonical, parse_combo
from use_computer.tree import NodeSelector, OutputFormat, TreeScope, Via


class MouseButton(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class ScrollDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class BaseAction(BaseModel):
    """Fields every action shares."""

    delay: float | None = Field(default=None, ge=0, description="Seconds to wait afterwards.")
    verify: bool = Field(default=False, description="Compare the screen before and after.")

    @property
    def target(self) -> Coordinate | None:
        """The point this action acts on, or None if it has no coordinate."""
        return None

    @property
    def origin(self) -> Coordinate | None:
        """The point this action starts from -- only a drag has one."""
        return None


class _InAWindow(BaseAction):
    """An action whose coordinate belongs to a particular window.

    A coordinate lands on whatever window is in front. That is what a bare coordinate has always
    meant, and it is fine until the agent meant a particular window -- which is most of the time.
    Naming it here is how the caller says so, and the window is brought forward before the
    coordinate is sent. Measured: two drags aimed at a canvas selected text in a terminal instead,
    and `--verify` then confirmed the wrong action with the wrong evidence.
    """

    window: TreeScope | None = None

    @field_validator("window", mode="before")
    @classmethod
    def _parse_scope(cls, value: Any) -> Any:
        return TreeScope.parse(value) if isinstance(value, str) else value


class _Positioned(_InAWindow):
    """An action that may carry a coordinate. Omitting it acts where the pointer already is."""

    x: int | None = None
    y: int | None = None
    space: CoordinateSpace | None = None

    @property
    def target(self) -> Coordinate | None:
        if self.x is None or self.y is None:
            return None
        space = self.space if self.space is not None else CoordinateSpace.SCREENSHOT
        return Coordinate(x=self.x, y=self.y, space=space)


#: Flat selector keys, as they appear in a batch file. They are collected into a NodeSelector so
#: the JSON reads the way the CLI flags do.
_SELECTOR_KEYS = ("id", "role", "name", "exact", "nth", "window")


class _Selectable(BaseModel):
    """Mixin for actions that can name an element instead of a point."""

    selector: NodeSelector | None = None
    via: Via = Field(default=Via.AUTO, description="Which rung of the ladder to take.")

    @model_validator(mode="before")
    @classmethod
    def _collect_selector(cls, data: Any) -> Any:
        """Gather the flat selector keys of a batch file into one NodeSelector."""
        if not isinstance(data, dict) or data.get("selector") is not None:
            return data
        present = {key: data[key] for key in _SELECTOR_KEYS if data.get(key) is not None}
        if not present:
            return data
        rest = {key: value for key, value in data.items() if key not in _SELECTOR_KEYS}
        window = present.pop("window", None)
        node_id = present.pop("id", None)
        rest["selector"] = NodeSelector(
            node_id=node_id,
            window=TreeScope.parse(window) if isinstance(window, str) else (window or TreeScope()),
            **present,
        )
        return rest


class MoveAction(_Positioned):
    action: Literal["move"] = "move"
    x: int
    y: int


class _PositionedOrSelected(_Positioned, _Selectable):
    """An action that takes a coordinate *or* an element, never both.

    Rejecting the pair is deliberate: deciding which one wins would be exactly the kind of
    silent reinterpretation this tool refuses to do with coordinate spaces.
    """

    @model_validator(mode="after")
    def _one_target(self) -> _PositionedOrSelected:
        if self.selector is not None and (self.x is not None or self.y is not None):
            raise ValueError(
                "give a coordinate or a selector, not both -- the target is one thing or the other"
            )
        return self


class ClickAction(_PositionedOrSelected):
    action: Literal["click"] = "click"
    button: MouseButton = MouseButton.LEFT


class DoubleClickAction(_PositionedOrSelected):
    action: Literal["double_click"] = "double_click"
    button: MouseButton = MouseButton.LEFT


class RightClickAction(_PositionedOrSelected):
    action: Literal["right_click"] = "right_click"


class DragAction(_InAWindow):
    action: Literal["drag"] = "drag"
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    space: CoordinateSpace | None = None
    button: MouseButton = MouseButton.LEFT

    @property
    def origin(self) -> Coordinate:
        return Coordinate(x=self.from_x, y=self.from_y, space=self._space)

    @property
    def target(self) -> Coordinate:
        return Coordinate(x=self.to_x, y=self.to_y, space=self._space)

    @property
    def _space(self) -> CoordinateSpace:
        return self.space if self.space is not None else CoordinateSpace.SCREENSHOT


class ScrollAction(_PositionedOrSelected):
    action: Literal["scroll"] = "scroll"
    amount: int
    direction: ScrollDirection = ScrollDirection.DOWN


class TypeAction(BaseAction):
    action: Literal["type"] = "type"
    text: str
    rate: float | None = Field(
        default=None,
        ge=0,
        description="Seconds between keystrokes; None uses the configured rate.",
    )


class KeyAction(BaseAction):
    action: Literal["key"] = "key"
    combo: str

    @field_validator("combo")
    @classmethod
    def _canonicalise(cls, value: str) -> str:
        # Parse at construction: an unknown key name must fail before a connection is opened,
        # and the canonical spelling is what appears in results and logs.
        return canonical(value)

    @property
    def key_combo(self) -> KeyCombo:
        return parse_combo(self.combo)


class ScreenshotAction(BaseAction):
    action: Literal["screenshot"] = "screenshot"

    @field_validator("window", mode="before")
    @classmethod
    def _parse_scope(cls, value: Any) -> Any:
        return TreeScope.parse(value) if isinstance(value, str) else value

    out: Path | None = Field(
        default=None, description="Where to write it. None means the screenshot directory."
    )
    of: str | None = Field(
        default=None,
        description="Crop to this node's box. The tree knows where; only what is missing.",
    )
    window: TreeScope = Field(
        default_factory=TreeScope,
        description="Which tree `of` is an id in. An id means nothing without its scope.",
    )
    pad: int = Field(
        default=0,
        ge=0,
        description="Grow the crop by this many pixels each side; a control's box often "
        "excludes the label beside it.",
    )


class TreeAction(BaseAction):
    """Read the accessibility tree. An action, so a batch can end with the resulting state."""

    action: Literal["tree"] = "tree"
    window: TreeScope = Field(default_factory=TreeScope)
    depth: int | None = Field(default=None, ge=0, description="None uses the configured depth.")
    role: str | None = None
    name: str | None = None
    of: str | None = Field(default=None, description="Re-enter at a node id from an earlier tree.")
    full: bool = Field(
        default=False,
        description="Everything: no pruning, no budget, every state, every subtree expanded.",
    )
    out: Path | None = Field(default=None, description="Write the tree JSON here instead.")
    fallback: bool | None = Field(
        default=None, description="Screenshot when there is no tree. None uses configuration."
    )
    format: OutputFormat = Field(
        default=OutputFormat.TEXT, description="Rendered text, or objects to parse."
    )

    @field_validator("window", mode="before")
    @classmethod
    def _parse_window(cls, value: Any) -> Any:
        return TreeScope.parse(value) if isinstance(value, str) else value


class WindowsAction(BaseAction):
    """List what is open. The cheapest read there is, and the one to make first."""

    action: Literal["windows"] = "windows"
    format: OutputFormat = Field(
        default=OutputFormat.TEXT, description="Rendered text, or objects to parse."
    )


class _ElementAction(BaseAction, _Selectable):
    """An action that only exists against an element: there is no coordinate form of it."""

    @model_validator(mode="after")
    def _needs_a_selector(self) -> _ElementAction:
        name = getattr(self, "action", type(self).__name__)
        if self.selector is None:
            raise ValueError(f"{name} needs an element: pass --id, --role or --name")
        if self.via is Via.COORDINATE:
            # There is no coordinate form of these. Clicking the centre of a node to approximate
            # `focus` or `set_value` would be a different gesture wearing the same name.
            raise ValueError(f"{name} has no coordinate form; --via coordinate cannot apply")
        return self


class FocusAction(_ElementAction):
    action: Literal["focus"] = "focus"


class ToggleAction(_ElementAction):
    action: Literal["toggle"] = "toggle"


class ExpandAction(_ElementAction):
    action: Literal["expand"] = "expand"


class CollapseAction(_ElementAction):
    action: Literal["collapse"] = "collapse"


class SelectAction(_ElementAction):
    action: Literal["select"] = "select"


class SetValueAction(_ElementAction):
    """Assign text atomically, emitting no keystrokes.

    Not a faster `type`: some applications ignore it entirely, because their validation only
    fires on key events. Both are correct, for different fields.
    """

    action: Literal["set_value"] = "set_value"
    value: str


class ShowMenuAction(_ElementAction):
    action: Literal["show_menu"] = "show_menu"


class ActivateAction(BaseAction):
    """Bring a window forward and give it keyboard focus.

    The only action whose target is a window rather than an element or a point. A window object
    exposes no actions of its own on any of the three platforms -- AT-SPI answers `It supports:
    none` -- so it is done by focusing a descendant, which raises the top-level window everywhere.
    """

    action: Literal["activate"] = "activate"
    window: TreeScope

    @field_validator("window", mode="before")
    @classmethod
    def _parse_scope(cls, value: Any) -> Any:
        return TreeScope.parse(value) if isinstance(value, str) else value


Action = Annotated[
    MoveAction
    | ClickAction
    | DoubleClickAction
    | RightClickAction
    | DragAction
    | ScrollAction
    | TypeAction
    | KeyAction
    | ScreenshotAction
    | TreeAction
    | WindowsAction
    | FocusAction
    | ToggleAction
    | ExpandAction
    | CollapseAction
    | SelectAction
    | SetValueAction
    | ShowMenuAction
    | ActivateAction,
    Field(discriminator="action"),
]

#: The actions that operate an element rather than a point. `click` and friends are not here:
#: they are in both worlds, and which one they took is decided by their selector.
ELEMENT_ONLY = (
    FocusAction,
    ToggleAction,
    ExpandAction,
    CollapseAction,
    SelectAction,
    SetValueAction,
    ShowMenuAction,
)


def selector_of(action: Action) -> NodeSelector | None:
    """The element this action names, if it names one."""
    return getattr(action, "selector", None)

#: Parses a batch file: a JSON array of action objects, discriminated on `action`.
ActionListAdapter: TypeAdapter[list[Action]] = TypeAdapter(list[Action])

#: Every action name, in the spelling the discriminator uses.
ACTION_NAMES: tuple[str, ...] = (
    "move",
    "click",
    "double_click",
    "right_click",
    "drag",
    "scroll",
    "type",
    "key",
    "screenshot",
    "tree",
    "windows",
    "focus",
    "toggle",
    "expand",
    "collapse",
    "select",
    "set_value",
    "show_menu",
    "activate",
)


def _cli_spelling(name: str) -> str:
    """How this action is spelled as a command: `set_value` is typed `set-value`."""
    return name.replace("_", "-")


def normalise_action_names(data: Any) -> Any:
    """Accept the CLI's own spelling of an action name inside a batch.

    The command is `use-computer set-value`; the batch wanted `set_value`. Same action, two
    spellings, and nothing said so -- an agent that has just read `set-value --help` has no reason
    to expect a different name three lines later.
    """
    if not isinstance(data, list):
        return data
    out = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("action"), str):
            item = {**item, "action": item["action"].replace("-", "_")}
        out.append(item)
    return out


def check_action_names(data: Any) -> None:
    """Fail on an unknown action with a sentence, before pydantic offers its union.

    The union's own error is four hundred characters naming every variant except the one the
    caller should have written. This is a message to somebody mid-task who cannot see the code.
    """
    if not isinstance(data, list):
        return
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        name = item.get("action")
        if not isinstance(name, str) or name in ACTION_NAMES:
            continue
        close = get_close_matches(name, ACTION_NAMES, n=1, cutoff=0.6)
        suggestion = f" Did you mean {_cli_spelling(close[0])!r}?" if close else ""
        raise ValueError(
            f"unknown action {_cli_spelling(name)!r} at index {index}.{suggestion}"
        )

#: Parses a single action object.
ActionAdapter: TypeAdapter[Action] = TypeAdapter(Action)


def with_default_space(action: Action, space: CoordinateSpace) -> Action:
    """Fill in the coordinate space an action did not state, from configuration."""
    if getattr(action, "space", "missing") is None:
        return action.model_copy(update={"space": space})
    return action


def resolve(action: Action, screen: ScreenInfo) -> tuple[Coordinate | None, Coordinate | None]:
    """Convert an action's coordinates into actuation units.

    Returns ``(target, origin)``; either may be ``None`` when the action carries no coordinate.

    Raises:
        CoordinateSpaceError: when the scale needed for the conversion is unknown.
    """
    target = action.target
    origin = action.origin
    resolved_target = convert(target, CoordinateSpace.ACTUATION, screen) if target else None
    resolved_origin = convert(origin, CoordinateSpace.ACTUATION, screen) if origin else None
    return resolved_target, resolved_origin
