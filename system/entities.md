---
title: "Entities"
status: synced
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
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

### Action

A discriminated union on `action`, with one variant per member of the action set:

`MoveAction`, `ClickAction`, `DoubleClickAction`, `RightClickAction`, `DragAction`,
`ScrollAction`, `TypeAction`, `KeyAction`, `ScreenshotAction`.

Fields common to all: `delay: float | None`, `verify: bool`.
Positional variants carry `Coordinate`s; `TypeAction` carries `text` and an optional rate;
`KeyAction` carries a `KeyCombo`.

### Screenshot

`path: Path | None`, `data: bytes | None`, `width`, `height`, `space`, `captured_at`.

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
scale), `KeySyntaxError`, `ConfigError`, `ActionFailedError`.

## Agent Notes

- Frozen means `model_config = ConfigDict(frozen=True)` on every result model.
- The `Action` union is discriminated on the literal `action` field so a batch JSON file parses
  into typed variants in one `TypeAdapter` call.
