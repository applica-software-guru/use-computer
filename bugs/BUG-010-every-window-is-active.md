---
title: "windows marks several windows active"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# `windows` marks several windows active

## What happens

```
id      app                           role    title                     pid     box              active
0/19/0  cinnamon                      window                            2067    0,0 1921x1080    *
0/26/0  nemo-desktop                  window  Desktop                   2121    0,0 1920x1038
0/34/0  Codex                         window  ChatGPT                   144775  0,0 1920x1038    *
0/37/0  com.github.maoschanz.drawing  window  Unsaved file ~ Pencil     385002  0,0 1920x1038    *
```

Three stars. Only one window can be the one `--window focused` resolves to.

## Why

`atspi.py` decides it with `"active" in states or "focused" in states`. AT-SPI reports
`focused` per application — each app marks *its own* most recently focused window — so on a
desktop with several running applications the flag is true many times over.

## Why it matters

`ui-tree.md` states the column's whole job: "`active` says which one `focused` resolves to." A
column that is true for three of ten windows answers nothing, and it is the first thing the skill
tells an agent to read:

> Make this call first: it gives you the `--window` value everything else needs, and tells you
> which window `focused` will resolve to.

An agent that trusts it picks the wrong window and then reads a tree, clicks and verifies inside
it, all consistently and all wrong.

## Expected

At most one window carries the mark, and it is the one `--window focused` resolves to — the same
decision, made once. If the platform cannot say, no window is marked rather than several.
