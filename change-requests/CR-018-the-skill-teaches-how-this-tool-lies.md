---
title: "The skill teaches how this tool lies"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# The skill teaches how this tool lies

## Why

CR-014 gave the skill the right spine: two ways of knowing, and how to move between them. A full
agent session against a real application — open a drawing program, draw a tree — showed the spine
holds and the **failure half is missing**.

The session took fifteen commands for work that needed three. Not one of the detours came from not
knowing a flag. Every one came from **believing a report**:

| What the tool said | What was true |
| --- | --- |
| `click radio 'Dark Brown' … via the platform API` | the colour did not change |
| `…/…-node.png 1920x885 of 0/0/2` | a picture of a different application |
| `drag at (450, 300) — unchanged` | a line was drawn, plainly visible |
| `no tree here (empty)` | sixty nodes, read a second earlier |

The skill currently teaches this asymmetry **once**, about coordinates:

> A click that lands on nothing looks exactly like a click that worked.

That sentence is right and it is filed under the wrong heading. It reads as a caveat about rung
three, and the session's failures were on **rung one** — the rung the skill calls exact, and the
one `--via auto` chooses by default. An agent that has read the current skill will trust precisely
the reports that turned out to be wrong.

The fixes in this batch remove the specific defects. They do not remove the shape of the problem,
because the shape is not a defect: an accessibility API returns "I invoked that action", never "the
application did something", and the application is free to ignore it. **That gap is permanent and
the skill has to name it.**

## What changes

### A section on what a result is worth

Not a list of bugs. One idea, stated where the agent will need it: **a result line reports what
was attempted, not what happened.** Then the three things that follow from it:

- **`[actions]` is what the platform will accept, not what will work.** A colour swatch that
  advertises `[click,focus,select]` accepts `click` and does nothing with it; `select` is the one
  that carries the meaning. When an action reports success and the screen disagrees, the next move
  is **another action on the same node**, not vision.
- **Confirm by re-reading, not by diffing.** After an element action, `tree` says *what* the state
  is now. Change detection only says that some pixels moved, it has a floor below which it says
  nothing at all, and it cannot tell your click apart from a clock. This already exists in the
  skill as an aside about `via: action`; it is the general rule and belongs in the open.
- **Coordinates land in whatever window is in front.** Pass `--window` so the tool brings the right
  one forward, and know that without it a coordinate means "wherever the pointer is now".

### The blind spot, and what to do about it

`?unexposed x,y wxh` on a node (CR-015) says the platform is not describing that region. It is
the normal state of a canvas, a map, a chart, a game, a PDF view. It is not an error and there is
nothing to expand: it is the cue to switch to pixels **for that region only**, and the region is
given, so `screenshot --of` that node and aim inside it.

This gives the skill the case it does not currently have. Today it teaches two clean states — the
tree answers, or the tree is empty and hands you a picture. The common real state is **a rich tree
with a hole in it**, and until now nothing named it.

### Where `--via` is, and where it is not

The skill calls `--via` "the one flag worth understanding" and shows it as if it were universal.
It is not, and the CLI is right: `select`, `toggle`, `expand`, `collapse`, `set-value` and
`show-menu` have no coordinate form, so they take no `--via`. Passing it is a usage error, which
is what an agent following the current skill gets.

### `activate`

One line where the ladder is, because it is now rung zero of any coordinate work.

## What does not change

The two-modes table stays as the spine. The ladder stays. Nothing here restates `--help`: which
report to trust, and what an accepted-and-ignored action looks like, are exactly what `--help`
cannot say.

## Agent Notes

- The skill's test asserts that everything the skill names exists. Every command, flag and marker
  introduced here — `activate`, `--window` on coordinate actions, `?unexposed` — must be reachable
  from the CLI, and the `--via` claim must match which commands actually accept it.
- Keep it shorter than the sum of its parts. The failure section replaces scattered warnings; it
  does not add a fourth place where verification is discussed.
