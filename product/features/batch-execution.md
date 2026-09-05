---
title: "Batch Execution"
status: synced
author: ""
last-modified: "2026-09-05T12:40:00.000Z"
version: "2.0"
---

# Batch Execution

Opening a VNC connection dominates the cost of a single action. Paying that cost once per click
turns a five-step plan into five connection handshakes. One run therefore accepts a **batch** of
actions and performs them over one connection.

## Shape

A batch is an ordered list of actions, supplied as JSON — inline, from a file, or on stdin:

```bash
use-computer batch --use staging actions.json
echo '[{"action":"click","x":120,"y":340},{"action":"type","text":"hello"}]' \
  | use-computer batch --use staging -
```

The backend is opened once, every action runs in order against it, and it is closed at the end —
including when an action fails.

## Failure

By default a batch **stops at the first failure**: subsequent actions may depend on the state the
failed one was meant to produce. The run reports every action attempted, its result, and which
index failed, so the agent can resume from a known point. `--continue-on-error` runs the remainder
anyway, for independent actions.

Exit code is 0 only if every attempted action succeeded.

## An action is spelled the way the CLI spells it

The CLI command is `set-value`; the batch takes `set_value`. Same action, two spellings, and
nothing said so:

```
$ echo '[{"action":"set-value", …}]' | use-computer -
error: - is not a valid action list: 1 validation error for
list[tagged-union[MoveAction,function-after[_one_target(), ClickAction],…
```

Four hundred characters of internal union, naming every action type except the one the caller
should have written.

Both spellings are accepted — `set-value` and `set_value`, `double-click` and `double_click`,
`right-click` and `right_click` — because an agent that has just read `use-computer set-value
--help` has no reason to expect a different name three lines later. And an unrecognised action is
one sentence that names the input and the nearest match:

```
error: unknown action 'set-valeu' at index 1. Did you mean 'set-value'?
```

A parser error is a message to a caller who is mid-task and cannot see the code. It says what was
wrong, where, and what to write instead.

## Result

One JSON object on stdout for the whole run: the profile used, the backend and its screen
geometry, and the ordered list of per-action results. A single action invoked directly is simply a
batch of one and returns the same shape.

## Agent Notes

- Per-action `delay` is honoured *inside* the batch — it is how the agent gives an application
  time to respond between steps.
- `--verify` on a batch applies change detection per action; the before-screenshot of action *n+1*
  may reuse the after-screenshot of action *n* when no delay intervenes.

## What a batch prints

One line per action, numbered, so a failure is locatable without counting:

```
1 focus text 'Destinatario' via the platform API — 8 ms
2 type "mario@example.com" — 240 ms
3 click button 'Invia' via the platform API — 12 ms
4 tree — 24 nodes, 1 truncated
ok — profile laptop, backend local, screen 1920x1080, scale 1
```

The closing line says whether it finished and, when it did not, which action stopped it. The exit
code carries the same answer for a caller that would rather branch than read.
