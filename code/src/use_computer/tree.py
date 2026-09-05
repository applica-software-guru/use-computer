"""The accessibility tree: what the operating system says is on the screen.

A screenshot has to be looked at. The OS already knows there is a button labelled "Invia" at a
given box, enabled, inside a dialog -- and reading that costs a fraction of what looking at a
picture of it costs.

This module is pure. It holds the models and nothing that touches a platform binding, so the
policy above it (pruning, budgets, selector matching in :mod:`use_computer.selectors`) tests
without a desktop -- which matters, because no CI runner has one.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from use_computer.compare import Screenshot
from use_computer.coordinates import Coordinate, CoordinateSpace


class Box(BaseModel):
    """The geometry of an element, in the units the accessibility API reports.

    That is the *actuation* space -- never screenshot pixels. Easy to get wrong, because on a
    1:1 display the two agree and the bug only shows up on somebody's HiDPI laptop.
    """

    model_config = ConfigDict(frozen=True)

    x: int
    y: int
    width: int
    height: int
    space: CoordinateSpace = CoordinateSpace.ACTUATION

    @model_validator(mode="before")
    @classmethod
    def _from_array(cls, data: Any) -> Any:
        if isinstance(data, (list, tuple)) and len(data) == 4:
            x, y, width, height = data
            return {"x": x, "y": y, "width": width, "height": height}
        return data

    @model_serializer
    def _as_array(self) -> list[int]:
        """``[x, y, width, height]``.

        The space is not repeated on every node because it is always actuation, and the keys cost
        more than the values -- over a tree of thousands of nodes that is most of the payload.
        """
        return [self.x, self.y, self.width, self.height]

    @property
    def positioned(self) -> bool:
        """Whether this box is anywhere at all.

        A platform reports an element that is not currently rendered -- the items of a closed
        menu, say -- with a sentinel rather than a position. Such an element is still operable
        through the accessibility API, and its centre is not a place: clicking it would land
        wherever a garbage coordinate happens to point.
        """
        return self.width > 0 and self.height > 0

    @property
    def center(self) -> Coordinate:
        """The point to click when the platform offers no way to operate the element."""
        return Coordinate(
            x=self.x + self.width // 2, y=self.y + self.height // 2, space=self.space
        )


class UINode(BaseModel):
    """One element of the tree."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="A structural path in the *full* tree, e.g. 0/2/1/3.")
    role: str = Field(description="Canonical role, normalised across platforms.")
    name: str | None = None
    value: str | None = None
    states: tuple[str, ...] = ()
    actions: tuple[str, ...] = Field(
        default=(),
        description="Canonical actions this node supports. Empty means: click it by coordinate.",
    )
    box: Box
    offscreen_children: int = Field(
        default=0,
        ge=0,
        description="Descendants not on screen, counted rather than expanded.",
    )
    children: tuple[UINode, ...] = ()

    @model_serializer
    def _compact(self) -> dict[str, Any]:
        """Omit what is empty, and say only what is worth its bytes.

        A tree is only useful if an agent can afford to read it: the obvious shape measured 271
        bytes a node against 150 for this one, over the same window.
        """
        out: dict[str, Any] = {"id": self.id, "role": self.role}
        if self.name:
            out["name"] = self.name
        if self.value:
            out["value"] = self.value
        if self.states:
            out["states"] = list(self.states)
        if self.actions:
            out["actions"] = list(self.actions)
        out["box"] = self.box
        if self.offscreen_children:
            out["offscreen_children"] = self.offscreen_children
        if self.children:
            out["children"] = list(self.children)
        return out

    @property
    def center(self) -> Coordinate:
        return self.box.center

    def describe(self) -> str:
        """Short human form, for an error message a stuck agent has to read."""
        name = f" {self.name!r}" if self.name else ""
        return f"{self.role}{name} at {self.id}"


