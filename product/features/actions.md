---
title: "Actions"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.3"
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
| `screenshot` | Capture the current screen, write it to a file, and return its path with the coordinate space and size. |
| `tree` | Read the accessibility tree of the focused window (or the desktop) and return it. |
| `focus` | Give keyboard focus to an element. |
| `toggle` | Flip a checkbox, switch or toggle button. |
| `expand` | Open a disclosure, combo box or tree item. |
| `collapse` | Close one. |
| `select` | Select an item in a list, tab strip or menu. |
| `set_value` | Assign an element's text or value atomically, without keystrokes. |
| `show_menu` | Open an element's context menu through the platform, where it offers one. |

`double_click` and `right_click` are distinct actions rather than parameters of `click`, because
that is how the calling agent thinks about them and because backends implement them differently.
The same reasoning puts `focus`, `toggle`, `expand` and the rest in this table as peers rather than
behind a `--do <verb>` flag on some general-purpose command.

## Addressing an element

An action can name its target by coordinate or by element — see
[element-addressing.md](element-addressing.md):

| | Addressing |
| --- | --- |
| `click`, `double_click`, `right_click`, `scroll` | coordinate **or** element |
| `focus`, `toggle`, `expand`, `collapse`, `select`, `set_value`, `show_menu` | element only |
| `move`, `drag` | coordinate only — aiming a pointer is their whole meaning |
| `type`, `key` | neither — they target **the focus**, not an element |
| `screenshot`, `tree` | neither |

An element-addressed action takes `--via auto|action|coordinate`: whether to operate the element
through the platform API, or click the centre of its box. `auto` prefers the API and falls back to
the click; the result always reports which one it used.

Among the pointer actions only `click` has a platform-API form. `double_click`, `right_click` and
`scroll` use an element to find *where* and then act with a real pointer, because the accessibility
API has no double-click, no secondary click and no scroll-by-an-amount. The element-only actions
are the mirror image: no coordinate form, so `--via coordinate` on one of them is an error.

### `set_value` is not `type`

`set_value` assigns text atomically and emits **no keystrokes**. It is faster, and some
applications ignore it because their validation only fires on key events. `type` sends real
keystrokes to whatever holds focus. Both are correct, for different fields.

## Common parameters

Every action accepts:

- **`delay`** — seconds to wait after the action, so the application can react.
- **`space`** — the coordinate space the action's coordinates are expressed in
  (see [coordinate-spaces.md](coordinate-spaces.md)).
- **`verify`** — take a screenshot before and after and report whether the screen changed
  (see [change-detection.md](change-detection.md)).

## Screenshots are files

A screenshot is never returned as bytes. It is written to a file and the result carries the path.
An agent that wants the pixels reads the file, and pays for it only when it decides to — rather
than having a megabyte of base64 poured into its context by a batch it did not think about.

`screenshot --out PATH` writes there. Without `--out` it writes into the configured screenshot
directory under a name that sorts and does not collide.

### `screenshot --of NODE_ID` crops to one element

The tree knows exactly *where* something is; sometimes only *what* is missing — a placeholder an
application paints rather than exposes, say. Answering that with a picture of the whole screen is
the wrong price:

```bash
use-computer screenshot --window "Chat" --of 0/1/0/0/0/13/0 --pad 8
→ …/20260905T092204.279Z-node.png 653x28 of 0/1/0/0/0/13/0
```

**18,284 pixels instead of 2,073,600**, with the thing being asked about filling the frame rather
than occupying 0.9% of it. `--pad N` grows the crop each side, because a control's box often
excludes the label beside it. An id is scope-relative, so `--of` takes `--window` too.

## What an action prints

One line, on stdout:

```
click button 'Invia' at 0/2/1/3 via the platform API — 12 ms
```

A `screenshot` prints its path and nothing else, because the path is the answer.

## Results

Each action produces a result recording what was requested, the coordinates as resolved into
actuation units, whether it was performed or skipped (dry-run), how long it took, and — when
`verify` was requested — whether the screen changed. An element-addressed action also records the
node it matched and the `via` it took. Results are frozen models; nothing mutates them after the
action ran.

## Agent Notes

- Coordinates are never silently reinterpreted. An action whose coordinate space cannot be
  reconciled with the backend's fails with a clear error.
- `type` sends text, not key names. `ctrl+a` typed through `type` is the literal seven characters.
- An action operating an element through the API moves no pointer and paints no hover state, so
  `verify` sees less pixel change than the equivalent coordinate click. A small magnitude there is
  not failure.
