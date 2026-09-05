---
title: "A depth limit is reported as an empty tree, and sends the agent to vision"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# A depth limit is reported as an empty tree, and sends the agent to vision

## What happens

```
$ use-computer tree --window 0/37/0 --depth 1
no tree here (empty); screenshot at …/20260905T115136.137Z-tree.png
```

The same window, read a second earlier without `--depth`, returned 60 nodes: a toolbar, fourteen
tools, a menubar.

## Why

`runner.py` ends the tree path with

```python
if not root.children:
    return self._no_tree(TreeReason.EMPTY, fallback)
```

`--depth 1` returns the root alone, so `root.children` is empty and the branch fires. The same
happens whenever pruning or the node budget legitimately leaves a childless root.

## Why it matters

`empty` is not a size, it is a **diagnosis**: `ui-tree.md` defines it as "the provider works and
the application exposes nothing", and the skill turns that diagnosis into an instruction —

> `reason: unavailable` or `empty` — this application exposes nothing (Qt, Electron, canvas, games
> do this). A screenshot is already attached to that answer. **Go and look.**

So a flag the agent passed itself, to read *less*, comes back as a statement about the
application, with a screenshot attached to make the wrong branch convenient. The agent abandons a
perfectly good tree and pays for vision.

## Expected

A limit the caller asked for is never a property of the application. A tree cut to nothing by
`--depth`, pruning or the budget says so, and says which limit did it, so the way back is obvious.
`empty` stays reserved for a provider that answered with nothing.
