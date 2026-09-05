---
title: "A window you can bring forward, and coordinates that stay inside it"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# A window you can bring forward, and coordinates that stay inside it

## Why

Every coordinate this tool sends lands on **whatever window happens to be in front**, and nothing
in the tool knows or says which window that is.

In one session this produced three separate wrong answers, none of which announced itself:

- `screenshot --window 0/37/0 --of 0/0/2` returned a picture of a **terminal**, because Drawing
  was behind it. Right size, right node id, `ok`. (BUG-012)
- Two `drag` calls aimed at a canvas **selected text in the terminal** instead.
- `--verify` then reported the selection highlight as the change, so the wrong action was
  confirmed by the wrong evidence, consistently.

The tool already refuses to guess about far smaller things. `--window` refuses an ambiguous title.
A coordinate refuses to be converted when the scale is unknown. But which window a click enters —
the largest assumption in the whole tool — is not checked at all.

And there is no clean way to fix it, because **nothing in this tool means "bring that window
forward"**. The mechanism exists; the command does not. `focus` refuses on the window node itself —

```
$ use-computer focus --window 0/37/0 --id 0 --role window
ActionNotSupportedError: window 'albero.png ~ Line' at 0 does not support 'focus'.
It supports: none
```

— while `focus` on any *descendant* raises the window as a side effect, measured:
`_NET_ACTIVE_WINDOW` moved from the terminal to Drawing after focusing its "Open" button.

That side effect is not a substitute for the command, for three reasons. It is documented nowhere,
so an agent has no way to know it. It requires picking an arbitrary descendant. And it is not
free: it moves keyboard focus onto that widget, which decides where a later `type` lands and can
scroll a list or raise a tooltip on the way. Working around it during the session meant clicking a
random widget by coordinate — the same unguarded act — and finally leaving the tool for `wmctrl`.

## What changes

### `use-computer activate --window <id | title | @pid>`

Brings a window forward and gives it keyboard focus.

```bash
use-computer activate --window 0/37/0
→ activated window 'albero.png ~ Line' 0/37/0
```

No new dependency on any platform. A window node itself exposes no actions — verified: AT-SPI
answers `It supports: none` — but **focusing a descendant activates the window**, which is already
implemented as `perform(FOCUS)`:

- **Linux/AT-SPI** — `grab_focus()` on the first focusable descendant. Measured: `_NET_ACTIVE_WINDOW`
  moved from the terminal to Drawing.
- **Windows/UIA** — `SetFocus()` on the element, which raises its top-level window.
- **macOS/AX** — `AXRaise` on the window itself, which AX windows do support, falling back to
  focusing a descendant.

If no descendant can take focus, it fails saying so, rather than reporting a success that did not
happen.

### `--window` on the coordinate actions, and it means something

`click --x/--y`, `double-click`, `right-click`, `move`, `drag` and `scroll` take `--window`. When
it is given, **that window is brought forward before the coordinate is sent**.

This is the whole point: naming the window is how an agent says what it meant, and until now the
coordinate commands had no way to hear it. Without `--window` behaviour is unchanged — the action
goes to whatever is in front, which is what a bare coordinate has always meant.

### `screenshot --of` stops cropping the wrong application

Cropping to a node in a window that is not in front is not a picture of that node. `screenshot`
brings the node's window forward before capturing, and if it cannot, it **refuses and says the
window is not visible** instead of returning a plausible picture of something else.

### An element action that falls to rung two

`--via coordinate`, and `--via auto` when it drops to a coordinate, activate the resolved node's
window first. Rung one is unaffected: it sends no coordinates, so there is nothing to aim.

## The cost, stated

Activating a window is a visible change to the user's desktop. That is a real cost and it is the
right trade: the alternative is not "nothing happens", it is a click landing in someone else's
application. A tool whose job is to move a real pointer cannot be shy about which window the
pointer is over.

`--dry-run` reports the activation it would perform without performing it, like everything else.

## Agent Notes

- Activation is idempotent and cheap when the window is already in front; check first and skip.
- Give the window a moment to come forward before sending the coordinate. A settle that is skipped
  here reintroduces exactly the bug this change request exists to remove.
- `windows` already reports which window is active; that answer must agree with what `activate`
  does, which is also what BUG-010 is about.
