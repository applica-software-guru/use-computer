---
title: "Coordinate Spaces"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.1"
---

# Coordinate Spaces

A screenshot on a HiDPI display is larger than the space the operating system clicks in. A
2560×1600 screenshot may correspond to a 1280×800 actuation space. An unhandled factor of two makes
every click land in the wrong place, and nothing about the failure looks like a scaling bug.

## The two spaces

- **`screenshot`** — pixels of the captured image. This is the space ui-locator returns
  coordinates in, because it looked at the image.
- **`actuation`** — the units the backend moves the pointer in. What the OS calls "points" on
  macOS; usually identical to screenshot pixels on a non-HiDPI display or over VNC.

## Rules

1. **Every coordinate carries its space.** A bare pair of numbers is not a coordinate; the space is
   part of the value, defaulting to a configured space rather than being assumed per-call.
2. **The backend reports its own spaces.** Each backend exposes its screen size in both spaces and
   the scale factor between them.
3. **`use-computer` scales.** A coordinate given in `screenshot` space is converted into actuation
   units before the action is performed. The result records both.
4. **It refuses to guess.** If the ratio is unknown — the backend cannot report it, or the two
   reported sizes are inconsistent — the action fails with an error explaining what is unknown and
   how to resolve it (capture a screenshot to establish the ratio, or set the scale explicitly in
   the profile).

## Accessibility boxes arrive in actuation units

The accessibility API reports geometry in the OS's own units — the **actuation** space. A node's
`box` and `center` therefore carry `space: actuation` and are never reinterpreted as screenshot
pixels. This is easy to get wrong because on a 1:1 display the two agree, and the bug only appears
on somebody's HiDPI laptop.

## Rung one needs no coordinates at all

Operating an element through the platform API involves no geometry, so it works even when the scale
is unknown — the one situation where this tool otherwise refuses to act. An agent stuck on
"the scale is unknown" can still get work done with `--via action`.

## Overriding

A profile may declare an explicit `scale` when a backend cannot discover it. An explicit scale is
trusted; it is the user's assertion, and `config show` reports which layer it came from.

## Agent Notes

Scaling is a single pure function over (coordinate, source space, target space, scale factor).
Keep it out of the backends; they only *report* their spaces.
