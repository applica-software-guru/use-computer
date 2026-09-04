---
title: "Safety"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.2"
---

# Safety

`use-computer` types real keystrokes and moves a real pointer. On the local backend it does so on
the machine the user is sitting at. Safety here is not a policy layer; it is how the tool is built.

## Dry run

`--dry-run` resolves and logs every action — profile selection, coordinate scaling, key
normalisation — without performing any of it. Results are returned with `performed: false`, so an
agent can rehearse a whole batch and inspect exactly what would happen.

## Pacing

- **Per-action delays** so the application under control can react.
- **A typing rate applications do not drop characters from.** Typing a string as fast as the API
  allows loses characters in real applications; the rate is deliberate and configurable.

## Explicit opt-in for local

The `local` backend controls the user's own machine. It refuses to act unless it has been enabled
explicitly — a setting in the profile or an environment variable, never a silent default. A local
profile without the opt-in fails with an error explaining exactly what to set.

`config init` asks for that opt-in **out loud** rather than writing it into a file on the user's
behalf, and declining aborts the setup instead of producing a profile that cannot run. An opt-in
nobody was asked for is not an opt-in.

## Element actions are still real actions

Operating an element through the accessibility API moves no pointer, which makes it *quieter* than
a click, not safer:

- `--dry-run` still **resolves** the selector and reports the node it would have acted on and the
  rung it would have taken. A dry run that skips resolution tells the agent nothing it did not
  already know.
- **`focus` is a side effect.** It takes focus from whatever the user was doing, and on the local
  backend that is their real desktop. No action quietly focuses an element first to make itself
  work; if a toolkit requires focus, the error says so.
- On macOS the accessibility API will act on an application that is **not frontmost**. That is a
  genuine advantage and a genuine footgun: nothing visibly comes forward when it happens.

## Permission errors

Reading the tree needs the same Accessibility permission on macOS that input synthesis does, and on
Linux it needs the accessibility bus running: GTK applications expose nothing over AT-SPI when
`org.a11y.Bus` is absent. An empty tree that actually means "you have it switched off" is the worst
possible answer, so that case is an error naming what to enable, never an empty result.

macOS gates input synthesis behind Accessibility and screen capture behind Screen Recording. When
the permission is missing, the underlying libraries typically do nothing at all — a click that
never happens and never errors. `use-computer` detects the denial and raises a clear error naming
the permission and where to grant it, rather than reporting success for an action that did not
occur.

## Agent Notes

Every safety behaviour is observable in the JSON result: `performed`, the resolved coordinates, the
delay applied. Never make a safety decision that leaves no trace in the output.
