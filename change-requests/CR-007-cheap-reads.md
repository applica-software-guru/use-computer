---
title: "Cheap reads: list the windows, and stop paying for what is not on screen"
status: pending
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# Cheap reads: list the windows, and stop paying for what is not on screen

## Why

`tree` works and is still too expensive to send to a model. Measured on a real desktop, one
terminal window is **19.9 KB of JSON for 73 nodes**, and getting to that window at all means
dumping a two-level tree of the whole desktop and reading the titles out of it.

Two separate problems, and neither is solved by another budget:

1. **There is no cheap first call.** An agent's first question is "what is open?", and the only way
   to ask it is `tree --window all --depth 2` — a tree read, parsed for titles it happens to
   contain. That is a dump standing in for a lookup.
2. **Most of a window's tree is not on screen.** Of those 73 nodes, **55 are the items of closed
   menus** — real, operable through the platform, and not visible. They are worth keeping
   *reachable*; they are not worth spending three quarters of the payload on before anyone asks.

## What changes

### `use-computer windows`

The missing first call. A flat list of what is open, at one depth-2 read of the desktop:

```json
[
  {"id": "0/29/0", "title": "◐ Estrazione albero UI", "role": "window",
   "pid": 4711, "box": [0, 0, 1920, 1038], "active": true},
  {"id": "0/33/0", "title": "Roberto Conterosito – (1379)", "role": "panel",
   "pid": 5210, "box": [331, 130, 1152, 784], "active": false}
]
```

**Measured: 12 windows, 1,429 bytes, 119 bytes each.** That is the whole desktop for less than a
fifteenth of one window's tree, and it is what an agent should read before it reads anything else:
it yields the `--window` value every later call needs, and `active` says which one `focused` will
resolve to.

`pid` appears here and **not** on `UINode`. A window list is where a pid is worth its bytes; on
every node it is repetition.

### A compact node, as the default

The node shape changes. Measured over the same 73 nodes:

| Shape | Bytes | Per node | |
| --- | --- | --- | --- |
| Today | 19,752 | 271 B | |
| Notable states only | 14,671 | 201 B | −26% |
| ... and `box` as `[x, y, w, h]` | 10,948 | 150 B | **−45%** |

Two changes, both of which remove noise rather than information:

- **`states` carries only what is surprising.** `showing`, `enabled`, `focusable`, `visible`,
  `sensitive` and `selectable` are what almost every node says, so they say nothing. What changes a
  decision — `disabled`, `checked`, `selected`, `expanded`, `modal` — stays. Dropping the field
  entirely was measured too, and saves a further 4%: not worth losing "this button is disabled".
- **`box` becomes `[x, y, width, height]`.** The keys cost more than the values.

### Off-screen subtrees are summarised, not expanded

This is the large one. A subtree hanging off a node that has no on-screen position is not
something the agent is looking at. It is reported as a count and left reachable:

```json
{"id": "0/0/0/0", "role": "menu", "name": "File",
 "actions": ["click", "select"], "box": [0, 32, 37, 28], "offscreen_children": 5}
```

`--of 0/0/0/0` expands it, exactly as a truncated subtree is re-entered today. Nothing is lost and
nothing is hidden — the count is right there.

**Measured: 73 nodes and 10,948 bytes become 24 nodes and 3,777 bytes.**

### Together

| | Nodes | Bytes |
| --- | --- | --- |
| Today | 73 | 19,752 |
| Compact node | 73 | 10,948 |
| ... plus off-screen summarised | **24** | **3,777** |

**5.2× smaller for the same window**, and `--full` brings back every field and expands every
subtree for the caller that wants the old shape.

## Deliberately not done

Four things were measured and rejected. Recording them so nobody spends the afternoon again:

**No `find` command.** It would be `tree --role X --name Y`, which already returns the matches
flat. A second way to do one thing doubles the ways to be wrong and halves the value of an
example — the same argument that kept `act` out of [CR-006](CR-006-element-addressing.md).

**No `--actionable` filter.** It sounds like the obvious lever and is not: **68 of the 73 nodes
already carry actions**, because pruning removed the ones that did not. It would save 5%.

**No flat node list.** Replacing nesting with a `parent` id on every node measured *worse* —
131 B/node against 115 — because the repeated parent id costs more than the nesting it removes.

**Not just omitting nulls and empty lists.** On its own that is 10%, which does not pay for
changing a documented shape. It comes along with the compact node anyway.

## Documentation to update

- `product/features/ui-tree.md` — `windows`; the compact node; `offscreen_children` and how to
  expand it; `--full`.
- `product/features/cli.md` — the `windows` command; `--full` on `tree`.
- `product/features/configuration.md` — nothing new, but say that the shape, not another budget,
  is what made the tree affordable.
- `product/features/skill.md` — the skill must teach `windows` **first**, before `tree`.
- `system/entities.md` — `WindowInfo`; `UINode.states` narrowed to notable states;
  `UINode.offscreen_children`; `Box` serialising as an array.
- `system/interfaces.md` — the `windows` command and its JSON; the new node JSON; the
  `AccessibilityProvider.windows()` addition.
- `system/architecture.md` — where the notable-state filter and the off-screen summary live
  (`selectors.py`, with the rest of the policy).

## Agent Notes

- **`windows` must survive an application that will not answer.** It is one depth-2 read of the
  desktop, which is exactly the traversal [BUG-001](../bugs/BUG-001-one-wedged-app-kills-the-desktop.md)
  was about. Losing one application is acceptable; losing the list is not.
- The off-screen summary counts the **whole** subtree, not the immediate children. A menu with five
  items each having a submenu should say what expanding it will actually cost.
- Summarising is a *reporting* decision, like pruning: it happens on the way out, and a selector
  still resolves against everything. `click --name "Preferences"` must keep working with the menu
  closed — that is the whole point of rung one, and it is the thing this change could most easily
  break.
- `--full` means full: every state, every field, every subtree expanded. It is the escape hatch,
  so it must not be a slightly-less-compact middle setting.
