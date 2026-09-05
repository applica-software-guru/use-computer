---
title: "screenshot --of crops whatever is in front, not the window the node is in"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# `screenshot --of` crops whatever is in front, not the window the node is in

## What happens

GNOME Drawing was open but behind a terminal. Cropping to one of *Drawing's* nodes:

```
$ use-computer screenshot --window 0/37/0 --of 0/0/2
…/20260905T115055.777Z-node.png 1920x885 of 0/0/2
ok — profile local, backend local, screen 1920x1080, scale 1
```

The file contains **the terminal**. Right size, right path, right node id, `ok`.

## Why

`_crop_to_node` reads the node's box out of the accessibility tree and crops the screenshot it was
handed. That screenshot is a capture of the desktop as it is now. The tree knows where the node
*is*; nothing checks whether anything is *on top of it*.

## Why it matters

This is the single failure in the session that produced no signal of any kind. Every other one
either printed something odd or produced a visibly wrong result. This one hands over a plausible
picture of the wrong application, and the whole point of `screenshot --of` is that the agent is
about to look at it and decide what the element is:

> The loop is **`tree` to locate, `screenshot --of` to look, `click --id` to act.**

Locate in Drawing, look at a terminal, act in Drawing. The vision step, which exists to be the
trustworthy one, becomes the source of the error.

The same blindness applies to every coordinate action: `click --x --y` and `drag` land on whatever
is in front. Confirmed in the same session — two drags meant for a canvas selected text in the
terminal instead, and `--verify` reported the selection highlight as the change.

## Expected

A crop of a node that is covered, or in a window that is not on top, is not returned as if it were
a picture of that node. The tool either raises the window (see the change request that adds a way
to do that) or refuses and says the window is not visible.