class WindowInfo(BaseModel):
    """One entry of what ``windows`` returns.

    The cheapest question an agent can ask is "what is open?", and it should not cost a tree:
    twelve windows measured at 1,429 bytes against 19,752 for a single window's tree.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    title: str | None = None
    role: str
    app: str | None = Field(
        default=None,
        description="The application it belongs to. Without it a candidate list is unreadable.",
    )
    pid: int | None = None
    box: Box
    active: bool = False


class OutputFormat(str, Enum):
    """How a read comes back. Either way stdout is one JSON object."""

    TEXT = "text"
    """One line per node inside a string field. 39% of the tokens, and the default."""

    JSON = "json"
    """Objects, for a caller that parses rather than reads."""


class TreeScopeKind(str, Enum):
    FOCUSED = "focused"
    ALL = "all"
    TITLE = "title"
    PID = "pid"
    ID = "id"
    """A specific window, by the id `windows` reported. What a title resolves to."""


class WindowsResult(BaseModel):
    """What ``windows`` returns. Symmetrical with TreeResult, so the two reads look alike."""

    model_config = ConfigDict(frozen=True)

    text: str | None = None
    windows: tuple[WindowInfo, ...] = ()


class TreeScope(BaseModel):
    """What to snapshot. The focused window by default, never the whole desktop."""

    model_config = ConfigDict(frozen=True)

    kind: TreeScopeKind = TreeScopeKind.FOCUSED
    value: str | None = None

    @classmethod
    def parse(cls, raw: str | None) -> TreeScope:
        """``focused``, ``all``, ``@1234`` for a pid, anything else a window title."""
        if raw is None or raw == "" or raw == TreeScopeKind.FOCUSED.value:
            return cls(kind=TreeScopeKind.FOCUSED)
        if raw == TreeScopeKind.ALL.value:
            return cls(kind=TreeScopeKind.ALL)
        if raw.startswith("@"):
            return cls(kind=TreeScopeKind.PID, value=raw[1:])
        return cls(kind=TreeScopeKind.TITLE, value=raw)


class TreeReason(str, Enum):
    """Why no tree came back."""

    UNAVAILABLE = "unavailable"
    """No provider for this platform, or a backend that structurally cannot have one."""

    DENIED = "denied"
    """The OS refused the accessibility permission."""

    EMPTY = "empty"
    """The provider works and the application exposes nothing."""


class TreeResult(BaseModel):
    """A snapshot, or the reason there isn't one and the picture taken instead."""

    model_config = ConfigDict(frozen=True)

    root: UINode | None = None
    node_count: int = 0
    truncated: bool = False
    truncated_ids: tuple[str, ...] = ()
    text: str | None = Field(
        default=None,
        description="The rendering, legend first. Absent under --format json, which carries "
        "objects instead: asking for the envelope is asking to parse.",
    )
    reason: TreeReason | None = None
    screenshot: Screenshot | None = None
    path: Path | None = Field(
        default=None,
        description="Where the tree was written, when --out asked for a file. `root` is then "
        "omitted, which is the point of asking.",
    )


class Via(str, Enum):
    """Which rung of the ladder an element-addressed action should take."""

    AUTO = "auto"
    """The platform API when the node supports it, otherwise a click at its centre."""

    ACTION = "action"
    """Rung one only. Error rather than fall back."""

    COORDINATE = "coordinate"
    """Resolve the element, then click its centre with a real pointer."""


class NodeSelector(BaseModel):
    """How an action names an element.

    Resolved against a tree read *at the moment of the action*, never against an old snapshot.
    That is what makes a handle safe to carry between runs.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str | None = Field(default=None, description="An id from `tree`, fingerprinted.")
    role: str | None = None
    name: str | None = None
    exact: bool = Field(default=False, description="Match the name exactly, not as a substring.")
    nth: int | None = Field(default=None, ge=0, description="Pick one of several candidates.")
    window: TreeScope = Field(default_factory=TreeScope)

    @model_validator(mode="after")
    def _needs_something_to_match_on(self) -> NodeSelector:
        if self.node_id is None and self.role is None and self.name is None:
            raise ValueError("a selector needs at least one of: id, role, name")
        return self

    def describe(self) -> str:
        parts = []
        if self.node_id:
            parts.append(f"id={self.node_id}")
        if self.role:
            parts.append(f"role={self.role}")
        if self.name:
            parts.append(f"name{'=' if self.exact else '~='}{self.name}")
        if self.nth is not None:
            parts.append(f"nth={self.nth}")
        return " ".join(parts)


__all__ = [
    "Box",
    "OutputFormat",
    "NodeSelector",
    "TreeReason",
    "TreeResult",
    "TreeScope",
    "TreeScopeKind",
    "UINode",
    "Via",
    "WindowInfo",
    "WindowsResult",
]
