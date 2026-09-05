---
title: "An element action reports success when the platform accepted and ignored it"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# An element action reports success when the platform accepted and ignored it

## What happens

A colour swatch in GNOME Drawing's palette. The tree reports it fully:

```
0/1/0/1/0/0/11 radio "Dark Brown" [click,focus,select] 337,833 48x32
```

```
$ use-computer click --id 0/1/0/1/0/0/11 --role radio --name "Dark Brown"
click radio 'Dark Brown' at 0/1/0/1/0/0/11 via the platform API — 600 ms
ok — profile local, backend local, screen 1920x1080, scale 1
```

The colour does not change. The next stroke is still red.

Two things do work, and they identify the fault exactly:

```
$ use-computer click  --id … --role radio --name "Dark Brown" --via coordinate   # works
$ use-computer select --id … --role radio --name "Green"                          # works
```

## Why

Not "AT-SPI lied". The node offers three actions and we map the `click` **command** onto the
`click` **action**. GTK's colour swatch implements that action as a no-op and returns true from
`do_action` — true means *the action exists and was invoked*, not *something happened*. `select`
is the action that carries the meaning for this widget, and it works.

`runner.py` takes the boolean at face value:

```python
done = self._provider().perform(matched.id, wanted, …)
if done:
    return _Outcome(via=Via.ACTION)
```

## Why it matters

This is rung one — the rung both `ui-tree.md` and the skill present as the exact one:

> Structure first, always: it is cheaper and **it is exact**.

And `--via auto`, the documented default, chooses it *because* the node advertises `click`. So the
default path picks the broken action, reports success, and the agent proceeds on a false premise:
in this session, three later strokes came out in the wrong colour before anyone looked.

`[actions]` is a list of what the platform will *accept*, not of what will *work*. Nothing in the
docs says so, and the code assumes the opposite.

## Expected

Two changes, both narrow:

- For a node whose role makes selection the activation — `radio`, `listitem`, `option`,
  `treeitem`, `tab`, `menuitem` — a `click` command prefers the `select` action when the node
  offers it.
- Where the action should have left an observable trace on the node itself (`checked`,
  `selected`), the node is re-read and the line says so when nothing moved, rather than reporting
  a success nobody verified.
