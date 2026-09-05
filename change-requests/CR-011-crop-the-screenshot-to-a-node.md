---
title: "Crop the screenshot to a node"
status: pending
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# Crop the screenshot to a node

## Why

Telegram's message box shows "Write a message…" and its search box shows "Search". Neither string
exists in the accessibility tree: Telegram Desktop paints its own widgets, so the placeholder is
pixels. Checked exhaustively — accessible name, description, attributes, the text interface's
content and default attributes, relations, siblings, and the entire child subtree: empty on both
fields.

So this is a rung-three case and the ladder works as designed. Except that today rung three costs a
screenshot of **1920×1080** — two million pixels — to answer a question about a **653×28** box the
tree already located exactly.

That is the wrong price for the question. The tree knows precisely *where*; only *what* is missing.

## What changes

```bash
use-computer screenshot --of 0/1/0/0/0/13/0
use-computer screenshot --of 0/1/0/0/0/13/0 --pad 8
```

`--of` takes a node id, resolves it the way every element-addressed action does, and writes a PNG
cropped to that node's box, reporting what it cropped:

```json
{"path": "…/20260905T091200.481Z-node.png", "box": [733, 867, 653, 28], "of": "0/1/0/0/0/13/0"}
```

**18,284 pixels instead of 2,073,600.** And the thing being asked about fills the frame instead of
occupying 0.9% of it, which is also the difference between a vision model reading it and guessing.

`--pad N` grows the crop on each side, because a control's own box often excludes the label beside
it.

### It composes with what is already there

The loop becomes: `tree` finds the candidates and their boxes, `screenshot --of` shows one, and
`click --id` acts on it — with `--id` already fingerprint-checked, so the node that was looked at is
the node that gets clicked.

## Deliberately not done

**No cropping to a selector.** `--of` takes an id from a tree just read. A `--role`/`--name`
selector would have to resolve to exactly one node to be croppable, and a caller who can name it
that precisely does not need to look at it.

**No automatic crop on `NodeNotFoundError`.** Tempting and wrong: nothing matched, so there is no
box to crop to. The full-screen fallback is correct there and stays.

**No OCR.** This tool does not read pixels. It produces them for something that does.

## Documentation to update

- `product/features/actions.md` — `screenshot` gains `--of` and `--pad`.
- `product/features/ui-tree.md` — the loop: locate with `tree`, look with `screenshot --of`, act
  with `click --id`.
- `product/features/skill.md` — the cheap way down to vision, where it currently just says "take a
  screenshot".
- `system/entities.md` — `ScreenshotAction.of` and `pad`; `Screenshot.box` and `of`.
- `system/interfaces.md` — the flags and the JSON.

## Agent Notes

- Clip the crop to the screen. A node's box can extend past the edge, and a negative origin or an
  over-wide width must yield a smaller picture, never an error.
- A node with no on-screen position cannot be cropped to. Refuse exactly as a coordinate click
  already refuses on one, and for the same reason: the box is arithmetic, not a place.
- The crop is in **screenshot** pixels and the node's box is in **actuation** units. This is the
  one place in the tool where a box crosses that boundary, so it is the one place the scale must be
  applied rather than assumed. On a HiDPI display an unscaled crop is off by a factor of two and
  looks entirely plausible.
