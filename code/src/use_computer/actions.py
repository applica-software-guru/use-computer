"""The action models, and the resolution that happens before a backend sees them.

The action set is the whole surface of what use-computer does to a screen. Coordinate scaling
and key parsing are applied here, so that everything crossing the backend boundary is already
in actuation units and canonical key names.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator

from use_computer.coordinates import Coordinate, CoordinateSpace, ScreenInfo, convert
from use_computer.keys import KeyCombo, canonical, parse_combo


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


class MoveAction(_Positioned):
    action: Literal["move"] = "move"
    x: int
    y: int


class ClickAction(_Positioned):
    action: Literal["click"] = "click"
    button: MouseButton = MouseButton.LEFT


class DoubleClickAction(_Positioned):
    action: Literal["double_click"] = "double_click"
    button: MouseButton = MouseButton.LEFT


class RightClickAction(_Positioned):
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


class ScrollAction(_Positioned):
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
    out: Path | None = None
    base64: bool = False


Action = Annotated[
    MoveAction
    | ClickAction
    | DoubleClickAction
    | RightClickAction
    | DragAction
    | ScrollAction
    | TypeAction
    | KeyAction
    | ScreenshotAction,
    Field(discriminator="action"),
]

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
