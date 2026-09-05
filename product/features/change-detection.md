---
title: "Change Detection"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.3"
---

# Change Detection

A click that lands on nothing looks exactly like a click that worked. Without feedback the calling
agent retries a stale coordinate forever.

## What it does

With `verify` enabled, an action captures a screenshot before and after itself and reports whether
the screen actually changed:

- `changed` — true/false.
- a magnitude — the fraction of pixels that differ, so the agent can distinguish a blinking cursor
  from a new dialog.
- optionally the bounding box of the changed region, which tells the agent *where* something
  happened.

A threshold (configurable, with a sensible default) separates noise — a caret, a clock — from a
real change.

## What it prints

On the action's own line, and the picture beneath it:

```
click at (200, 200) — changed 6% — 41 ms
  /home/you/.local/share/use-computer/screenshots/20260905T093017.762Z-click.png

click at (412, 260) — unchanged — 38 ms
```

**`unchanged` as a word**, not a false: it is the one an agent has to notice, because it means the
coordinate was stale. And the path is there because the capture is already paid for — an agent that
had to ask for it again would pay twice for one picture.

## How the agent uses it

`changed: false` after a click means the coordinate was probably stale: ask ui-locator again
rather than clicking the same pixel a second time. `changed: true` with a tiny magnitude in a
corner is a clock tick, not a response.

The after-screenshot is written to a file and its path comes back in the same result. Verification
is capturing the screen anyway, so reporting where it landed costs nothing — and it saves the agent
the round trip of asking for a screenshot it has already paid for. This is why there is no separate
flag for "screenshot after the action": `verify` is it.

## Against an element action, expect less

An action performed through the accessibility API moves no pointer and paints no hover state, so it
changes fewer pixels than the equivalent coordinate click for the same outcome. A small `magnitude`
there is not evidence of failure. When the target was an element, re-reading the
[tree](ui-tree.md) is the better feedback signal: it says *what* changed rather than merely *that*
something did.

Change detection is **advisory**. A false result does not fail the action; the action was performed
and the agent decides what it means.

## Cost

Verification costs two screenshots per action, so it is **opt-in** per action or per run. In a
batch, an action's after-screenshot can serve as the next action's before-screenshot when nothing
intervened.

## Agent Notes

Comparison is done with pillow on downscaled greyscale images — the goal is "did something happen",
not pixel-perfect diffing. Keep the comparison in its own module so the metric can change without
touching the action layer.
