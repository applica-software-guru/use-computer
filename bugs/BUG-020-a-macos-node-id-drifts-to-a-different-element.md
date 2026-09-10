---
title: "a macOS node id drifts to a different element between calls"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-09T00:00:00.000Z"
---

# A macOS node id drifts to a different element between calls

## What happens

Reading Calculator's tree once, then acting on the ids it just printed, one call at a time:

```
$ use-computer tree --window Calculator --depth 6
    0/0/0/0/0/3  button "All Clear"
    0/0/0/0/0/6  button "7"
    0/0/0/0/0/16 button "3"
    0/0/0/0/0/17 button "Add"
    0/0/0/0/0/21 button "Equals"

$ use-computer click --id 0/0/0/0/0/3  --window Calculator
click button 'All Clear' at 0/0/0/0/0/3 — ok

$ use-computer click --id 0/0/0/0/0/6  --window Calculator
click button '8' at 0/0/0/0/0/6 — ok        # asked for "7"

$ use-computer click --id 0/0/0/0/0/17 --window Calculator
click button 'Change Sign' at 0/0/0/0/0/17 — ok   # asked for "Add"

$ use-computer click --id 0/0/0/0/0/16 --window Calculator
click button 'Add' at 0/0/0/0/0/16 — ok     # asked for "3"

$ use-computer click --id 0/0/0/0/0/21 --window Calculator
NodeNotFoundError: no node matches id=0/0/0/0/0/21
```

Every call after the first names a real button -- the CLI never refuses any of them -- just not the
one the preceding `tree` said lived at that id. The first click, at an id that had not yet caused
any state change, was the only one that landed correctly.

## Why

`AxProvider._build` (`accessibility/ax.py`) numbers a node by its position in `AXChildren`:

```python
children = tuple(
    self._build(child, f"{node_id}/{index}", depth - 1)
    for index, child in enumerate(raw)
)
```

That id is only as stable as `AXChildren`'s ordering, across two separate calls, on macOS, once the
UI has changed in between. It plainly is not: pressing `All Clear` changed what was on screen, and
by the very next call the digit and operator buttons no longer enumerated in the same order they
had a moment before. Nothing here checks for that -- an id is trusted purely as a path to walk, with
no identity of its own to confirm against, only the *name* and *role* the caller separately supplied
happen to be checked when they are given at all.

## Why it matters

Ids from `tree` are the addressing scheme every selector-based action shares --
`click`/`focus`/`toggle`/`expand`/`collapse`/`select`/`set_value`/`show_menu` all resolve one the
same way, through `matched.id`. An agent that reads a tree once and then acts on several of its ids
in sequence -- the ordinary shape of "read the state, then do several things" -- has every reason to
expect each id still means what the tree said it meant. On macOS, the moment any action in that
sequence changes the UI, every id after it is a gamble: sometimes a different, still-real element
(silently doing the wrong thing and reporting success), sometimes nothing at all.

## Expected

- An id resolved against a *stale* snapshot either still resolves to the element it originally
  named, or the action fails loudly rather than acting on whatever now happens to sit at that path.
- At minimum, `--id` should refuse to proceed silently when `--role`/`--name` are available to check
  against and disagree with what the id now points to, rather than trusting the id alone -- the
  option's own `--help` already claims this happens ("Checked against role and name") when in fact
  the check is skipped whenever the caller supplies only an id, which is the common case a
  freshly-read tree invites.
