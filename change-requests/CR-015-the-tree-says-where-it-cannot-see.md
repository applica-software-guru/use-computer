---
title: "The tree says where it cannot see"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# The tree says where it cannot see

## Why

An agent was asked to draw a tree in GNOME Drawing. `use-computer tree` answered well: the
toolbar, fourteen named tools, the menubar, a palette of forty colours with names like
"Dark Brown". Everything except **the one thing the task was about**.

```
0/0/2 panel !horizontal 0,106 1920x885 +4
  0/0/2/0 scrollpane [focus] 0,106 163x885      <- the tool sidebar
    …
```

The panel is 1920 px wide. Its only child covers 163. The remaining **1757x885 is the canvas**,
and it is not in the tree — not pruned, not summarised, not truncated. Absent, including under
`--full`.

Nothing marks the hole. `reason` does not fire, because the provider worked and returned plenty.
No screenshot is attached, because as far as the tool is concerned nothing went wrong. The tree
looks complete, and an agent has no way to tell a window that exposes everything from a window
that exposes everything *except the part it needs*.

This is not an edge case. It is every drawing program, every map, every chart, every game, every
video canvas, every PDF view, every Electron surface that draws its own content — the entire class
of applications for which the answer "use the screenshot" is right. The tool currently gives that
class its least useful answer: a rich, confident, incomplete tree.

The existing escape hatches all assume the tree is empty. `ui-tree.md` documents `unavailable`,
`denied` and `empty`, and the skill turns them into "go and look". None of them describe an
application that exposes a full menu system around a blind spot.

## What changes

**A node whose children do not account for its own area says so.**

```
# id role "name" !states [actions] x,y wxh +offscreen ?unexposed
0/0/2 panel 0,106 1920x885 ?unexposed 163,106 1757x885
```

The marker names the region, in the same actuation units as every other box, because the region
*is* the answer: it is where `screenshot --of` should point and where a rung-three coordinate has
to land.

**The rule.** For a kept node with a positioned box and at least one positioned child, take the
union bounding box of those children and the largest uncovered strip of the parent that remains.
Report it when it is **at least 25% of the node's area and at least 10,000 square pixels**.

Both bounds earn their place on the measured window:

- The canvas panel: uncovered 1757x885, 92% of the node. Reported.
- Its parent, `0/0`: children tile it completely. Silent.
- The window root: a 1920x32 strip above the menubar, 3% of the node. Silent — that is decoration,
  not a canvas.

One marker on the one node that has a blind spot, and nothing anywhere else. A node with **no**
positioned children is not reported: a leaf is not a container that failed to describe itself.

**`--full` does not turn this off.** It is not an abbreviation, so there is nothing to expand; it
is a statement about the platform's coverage, and it is the one thing `--full` cannot recover.

## What this is not

Not an attempt to see into the canvas. The tool cannot, and should not pretend to. The change is
that the agent is **told there is something it cannot see, and exactly where** — which is the
difference between choosing to look and not knowing there was anything to look at.

## Agent Notes

- The marker is a report, never a filter: the node is kept and addressable exactly as before.
- Compute it from positioned children only. An unpositioned child covers nothing, so it must not
  be allowed to hide a blind spot by contributing an arithmetic box.
- This lands in `selectors.py` with the rest of the policy, so all three platforms share it and it
  tests without a desktop.
