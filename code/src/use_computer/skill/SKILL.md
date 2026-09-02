---
name: use-computer
description: Execute input on a screen — move, click, double-click, right-click, drag, scroll, type text, press key combinations, capture a screenshot. Use whenever you need to act on a GUI, locally or over VNC. Pair it with ui-locator, which tells you where to click.
x-skill-id: use-computer
x-skill-version: "1"
---

# use-computer

You act on a screen through the `use-computer` CLI. It moves a real pointer and types real
keystrokes. It does not decide *what* to click — you do, usually with coordinates from
`ui-locator`.

## Contract

- **stdout** is one JSON object per run. Parse it.
- **stderr** is diagnostics. Read it only when debugging.
- **exit codes**: `0` success, `1` failure, `2` bad usage.

Always pass `--use <profile>` unless a default profile is configured.

## Coordinates: the thing that goes wrong

A screenshot on a HiDPI display is larger than the space the OS clicks in. Coordinates from
`ui-locator` are in **screenshot** pixels — the space it looked at. That is the default here,
so pass them through unchanged. Pass `--space actuation` only if you already converted them
yourself, which you should not do.

If a run fails saying the scale is unknown, take a screenshot first (`use-computer screenshot`)
and read `screen` from the result; do not compute a factor and retry with different numbers.

## Acting

```bash
use-computer click --x 120 --y 340 --use staging
use-computer double-click --x 120 --y 340 --use staging
use-computer right-click --x 120 --y 340 --use staging
use-computer move --x 120 --y 340 --use staging
use-computer drag --from-x 10 --from-y 20 --to-x 300 --to-y 400 --use staging
use-computer scroll --amount 3 --direction down --use staging
use-computer type --text "hello world" --use staging
use-computer key ctrl+s --use staging
use-computer screenshot --out shot.png --use staging
```

`type` sends literal text. `ctrl+a` given to `type` types seven characters — use `key` for
shortcuts.

## Key syntax

Modifiers `ctrl`, `alt`, `shift`, `cmd` (aliases: `control`, `option`, `super`, `win`, `meta`)
joined to a key with `+`: `ctrl+shift+t`, `cmd+space`, `alt+f4`, `enter`. Named keys: `enter`,
`tab`, `esc`, `space`, `backspace`, `delete`, `insert`, `home`, `end`, `pageup`, `pagedown`,
`up`, `down`, `left`, `right`, `f1`–`f24`. One spelling works on every backend.

## Batch — prefer this

Opening a VNC connection costs more than the action does. Send the whole plan in one run; it
executes over one connection.

```bash
echo '[
  {"action":"click","x":120,"y":340,"verify":true},
  {"action":"type","text":"hello","delay":0.2},
  {"action":"key","combo":"enter"}
]' | use-computer - --use staging
```

`batch` is the default command, so `use-computer -` and `use-computer actions.json` work. A
batch stops at the first failure and reports `failed_index`, so you can resume from a known
point. `--continue-on-error` runs the rest anyway.

## Verify — how you know it worked

A click that lands on nothing looks exactly like a click that worked. With `--verify` (or
`"verify": true` on one action) each action reports:

```json
"change": {"changed": true, "magnitude": 0.18, "threshold": 0.002, "bbox": [40,120,600,400]}
```

- `changed: false` after a click → the coordinate was probably stale. **Ask ui-locator again.
  Do not click the same pixel twice.**
- `changed: true` with a tiny `magnitude` in a corner → a clock or a caret, not a response.

Verification costs two screenshots per action, so use it on the actions whose effect you need
to confirm, not on every one.

## Before you act on something risky

`--dry-run` resolves and logs everything — profile, scaled coordinates, normalised keys —
without performing any of it. Results come back with `"performed": false`. Rehearse a batch you
are unsure about.

## When it refuses

- **`BackendNotAvailableError`** — the extra is not installed. The message names it.
- **Local backend not enabled** — the `local` backend controls the user's own machine and needs
  an explicit opt-in. Tell the user to set `allow-local = true` in the profile; do not work
  around it.
- **Permission denied** — macOS Accessibility or Screen Recording. The message names which. Only
  the user can grant it.
- **Coordinate space error** — see above. Take a screenshot; do not guess a factor.

## Configuration

`use-computer config show` prints every resolved value, the layer it came from, and the exact
environment variable that would override it. Run it first when a profile behaves unexpectedly.
