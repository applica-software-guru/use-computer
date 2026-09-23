---
title: "Zoom when a guess is not enough"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-22T00:00:00.000Z"
---

# Zoom when a guess is not enough

## Why

[CR-011](CR-011-crop-the-screenshot-to-a-node.md) gave `screenshot` a way to crop to an element the
tree already located. It did nothing for the case the tree cannot help with at all: a drawing
program, a map, a game, a remote desktop over VNC — no `root`, or a `?unexposed` region inside one.
That is a pure rung-three interaction, and today rung three is: screenshot the whole screen, ask
ui-locator (or a vision model reading the image directly) where the target is, click the answer.

The screenshot in that loop is usually downscaled before it reaches a vision model — MCP image
tooling commonly caps the longest side around 2000px and reports a scale factor in the response,
expecting the calling model to multiply a coordinate back up. That multiplication is where clicks
go wrong: it is arithmetic a language model does unreliably, on a number it cannot check, and
nothing about a wrong answer looks different from a right one until the click misses.

Dropping the cap does not fix this — larger images cost more and most of them still would not carry
the target at native resolution once a whole desktop is in frame. Removing ui-locator does not fix
it either: specialised grounding models remain meaningfully more accurate at pixel localisation than
a general-purpose vision-language model eyeballing a screenshot, which is the reason rung three uses
one instead of asking the calling model to read pixels directly.

`screenshot --of` already proved the pattern for the case where a node exists: crop tight, so the
thing being asked about fills the frame instead of a fraction of a percent of it. The same pattern
applies to a bare point — crop around a guess, optionally magnify it, and let the caller confirm or
correct the guess against a picture close to native resolution before spending a click on it.

This is not a step to insert into every rung-three click. Most guesses are fine, and looking closer
at every one of them would spend an extra image on the common case to catch the rare one. It is a
tool for the moments a caller should not be confident: a small or crowded target, a click that
already missed, a guess between two plausible candidates. The skill teaches it as a judgement call,
not a mandatory stage of the ladder.

## What changes

### `screenshot --x/--y` crops to a point instead of a node

```bash
use-computer screenshot --x 860 --y 420                # 200x200 around the point (--radius 100)
use-computer screenshot --x 860 --y 420 --radius 40      # tighter, for a small target
```

`--x`/`--y` and `--of` are mutually exclusive — one crop source at a time, the same rule CR-006
already applies to a coordinate versus a selector. `--radius` sets the half-side of the (square)
crop around the point, in screenshot pixels; it defaults to 100.

**Unlike `--of`, a point has no window to look up.** `screenshot --window` continues to mean only
"which tree is `--of`'s id relative to" — it is not consulted by `--x`/`--y`, which crops whatever
is on screen right now, exactly like a bare `screenshot`. `activate --window` first if that is not
what is meant.

### `--zoom` magnifies whatever was captured

```bash
use-computer screenshot --x 860 --y 420 --zoom 4
→ …/20260905T092204.279Z-zoom.png 80x80 at 820,380 zoom 4x -> 320x320
use-computer screenshot --of 0/1/4 --zoom 4    # composes with --of too
```

An integer factor, applied after the crop — by `--x`/`--y` or by `--of`. It buys legibility, not
new detail, the way leaning in on a paper map does: a ten-pixel glyph or icon edge a vision model
glosses over reads cleanly once it is forty pixels wide. `--zoom` refuses on a bare `screenshot`
with neither `--of` nor `--x`/`--y`: there is nothing to zoom into on the whole desktop, only
something to crop first.

The result carries `box` as the crop **before** zoom, and `zoom` as the factor; `width`/`height`
are the file actually written. Recovering a screenshot-space point from one read off the zoomed
picture is one division and one addition: `screenshot_x = box.left + local_x / zoom` — small,
exact, and nothing like the display-wide resize factor a vision pipeline otherwise hands back for
the model to carry through a conversation.

### The loop rung three now teaches, when a guess needs it

```bash
use-computer screenshot                          # the downscaled overview vision looks at
# → ui-locator, or the calling model, guesses a point on it
# small, crowded, or a candidate you would not bet the click on -- look closer first:
use-computer screenshot --x 860 --y 420 --zoom 4  # near-native resolution around the guess
# → confirmed: click the original guess. off: correct --x/--y by the small offset and look again.
use-computer click --x 860 --y 420 --window "Drawing"
```

Otherwise the loop stays what it always was: screenshot, guess, click, confirm. Zooming costs one
more small image, not another vision round trip, so when it is warranted it is cheap: read the crop
yourself before spending the click, and reserve a second ui-locator call for a target still unclear
after looking closer.

## Deliberately not done

**No automatic zoom-and-click in one action.** `screenshot --x/--y --zoom` looks; it does not act.
Folding a click into it would hide the confirmation step this exists to add — the caller would be
back to trusting the first guess, just with an extra picture nobody looked at.

**No non-square crop, no separate width/height flags.** A point plus a radius is what an agent
reading a downscaled overview actually has: an approximate centre, not a box. `--of`'s crop is
already the node's real box; this is deliberately the simpler, guess-shaped tool.

**`--zoom` is capped at 8x.** Past that the picture is mostly interpolation, not legibility, and a
smaller `--radius` gets a closer look for less.

## Documentation to update

- `product/features/actions.md` — `screenshot --x/--y` and `--zoom`, alongside `--of`.
- `system/interfaces.md` — the flags, and the same conversion note.
- `system/entities.md` — `ScreenshotAction`'s `x`, `y`, `radius`, `zoom`; `Screenshot`'s `zoom`.
- `skill/SKILL.md` — a section on when to zoom into a guessed point before clicking it, and rung
  three's description.

## Agent Notes

- `crop()` and the new `magnify()` are the same kind of pure function: image in, image out, no
  backend, no window. `--of` and `--x`/`--y` both resolve to a box and hand it to `crop()`.
- `magnify()` keeps `box` as the pre-zoom crop rect and only updates `width`/`height`/`zoom` — the
  one thing that must never happen is `box` silently becoming post-zoom coordinates, which would
  turn the "one division, one addition" conversion into exactly the kind of silent scale factor
  this change exists to avoid.
- `--x`/`--y` does not call `_activate`: `ScreenshotAction.window` exists only to scope `--of`'s id
  resolution, and a point has no id to resolve. Calling `_activate` there would additionally break
  the one case this feature targets, since `_activate` needs an accessibility provider and VNC —
  the canonical no-tree backend — never has one.
