---
title: "Entities"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "2.0"
---

# Entities

Every data model is a pydantic 2 model. **Result models are frozen** — once an action has run, what
it did does not change.

### CoordinateSpace

An enum: `screenshot` | `actuation`. The space a coordinate is expressed in.

### Coordinate

`x: int`, `y: int`, `space: CoordinateSpace`. A bare pair of numbers is never a coordinate; the
space travels with it.

### ScreenInfo

Reported by a backend about itself:

- `width`, `height` — size in actuation units
- `screenshot_width`, `screenshot_height` — size in screenshot pixels
- `scale: float | None` — the ratio; `None` means unknown, and coordinate conversion refuses
  rather than guessing

### MouseButton

`left` | `right` | `middle`.

### ScrollDirection

`up` | `down` | `left` | `right`.

### KeyCombo

A parsed key combination: `modifiers: tuple[str, ...]`, `key: str`, both canonical names. Produced
by parsing the normalised key syntax; backends map it to their own vocabulary.

### Box

`x`, `y`, `width`, `height`, `space: CoordinateSpace`. The geometry of a UI element. The
accessibility API reports it in **actuation** units.

**Serialises as `[x, y, width, height]`**, and parses from either that array or the object form.
The space is not repeated on every node because it is always `actuation`: the keys cost more than
the values, and a tree carries thousands of them.

### UINode

One element of the accessibility tree:

- `id: str` — a structural path in the **full** tree, e.g. `0/2/1/3`
- `role: str` — canonical, normalised across platforms
- `name: str | None`, `value: str | None`
- `states: tuple[str, ...]` — canonical state names. On the way out only the **notable** ones
  survive: what almost every node reports (`showing`, `enabled`, `focusable`, `visible`,
  `sensitive`, `selectable`) says nothing and is dropped, while `checked`, `selected`, `expanded`,
  `modal` and the rest stay. **`disabled` is synthesised** when `enabled` is absent — the platforms
  report the positive and stay silent on the negative, which is the one case an agent must not miss
- `offscreen_children: int` — descendants not on screen, counted rather than expanded; `0` when
  there are none, or when they were expanded
- `actions: tuple[str, ...]` — the action names this node supports; empty means it can only be
  clicked by coordinate
- `box: Box`, `center: Coordinate`
- `children: tuple[UINode, ...]`

### WindowInfo *(frozen)*

One entry of what `windows` returns: `id`, `title: str | None`, `role`, `pid: int | None`,
`box: Box`, `active: bool`.

`pid` lives here and on nothing else. A window list is where it is worth its bytes; on every node
of a tree it is repetition.

### TreeScope

What to snapshot: `kind: focused | all | title | pid` with an optional `value`. Parsed from
`--window`, where `@1234` means a pid and anything else a title.

### TreeReason

An enum: `unavailable` | `denied` | `empty`. Why a tree could not be returned — no provider for
this platform or backend, the OS refused the permission, or the application exposes nothing.

### TreeResult *(frozen)*

- `root: UINode | None`
- `node_count: int`, `truncated: bool`, `truncated_ids: tuple[str, ...]`
- `reason: TreeReason | None` — set only when `root` is `None`
- `screenshot: Screenshot | None` — the fallback capture, when one was taken
- `path: Path | None` — where the tree was written, when `--out` asked for a file; `root` is then
  omitted, which is the point of asking

### NodeSelector

How an action names an element: `node_id: str | None`, `role: str | None`, `name: str | None`,
`exact: bool`, `nth: int | None`, `window: TreeScope`. At least one of `node_id`, `role` or `name`
must be set.

### Via

An enum: `auto` | `action` | `coordinate`. Which rung an element-addressed action should take;
`ActionResult.via` records which one it actually took, and is never `auto`.

### Action

A discriminated union on `action`, with one variant per member of the action set:

`MoveAction`, `ClickAction`, `DoubleClickAction`, `RightClickAction`, `DragAction`,
`ScrollAction`, `TypeAction`, `KeyAction`, `ScreenshotAction`, `TreeAction`, `FocusAction`,
`ToggleAction`, `ExpandAction`, `CollapseAction`, `SelectAction`, `SetValueAction`,
`ShowMenuAction`, `WindowsAction`.

Fields common to all: `delay: float | None`, `verify: bool`.
Positional variants carry `Coordinate`s; `TypeAction` carries `text` and an optional rate;
`KeyAction` carries a `KeyCombo`; `SetValueAction` carries `value`.

Element-addressable variants carry `selector: NodeSelector | None` and `via: Via`.
`ClickAction`, `DoubleClickAction`, `RightClickAction` and `ScrollAction` accept **either** a
coordinate or a selector, never both — a validator rejects the pair rather than deciding which
wins. `FocusAction`, `ToggleAction`, `ExpandAction`, `CollapseAction`, `SelectAction`,
`SetValueAction` and `ShowMenuAction` require a selector and take no coordinate at all.

### Screenshot

`path: Path`, `width`, `height`, `space`, `captured_at`.

A screenshot that has been surfaced to the caller always has a path: it is a file. `data` is held
in memory only while a comparison needs it, is never serialised, and never crosses the JSON
boundary.

### ChangeReport

The outcome of change detection: `changed: bool`, `magnitude: float` (fraction of differing
pixels), `threshold: float`, `bbox: tuple[int, int, int, int] | None`.

### ActionResult *(frozen)*

- `action` — the action as requested
- `resolved` — coordinates converted into actuation units
- `performed: bool` — false under dry-run
- `duration_ms: float`
- `change: ChangeReport | None`
- `screenshot: Screenshot | None`
- `tree: TreeResult | None` — for `tree`
- `windows: tuple[WindowInfo, ...] | None` — for `windows`
- `matched: UINode | None` — the node a selector resolved to
- `via: Via | None` — the rung actually taken; `action` or `coordinate`, never `auto`
- `error: ErrorInfo | None`

### RunResult *(frozen)*

One per invocation, and what the CLI serialises to stdout:

- `profile: str`
- `backend: str`
- `screen: ScreenInfo`
- `results: list[ActionResult]`
- `ok: bool`
- `failed_index: int | None`

### BackendProfile

A named entry in `config.toml`: `name`, `backend` (`local` | `vnc`), plus backend-specific
fields (`host`, `port`, `password` for vnc; `allow_local` for local) and an optional explicit
`scale`.

### Settings

The pydantic-settings model, env prefix `USE_COMPUTER`. Holds the resolved configuration plus, for
each field, the **layer** it came from — which is what `config show` prints.

### Errors

`UseComputerError` (base) → `BackendNotAvailableError` (names the extra to install),
`PermissionDeniedError` (names the OS permission), `CoordinateSpaceError` (unknown or inconsistent
scale), `KeySyntaxError`, `ConfigError`, `ActionFailedError`,
`UITreeUnavailableError` (no provider — names both the extra and, on Linux, the system package),
`NodeNotFoundError` (nothing matched), `AmbiguousNodeError` (carries the candidates),
`ActionNotSupportedError` (names the actions the matched node does support).

## Agent Notes

- Frozen means `model_config = ConfigDict(frozen=True)` on every result model.
- The `Action` union is discriminated on the literal `action` field so a batch JSON file parses
  into typed variants in one `TypeAdapter` call.
- `AmbiguousNodeError` carries the candidate `UINode`s, not a formatted string. The CLI renders
  them; the Python API hands them over as objects.
- `UINode.children` is a tuple and every result model is frozen, so a tree can be shared between an
  action's resolution step and the result it reports without anyone mutating it in between.
