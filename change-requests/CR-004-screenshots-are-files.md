---
title: "Screenshots are files, and verify returns one"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-04T00:00:00.000Z"
---

# Screenshots are files, and verify returns one

## Why

A screenshot is currently returned to the calling agent as base64 inside the JSON, and the
`--base64` flag that supposedly controls this does not: without `--out`, the bytes are emitted
anyway. Capturing the screen with no arguments prints 211 KB of base64.

Worse, `--verify` already captures the screen after every action it checks, and every one of those
captures is serialised the same way. A batch of five verified clicks pours a megabyte of base64
into the agent's context, which is the most expensive place it could possibly go.

Meanwhile `xdg_data_dir()` has been defined and unused since the beginning — the place these files
should have been going all along.

## What changes

**Base64 is removed, not made opt-in.** No `--base64` flag, no `base64` field in the JSON, no
`Screenshot.base64()`. A screenshot is a file; the JSON carries its path. An agent that wants the
pixels reads the file, and pays for it only when it decides to.

**`screenshot` writes a file whether or not it was told where.** With `--out`, there; without,
into the screenshot directory under a name that sorts and does not collide —
`20260904T103012.481Z-screenshot.png`.

**The screenshot directory is configuration.** `screenshot-dir`, resolved through the same layers
as everything else, defaulting to the XDG *data* directory (`use-computer/screenshots`) — never a
cache directory, and never the repository.

**`--verify` returns the path of the screenshot it already took.** It is capturing the screen
after the action regardless; writing that capture down and reporting where costs nothing extra,
and it saves the calling agent the round trip of asking for a screenshot it has already paid for.

There is deliberately **no separate `--screenshot` flag**. `--verify` is the way to ask for the
post-action screen, and one concept is better than two that overlap.

## Deliberately not done

Old screenshots are not pruned. The directory grows, and that is the user's to manage for now.

## Documentation to update

- `product/features/actions.md` — the screenshot action returns a path, not bytes.
- `product/features/change-detection.md` — verify reports where the after-screenshot was written.
- `product/features/configuration.md` — the `screenshot-dir` setting.
- `system/entities.md` — `Screenshot` carries a path; `ScreenshotAction` loses `base64`.
- `system/interfaces.md` — the CLI options and the JSON shapes.

## Agent Notes

The comparison still works on bytes in memory; only what crosses the JSON boundary changes. In a
batch, the after-screenshot of one action is already reused as the before-screenshot of the next —
it must be written once, not twice.
