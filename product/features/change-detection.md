---
title: "Change Detection"
status: synced
author: ""
last-modified: "2026-09-05T12:40:00.000Z"
version: "2.0"
---

# Change Detection

A click that lands on nothing looks exactly like a click that worked. Without feedback the calling
agent retries a stale coordinate forever.

## What it does

With `verify` enabled, an action captures a screenshot before and after itself and reports whether
the screen actually changed:

- `changed` — true/false.
- the **bounding box** of the changed region, which is what the agent can act on.
- a magnitude, kept for the JSON form and for a caller that wants a number.

A threshold separates noise — a caret, a clock — from a real change.

### The two errors are not symmetric, and the metric has to know it

A false `changed` costs a look. A false `unchanged` costs the coordinate: this feature's own advice
is to stop trusting it and pay for a vision round trip, so an under-sensitive metric does not merely
under-report, it **actively sends a correct coordinate to the bin**.

That is not hypothetical. A metric that compares images downscaled to 256 px on the longest edge,
and calls a change real only above 0.2% of the whole frame, is blind to roughly the first four
thousand pixels of any response — a drawn stroke, a ticked checkbox, an incremented spinner, a
highlighted row. Every one of those reported `unchanged` while plainly visible on screen.

So the sensitivity is set by **what a UI actually does in response to a click**, not by what is
convenient to compute:

- Comparison runs at **512 px on the longest edge**, not 256. Four times the area, still cheap,
  and a thin stroke survives the downscale instead of averaging away against the background.
- A change is real when the changed region's **longest side** reaches 16 screenshot pixels, or
  when the fraction clears the threshold. Extent, not a pixel count: a count means different
  things on different image sizes and cannot tell a thin wide stroke from a small blob. A caret is
  2x8 and stays noise; a 200x4 stroke and a 16x16 checkbox are changes.
- The box is therefore computed **before** the verdict, not after it. It is what decides, and it
  is the only part of this an agent can act on.

## What it prints

On the action's own line, and the picture beneath it:

```
click at (200, 200) — changed 604x312 at 40,120 — 41 ms
  /home/you/.local/share/use-computer/screenshots/20260905T093017.762Z-click.png

click at (412, 260) — unchanged — 38 ms
```

**The line carries the box, not the percentage.** `changed 6%` cannot be acted on, and rounds a
real change of a few thousand pixels to `changed 0%`, which reads as a denial. `604x312 at 40,120`
says a dialog opened; `12x18 at 1904,8` says a clock ticked. The magnitude stays in the JSON form
for a caller that wants to threshold it itself.

In a batch, where every capture lands in the same directory, the lines carry filenames and the
closing line names the directory once — see [configuration.md](configuration.md).

**`unchanged` as a word**, not a false: it is the one an agent has to notice, because it means the
coordinate was stale. And the path is there because the capture is already paid for — an agent that
had to ask for it again would pay twice for one picture.

## How the agent uses it

`changed: false` after a click means the coordinate was probably stale: ask ui-locator again
rather than clicking the same pixel a second time. A small box in a corner is a clock tick, not a
response.

**Read it against what you asked for.** A change smaller than the thing you expected is the useful
signal: a click meant to open a dialog that reports a 12x18 box in the corner did not open a
dialog. That comparison is the agent's, not the tool's — which is why the box is reported and not
just a verdict.

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

The compare size, the pixel delta and the extent floor are one decision, not three: raising the
size without lowering the floor changes nothing. The floor is expressed in **screenshot** pixels
and the box is scaled back before it is applied, so the rule means the same thing whatever the
compare size is — which a floor counted in pixels of the downscaled image would not. There is a
test for a thin stroke on a full-screen image precisely because that is the case the previous
metric got wrong, and one for a caret because that is the case it got right.
