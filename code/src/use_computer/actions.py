"""The action models, and the resolution that happens before a backend sees them.

The action set is the whole surface of what use-computer does to a screen. Coordinate scaling
and key parsing are applied here, so that everything crossing the backend boundary is already
in actuation units and canonical key names.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from use_computer.coordinates import Coordinate, CoordinateSpace, ScreenInfo, convert
from use_computer.keys import KeyCombo, canonical, parse_combo
from use_computer.tree import NodeSelector, TreeScope, Via


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


class _Positioned(BaseAction):
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


class DragAction(BaseAction):
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
    out: Path | None = Field(
        default=None, description="Where to write it. None means the screenshot directory."
    )


class TreeAction(BaseAction):
    """Read the accessibility tree. An action, so a batch can end with the resulting state."""

    action: Literal["tree"] = "tree"
    window: TreeScope = Field(default_factory=TreeScope)
    depth: int | None = Field(default=None, ge=0, description="None uses the configured depth.")
    role: str | None = None
    name: str | None = None
    of: str | None = Field(default=None, description="Re-enter at a node id from an earlier tree.")
    all: bool = Field(default=False, description="No pruning and no budget.")
    out: Path | None = Field(default=None, description="Write the tree JSON here instead.")
    fallback: bool | None = Field(
        default=None, description="Screenshot when there is no tree. None uses configuration."
    )

    @field_validator("window", mode="before")
    @classmethod
    def _parse_window(cls, value: Any) -> Any:
        return TreeScope.parse(value) if isinstance(value, str) else value


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
    | FocusAction
    | ToggleAction
    | ExpandAction
    | CollapseAction
    | SelectAction
    | SetValueAction
    | ShowMenuAction,
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
