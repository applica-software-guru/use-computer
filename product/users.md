---
title: "Users"
status: synced
author: ""
last-modified: "2026-09-03T00:00:00.000Z"
version: "1.1"
---

# Users

`use-computer` has one primary consumer that is not human, and two human ones.

### The calling AI agent (primary)

A computer-use agent that has already decided what to do and, usually via ui-locator, where to do
it. It invokes the CLI, reads JSON from stdout, and never reads stderr except when debugging.

What it needs:

- **Machine-readable output.** Plain JSON on stdout, one object per run, nothing interleaved.
- **A feedback signal.** Did the screen change after the click? Without it the agent cannot tell a
  stale coordinate from a slow application.
- **Unambiguous coordinates.** It may hold coordinates in screenshot pixels while the backend
  actuates in another space; the tool must convert, or refuse.
- **Batching.** A whole plan — click, type, press Enter — in one invocation, one connection.
- **Stable, non-negotiable exit codes.** 0 success, 1 failure, 2 bad usage.
- **A bundled skill** describing how to drive the tool, installable into the agent's own skills
  directory so the instructions ship with the version installed.

### The developer integrating it

A Python developer wiring `use-computer` into an agent harness, a test rig, or a remote desktop
session.

What they need:

- A Python API underneath the CLI, with typed, frozen result models.
- Installation without unwanted OS-level dependencies: backends are optional extras, imported
  lazily, so `pip install use-computer-cli` works anywhere.
- A named-profile config so switching from a local display to a VNC host is a flag, not a rewrite.
- `config show` to see every resolved value and the layer it came from when something is wrong.
- Dry-run to rehearse a batch before it touches a real screen.

### The maintainer / CI

Whoever releases the package and keeps it working across the supported dependency range.

What they need:

- A CI matrix over both ends of the supported typer range, because typer's breaking changes are the
  reason this project pins the way it does.
- A release gated on the git tag matching the version in `pyproject.toml` and on the bundled
  `SKILL.md` being present in the built wheel.
- Tests that pass identically on a laptop and inside GitHub Actions — no ambient environment,
  no colour-dependent assertions.

## Agent Notes

The agent is the user whose experience is designed for first. When a trade-off arises between
human ergonomics and machine legibility of the output, machine legibility wins.
