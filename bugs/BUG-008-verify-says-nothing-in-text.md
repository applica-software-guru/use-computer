---
title: "--verify reports nothing once stdout is text"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# `--verify` reports nothing once stdout is text

## What happens

```
$ use-computer click --x 200 --y 200 --verify
click at (200, 200) — 41 ms
```

The comparison ran. The after-screenshot was captured and written. Both are in the envelope:

```json
"change": {"changed": true, "magnitude": 0.06, "bbox": [0, 0, 1920, 105]},
"screenshot": {"path": "…/20260905T093017.762Z-click.png"}
```

Neither reaches stdout. A caller using the default output gets no feedback at all from the flag
whose entire purpose is feedback.

## Why

Inverting the output contract ([CR-010](../change-requests/CR-010-text-is-the-output.md)) moved
every result field from the envelope into a rendered line, and the line was written for the fields
an action always has. `change` and the verify screenshot only exist when `--verify` was passed, so
they were simply not carried across.

Two things are lost, and both are load-bearing:

- **The change signal.** `changed: false` after a click means the coordinate was stale; it is what
  stops an agent clicking the same wrong pixel forever. That is the reason change detection exists.
- **The screenshot path.** [CR-004](../change-requests/CR-004-screenshots-are-files.md) made
  `--verify` report the picture it had already captured precisely so an agent would not follow a
  verified action with a `screenshot` call. Without the path it does, and pays twice.

## What it should do

Say both, on the action's own line and one indented line beneath it:

```
click at (200, 200) — changed 6% — 41 ms
  /home/you/.local/share/use-computer/screenshots/20260905T093017.762Z-click.png
```

and, for the case that matters most:

```
click at (412, 260) — unchanged — 38 ms
```

`unchanged` as a word, not a false: it is the one an agent has to notice.

## Agent Notes

This is the failure the change request warned about in its own notes — "a line must never be a
truncated JSON object" was meant to stop fields being abbreviated, and instead a field was dropped.
Anything a result carries conditionally needs a place in the line, or it does not survive the
format.

Present in 0.2.1 as published.
