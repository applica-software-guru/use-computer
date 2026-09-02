---
title: "Actions"
status: new
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
---

# Actions

The action set is the whole surface of what `use-computer` does to a screen. Every backend
implements all of it; nothing else is added on top.

## The actions

| Action | Meaning |
| --- | --- |
| `move` | Move the pointer to a coordinate. |
| `click` | Press and release a mouse button at a coordinate (or where the pointer is). |
| `double_click` | Two clicks within the platform double-click interval. |
| `right_click` | Click with the secondary button. |
| `drag` | Press at a start coordinate, move to an end coordinate, release. |
| `scroll` | Scroll by an amount, vertically or horizontally, at a coordinate. |
| `type` | Type a literal string as keystrokes, at a rate applications do not drop characters from. |
| `key` | Press a key combination, e.g. `ctrl+shift+t`, using the normalised key syntax. |
| `screenshot` | Capture the current screen and return it (path and/or base64) with its coordinate space and size. |

`double_click` and `right_click` are distinct actions rather than parameters of `click`, because
that is how the calling agent thinks about them and because backends implement them differently.

## Common parameters

Every action accepts:

- **`delay`** — seconds to wait after the action, so the application can react.
- **`space`** — the coordinate space the action's coordinates are expressed in
  (see [coordinate-spaces.md](coordinate-spaces.md)).
- **`verify`** — take a screenshot before and after and report whether the screen changed
  (see [change-detection.md](change-detection.md)).

## Results

Each action produces a result recording what was requested, the coordinates as resolved into
actuation units, whether it was performed or skipped (dry-run), how long it took, and — when
`verify` was requested — whether the screen changed. Results are frozen models; nothing mutates
them after the action ran.

## Agent Notes

- Coordinates are never silently reinterpreted. An action whose coordinate space cannot be
  reconciled with the backend's fails with a clear error.
- `type` sends text, not key names. `ctrl+a` typed through `type` is the literal seven characters.
