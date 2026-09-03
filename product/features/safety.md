---
title: "Safety"
status: synced
author: ""
last-modified: "2026-09-03T00:00:00.000Z"
version: "1.1"
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

## Permission errors

macOS gates input synthesis behind Accessibility and screen capture behind Screen Recording. When
the permission is missing, the underlying libraries typically do nothing at all — a click that
never happens and never errors. `use-computer` detects the denial and raises a clear error naming
the permission and where to grant it, rather than reporting success for an action that did not
occur.

## Agent Notes

Every safety behaviour is observable in the JSON result: `performed`, the resolved coordinates, the
delay applied. Never make a safety decision that leaves no trace in the output.
