---
title: "activate reports success on macOS without bringing the app forward"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-09T00:00:00.000Z"
---

# `activate` reports success on macOS without bringing the app forward

## What happens

With Terminal in front and Calculator open behind it:

```
$ use-computer activate --window "Calculator"
activated window 'Calculator' 0/65/0 — 1378 ms
ok — profile local, backend local, screen 1920x1080, scale 1

$ use-computer windows --format json | jq '.results[0].windows.windows[] | select(.active)'
{"app": "Terminal", "title": "...", ...}
```

Half a second later, `windows` still names Terminal as the one in front. A screenshot taken at the
same moment shows why: Calculator's window is genuinely still *behind* Terminal on screen -- the
two overlap, and Terminal's content, not Calculator's, is what is visible and what a coordinate
click in that region will hit. `activate` did not lie about its own return value; the platform call
it made really did succeed, and still nothing visible happened.

## Why

`AxProvider.activate` (`accessibility/ax.py`) performs exactly one action:

```python
def activate(self, window_id: str) -> bool:
    element = self._index.get(window_id)
    ...
    status = self._api.AXUIElementPerformAction(element, "AXRaise")
    return bool(status == 0)
```

`AXRaise` orders a window to the front *within its own application*. It does not make that
application the frontmost one on the desktop -- that is a separate notion on macOS
(`NSRunningApplication.activateWithOptions:` / `NSApplicationActivateIgnoringOtherApps`), and
nothing here calls it. So a background application's single window can legitimately answer
"I raised myself" with status `0` while a different, still-frontmost application keeps covering it.

`Session._activate` (`runner.py`) trusts that boolean completely:

```python
if not provider.activate(root.id):
    ... fall back to focusing a child ...
raise ActionFailedError(...) if that also fails
```

`AXRaise` succeeding short-circuits the fallback, so the one case that would actually have worked
-- giving a descendant keyboard focus, which on macOS also tends to bring the owning app forward --
is never reached.

## Why it matters

`_bring_forward` (`runner.py`) exists specifically so a coordinate click cannot land in the wrong
application, and it is a no-op whenever the target is not already `active` -- which is precisely
when it matters most, since that is when another application is genuinely in front. On macOS this
means the safety mechanism the whole coordinate-click contract leans on the AX layer's raise, and
the AX layer's raise does not do the one thing that mechanism needs from it. Combined with
[[BUG-017-a-click-lands-where-the-pointer-used-to-be]], this is why a scripted sequence of clicks
aimed at a background window on macOS can run clean and touch nothing in it at all: the window
named by `--window` was never actually brought forward, so every coordinate in the sequence lands
in whatever was already on top.

## Expected

- `activate --window X` (and the same bring-forward step inside `click`, `scroll`, `drag`, etc. on
  a background window) leaves `X`'s owning application frontmost and its window on top on screen,
  confirmed by `windows` immediately after.
- On macOS this means raising the window *and* making its owning process the active application --
  `AXRaise` alone is not sufficient and should not be treated as if it were.
