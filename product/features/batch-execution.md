---
title: "Batch Execution"
status: synced
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
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

## Result

One JSON object on stdout for the whole run: the profile used, the backend and its screen
geometry, and the ordered list of per-action results. A single action invoked directly is simply a
batch of one and returns the same shape.

## Agent Notes

- Per-action `delay` is honoured *inside* the batch — it is how the agent gives an application
  time to respond between steps.
- `--verify` on a batch applies change detection per action; the before-screenshot of action *n+1*
  may reuse the after-screenshot of action *n* when no delay intervenes.
