---
title: "a click lands where the pointer used to be, on macOS"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-09T00:00:00.000Z"
---

# A click lands where the pointer used to be, on macOS

## What happens

`use-computer click --x 1135 --y 770` reports success, and the pointer eventually appears at
`(1135, 770)` -- but the press-and-release that constitutes the click fires wherever the pointer
already was, not where it was just told to go. A five-click sequence on macOS Calculator (`AC`,
`7`, `+`, `3`, `=`) reports five clean successes, and the display never changes: each click's
button-down actually lands on the *previous* click's target, one step behind, and the first one
lands wherever the pointer happened to be before the run started.

Isolated from any application, against the live pointer location the window server itself reports:

```python
from Quartz import CGEventCreate, CGEventGetLocation
from pynput.mouse import Controller

m = Controller()
m.position = (500, 500)
print(CGEventGetLocation(CGEventCreate(None)))   # -> still the OLD point
time.sleep(0.05)
print(CGEventGetLocation(CGEventCreate(None)))   # -> (500.0, 500.0), now correct
```

Setting `pynput`'s `mouse.position` on macOS posts the move asynchronously; the window server takes
on the order of 5-50 ms to actually adopt it. A read immediately after the write -- which is
exactly what a click's button-down does, since pynput stamps the event with the *current* location
-- gets the stale one.

## Why

`LocalBackend.click` (`backends/local.py`) does the move and the press back to back, with nothing
between them:

```python
def click(self, x, y, button, count):
    if x is not None and y is not None:
        self.move(x, y)
    pynput_button = self._button(button)
    for index in range(count):
        if index:
            time.sleep(DOUBLE_CLICK_GAP)
        self._mouse.press(pynput_button)
        time.sleep(PRESS_HOLD)
        self._mouse.release(pynput_button)
```

`PRESS_HOLD` (20 ms) is spent *after* `press()`, holding the button down -- it buys nothing for the
move that already happened. There is no wait between `self.move(x, y)` and `self._mouse.press(...)`,
which is exactly the gap the race lives in. `drag` has the same shape: it moves to `from_x, from_y`
and presses immediately, so a drag can pick up whatever was under the *previous* action's
coordinate rather than its own start point.

This is a documented quirk of driving macOS through Quartz events, not a `pynput` defect: the
warp is asynchronous by design, and anything that reads the pointer location right after setting it
can observe the old value.

## Why it matters

Every coordinate-driven action that also has to move first -- `click`, `double-click`,
`right-click`, the press end of `drag` -- is affected. Each one reports the coordinate it *meant*
to act on and a duration in the hundred-millisecond range (plenty of time for the *next* action's
move to have long since settled), which is exactly why the effect always looks shifted by one
action rather than simply missing: an agent chaining several such actions gets a report that is
consistently, silently wrong about where each one actually landed, and `--verify` compares the
screen against the *intended* action, not the one that happened.

## Expected

- On macOS, a click's button-down uses the position the click's own move just set, not whatever the
  window server has not caught up to yet -- e.g. a short wait after `move()` before `press()`
  (a two-digit number of milliseconds resolved the race in the reproduction above; something with
  margin over that, on this backend only, is the fix -- not a global slowdown of every action on
  every platform).
- `drag`'s initial press needs the same treatment at `from_x, from_y` before it moves toward the
  target.
- A click, double-click, right-click or drag reported as done at `(x, y)` actually acted at `(x, y)`.
