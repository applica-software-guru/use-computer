---
title: "The focused fallback walks the whole desktop once per window"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# The focused fallback walks the whole desktop once per window

## What happens

Measured on a desktop with 14 windows, a single `use-computer windows`:

| Path | D-Bus calls | Worst case at the 800 ms per-call bound |
| --- | --- | --- |
| normal | 145 | 1.9 minutes |
| **fallback** | **879** | **11.7 minutes** |

On a healthy desktop both are fast — 0.4 s — so nothing shows.

## Why

```python
return [
    info.model_copy(update={"active": info.id in self._focused_ids()})
    for info in found
]
```

`self._focused_ids()` is a method call **inside the comprehension**, so it is evaluated once per
window, and each evaluation walks every application on the desktop. Fourteen windows, fourteen
full enumerations.

The second walk should not exist at all, never mind fourteen of them: `_window_pairs` has already
read each window's state set in the first pass, and `focused` is in it.

## Why it matters, and when

The fallback fires precisely when **no window reports `active`** — which is the state a desktop is
in while an application is starting up. That is the exact situation in which this gets called:

```bash
nohup soffice --calc --norestore & sleep 12; use-computer windows
```

So the branch that costs six times as much is the branch taken when an application is least likely
to answer promptly, and every unanswered call costs the full 800 ms.

This was introduced in the same change that fixed [BUG-010](BUG-010-every-window-is-active.md), a
day old, and never measured. The fix there was about correctness and the cost of the fallback was
never looked at — a rule this project has stated about tokens and never applied to round trips.

## Expected

One walk. `focused` comes out of the pass that already read the states, and there is no second
enumeration to call — so the mistake cannot recur by being re-introduced somewhere else in the
expression.
