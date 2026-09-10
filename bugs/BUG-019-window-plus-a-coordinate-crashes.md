---
title: "--window plus a coordinate crashes click, double-click, right-click and scroll"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-09T00:00:00.000Z"
---

# `--window` plus a coordinate crashes `click`, `double-click`, `right-click` and `scroll`

## What happens

```
$ use-computer click --x 1189 --y 716 --window "Calculator"
ValidationError: 1 validation error for ClickAction
  Value error, a selector needs at least one of: id, role, name
```

Every command that accepts either a coordinate or a selector fails the same way the moment
`--window` is given alongside `--x`/`--y` with no `--id`/`--role`/`--name`: `double-click`,
`right-click` and `scroll` all reproduce it identically. This is not macOS-specific -- it is a pure
validation bug -- but it is what a caller reaches for the moment `--window` is used the way
`actions.py` itself documents: naming which window a bare coordinate belongs to.

## Why

`_Selectable._collect_selector` (`actions.py`) gathers the flat selector keys of a batch file into
one `NodeSelector` before the rest of validation runs:

```python
_SELECTOR_KEYS = ("id", "role", "name", "exact", "nth", "window")

@model_validator(mode="before")
def _collect_selector(cls, data):
    if not isinstance(data, dict) or data.get("selector") is not None:
        return data
    present = {key: data[key] for key in _SELECTOR_KEYS if data.get(key) is not None}
    if not present:
        return data
    ...
    rest["selector"] = NodeSelector(node_id=node_id, window=..., **present)
    return rest
```

`window` is in `_SELECTOR_KEYS`. But `window` is not only a selector field -- `_InAWindow` (the
base every positional action inherits) carries its own `window`, meaning "the window this
*coordinate* belongs to," independent of whether a selector is present at all. When a caller passes
`--window` with a coordinate and nothing else, `present` comes out non-empty on `window` alone, and
this code concludes an element selector was intended and builds one with no `id`/`role`/`name` --
which then fails its own required-field check downstream, on a value the caller never meant as a
selector in the first place.

## Why it matters

`_InAWindow`'s own docstring is explicit about what `--window` on a coordinate is for: "the window
is brought forward before the coordinate is sent" -- exactly the safety net the project built (see
[[BUG-018-activate-reports-success-without-coming-forward]]) so a coordinate cannot silently land in
the wrong application. That is the one path a caller reaches for when clicking a background window
by coordinate, and it is the path that cannot be reached at all: it crashes before the click ever
runs, on every one of `click`, `double-click`, `right-click`, and `scroll`.

## Expected

- `click --x X --y Y --window SCOPE` (and the same for `double-click`, `right-click`, `scroll`)
  succeeds: it brings `SCOPE` forward and then clicks the coordinate within it, exactly as
  `_InAWindow`'s docstring describes.
- `--window` alone, with no `--id`/`--role`/`--name`, is never treated as "the caller wants an
  element selector" -- only `id`, `role`, `name`, `exact` and `nth` say that; `window` qualifies
  whichever target (coordinate or selector) is actually present.
