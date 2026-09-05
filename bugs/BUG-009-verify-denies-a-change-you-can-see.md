---
title: "--verify says unchanged about a change you can see"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# `--verify` says `unchanged` about a change you can see

## What happens

Two drags on a blank canvas in GNOME Drawing, each drawing a brown line about 200 px long:

```
$ use-computer drag --from-x 300 --from-y 200 --to-x 450 --to-y 300 --verify
drag at (450, 300) — unchanged — 507 ms
$ use-computer drag --from-x 300 --from-y 350 --to-x 480 --to-y 450 --verify
drag at (480, 450) — unchanged — 500 ms
```

Both lines are plainly there in the screenshot `--verify` itself wrote.

## Why

`compare()` reduces both images to **256 px on the longest edge** and then calls it changed only
if the differing fraction exceeds `DEFAULT_THRESHOLD = 0.002`.

Those two numbers multiply into a very large blind spot:

- 1920x1080 becomes 256x144 = 36,864 pixels. A 200x4 px stroke lands on roughly 26x0.5 px, and
  after the downscale averages it against white it may not clear `PIXEL_DELTA = 16` at all.
- The threshold is a fraction of **the whole frame**. At full resolution 0.2% of 1920x1080 is
  **4,147 pixels** — bigger than most things a UI does in response to a click.

So a drawn stroke, a checkbox ticking, a spinner incrementing, a row highlighting and a small
label appearing are all `unchanged`.

## Why it is worse than a wrong number

The skill instructs the agent to act on this signal:

> `changed: false` after a click → the coordinate was probably stale. **Ask ui-locator again. Do
> not click the same pixel twice.**

So a false `unchanged` does not merely under-report. It tells the agent to **throw away a correct
coordinate** and pay for a vision round trip, and the tool sounds confident while doing it. During
the session that found this, it also sent the author to re-read the drag implementation looking
for a timing bug that was not there.

The two errors are not symmetric, and the code currently prefers the damaging one. A false
`changed` costs a look. A false `unchanged` costs the coordinate, the vision call, and the
agent's belief about what is on screen.

## Also

`changed {magnitude:.0%}` renders any real change under half a percent as **`changed 0%`**, which
reads as a denial in the one case the answer was right.

## Expected

A change an agent can see is reported as a change, and the line says **where** rather than what
percentage of the screen it covered — the bbox is what the agent can act on, the percentage is
not.
