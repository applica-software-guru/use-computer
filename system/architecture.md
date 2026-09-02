---
title: "Architecture"
status: new
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
---

# Architecture

The stack mirrors the ui-locator project. All code lives under `code/` in a **src layout** at
`code/src/use_computer`.

## Layers

```
cli.py            typer app, argv rewriting, JSON on stdout, exit codes
runner.py         opens one backend, executes a batch, assembles RunResult
actions.py        Action models; scaling + key parsing applied here
coordinates.py    pure conversion between coordinate spaces
keys.py           canonical key syntax → per-backend tables
compare.py        before/after screenshot comparison (pillow)
config.py         project-root discovery, layered settings, config show
backends/
  base.py         the Protocol + BackendNotAvailableError
  local.py        pynput + mss          (extra: local)
  vnc.py          vncdotool             (extra: vnc)
skill/SKILL.md    package data, shipped in the wheel
```

Dependencies point downward only. `coordinates`, `keys` and `compare` are pure and are the easiest
things in the codebase to test.

## The backend Protocol

A **runtime-checkable `Protocol`** that every backend implements, covering `screenshot`, `move`,
`click`, `drag`, `scroll`, `type_text` and `key`, plus reporting `ScreenInfo`. A backend's
**construction** raises `BackendNotAvailableError` naming the extra to install — the import of its
third-party dependency happens inside the constructor, never at module import, so the package
installs and `--help` works with no extras present.

The fake backend used in tests records the actions it was asked to perform and satisfies the same
Protocol.

## Configuration resolution

The project root is found by walking up from the current directory the way git finds its own,
looking for a `.use-computer` directory holding a committed `config.toml` and a gitignored
`.env`, with XDG config/data fallbacks — never a cache directory.

Layers resolve highest to lowest: CLI flags → environment (`USE_COMPUTER_` prefix) → `.env` →
selected profile → top-level config keys → global config → field defaults. Each resolved value
**carries the layer it came from**, so `config show` reports the truth rather than a reconstruction.
Unknown keys — including keys inside unselected profiles — produce warnings on stderr.

## Execution flow

1. CLI parses flags and the action(s), resolves the profile.
2. Runner constructs the backend **once** and queries its `ScreenInfo`.
3. For each action: convert coordinates into actuation units (refuse if the scale is unknown),
   normalise keys, optionally capture the before-screenshot, perform (unless dry-run), apply the
   delay, optionally capture the after-screenshot and compare.
4. Backend is closed, including on failure. A `RunResult` is serialised to stdout.

Stopping at the first failure is the default; `--continue-on-error` overrides it.

## CLI construction

The default command is implemented by **rewriting `argv` in the console-script entry point**, so a
bare action works alongside subcommands. Never by subclassing `TyperGroup` — typer 0.27 stopped
being click-based and that approach breaks silently.

JSON is emitted with plain `json.dumps`; rich is used only for human-facing output on stderr,
because rich soft-wraps long strings and can emit a newline inside a JSON string.

## Packaging

hatchling, with `skill/SKILL.md` declared as package data. Backends are optional extras. CI gates
the release on the git tag matching the version in `pyproject.toml` and on `SKILL.md` being
present in the built wheel.

## Agent Notes

- Never import a transitive dependency without declaring it. In ui-locator an undeclared `click`
  import survived unnoticed until typer dropped click.
- Declare a dependency floor that is actually tested, and verify it in CI.
