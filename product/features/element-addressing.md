---
title: "Element Addressing"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.0"
---

# Element Addressing

[The tree](ui-tree.md) lets an agent read the interface without looking at it. Element addressing
lets it act on the interface without aiming at it.

Taking a `center` from the tree and clicking that coordinate works, and throws away most of what
the tree just said. A coordinate click has to be aimed, so it depends on the scale being known; it
moves the user's real pointer; it fails on an element scrolled out of view that the OS would
happily activate; and there is a race between reading the coordinate and clicking it, during which
the layout can move.

The accessibility API answers all four: ask the button to press itself.

## The ladder

1. **Element, through the platform API** — the OS performs the action. No coordinates at all.
2. **Element, by coordinate** — the tree sees it but exposes no usable action, so click its centre.
   Common: custom-drawn widgets expose a name and nothing else.
3. **Pixel, from vision** — no such element in the tree. Screenshot → ui-locator → `--x/--y`.

Each rung is cheaper, faster and more accurate than the one below. **Rung three is not deprecated
and never will be** — it is the floor the whole ladder stands on.

## Two ways to address, both permanent

```bash
use-computer click --x 120 --y 340                # rung 3 — a pixel, from vision
use-computer click --id 0/2/1/3                   # a handle from `tree`
use-computer click --role button --name "Invia"   # a description, resolved live
```

Which actions accept which:

| | Addressing |
| --- | --- |
| `click`, `double-click`, `right-click`, `scroll` | coordinate **or** element |
| `focus`, `toggle`, `expand`, `collapse`, `select`, `set-value`, `show-menu` | element only |
| `move`, `drag` | coordinate only — aiming a pointer is their whole meaning |
| `type`, `key` | neither — they target **the focus**, not an element |
| `screenshot`, `tree` | neither |

`type` deliberately takes no selector. `type --id X` would have to mean "focus it, then type", and
silent chaining is how automation becomes unreproducible. Focus it yourself, or use `set-value`.

## Resolution is strict, and that is the point

A selector resolves against a tree read **at the moment of the action**, never against an old
snapshot. That is what makes a handle safe.

- **exactly one match** — perform it;
- **no match** — error, with the screenshot fallback, because "the tree cannot see it" is precisely
  the signal to drop to rung three;
- **more than one match** — error listing every candidate with role, name, id and box.

Refusing on ambiguity is a feature. Two buttons named "OK" in two dialogs is the ordinary case, and
a tool that silently picks the first fails a hundred runs later in a way nobody can reproduce. It
hands back the candidates; the agent narrows with a tighter `--name`, a `--window`, or `--nth`.
This is the same stance the tool takes when the coordinate scale is unknown: **refuse rather than
guess.**

`--id` is an accelerator, and it is **fingerprint-checked**: the node still at that path must still
carry the same role and name, or the action refuses and says the tree moved. A path is not an
identity — a row inserted above shifts every index below it.

## `--via` chooses the rung, the result reports it

- **`--via auto`** (default) — the platform API when the node supports it, otherwise a click at its
  centre.
- **`--via action`** — rung one only; error rather than fall back.
- **`--via coordinate`** — resolve the element, then click its centre with a real pointer. Some
  interfaces only respond to genuine pointer input (hover states, drag affordances, canvas
  handlers), and an agent needs to be able to insist.

**Only `click` has a rung-one form among the pointer actions.** `double-click`, `right-click` and
`scroll` address an element to find out *where*, and then act with a real pointer: their `via` is
always `coordinate`, because the accessibility API has no double-click, no secondary click, and no
scroll-by-an-amount. `--via action` on one of them is an error saying so, rather than a silent
substitution of something that is not the same gesture.

The element-only actions are the mirror image: they have no coordinate form, so their `via` is
always `action` and `--via coordinate` is an error. Nothing quietly clicks the centre of a node to
approximate `focus` or `set-value`.

Every result carries the rung actually taken, `"via": "action" | "coordinate"`. An agent that
ignores it still works; one that reads it learns which parts of an application are structurally
addressable and stops paying for vision on the rest.

## `set-value` is not `type`

`set-value` assigns text **atomically and emits no keystrokes**. It is faster, and some
applications ignore it entirely because their validation only fires on key events. `type` emits
real keystrokes into whatever holds focus. Both are correct, for different fields — when a form
refuses to accept a value that is visibly in the box, that is this distinction.

## Coordinates stop being mandatory

Rung one uses no coordinates, so an element-addressed action with `--via action` succeeds even when
the display's scale factor is unknown — the one situation where this tool otherwise refuses to act
at all.

## A whole interaction with no coordinates

```json
[
  {"action": "focus",  "role": "text",   "name": "Destinatario"},
  {"action": "type",   "text": "mario@example.com"},
  {"action": "click",  "role": "button", "name": "Invia"},
  {"action": "tree"}
]
```

One connection, one live resolution per action, and a closing `tree` that returns the resulting
state.

## Agent Notes

- **Ambiguity is an error** — never a first match, never a "best" match. The candidate list is the
  useful part of that error: role, name, id and box for each, so the agent chooses without a second
  round trip.
- Pixel addressing must not regress. Every change here is additive to it.
- `--dry-run` must still **resolve**, and report the node it would have acted on and the `via` it
  would have used. A dry run that skips resolution tells the agent nothing.
- `focus` takes focus from whatever the user was doing, and on the local backend that is their real
  desktop. `click --via action` must not quietly focus first to make itself work.
