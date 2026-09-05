---
title: "Architecture"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.4"
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
tree.py           pure: UINode, Box, TreeScope, TreeResult, NodeSelector, Via
selectors.py      pure: match a NodeSelector against a tree, prune, budget, clamp text,
                  keep notable states, count what is off screen instead of expanding it
render.py         pure: one line per node with a legend, plus the --human views
backends/
  base.py         the Protocol + BackendNotAvailableError
  local.py        pynput + mss          (extra: local)
  vnc.py          vncdotool             (extra: vnc)
accessibility/
  base.py         AccessibilityProvider Protocol + UITreeUnavailableError
  roles.py        per-platform role, state and action names → canonical ones
  atspi.py        Linux   — AT-SPI 2    (extra: tree)
  uia.py          Windows — UI Automation
  ax.py           macOS   — AXUIElement
skill/SKILL.md    package data, shipped in the wheel
```

`render.py` takes an already-shaped tree and formats it. It decides nothing: pruning, the budget,
notable states and the off-screen summary have all happened by the time it runs, which is why it
stays a page long and tests against a literal string.

Dependencies point downward only. `coordinates`, `keys`, `compare`, `tree`, `selectors`,
`render` and `accessibility/roles.py` are pure and are the easiest things in the codebase to test — `tree`
holds the models, `selectors` the policy over them, and neither imports a platform binding.

## The accessibility provider

A second runtime-checkable `Protocol`, separate from `Backend` because the split is different: the
`local` backend has three platform implementations of it and the `vnc` backend can have none at
all. It is selected by the **running platform**, never by configuration.

`roles.py` normalises each platform's vocabulary the way `keys.py` normalises key names — AT-SPI's
`push button`, UIA's `Button` and AX's `AXButton` all become `button`, and the canonical action
names map back onto `Action.do_action`, control patterns and `AXPress` respectively.

Pruning, the node budget, the notable-state filter, the off-screen summary and selector matching
all live in `selectors.py` and operate on an already built tree, so they are pure functions over
`UINode` and test without a desktop. Everything that shapes what the caller sees belongs here and
not in a provider: three platforms would otherwise abbreviate three different ways, and each
decision would need a desktop to test. That matters: no
CI runner has a session bus, a logged-in desktop or an Accessibility grant, so the platform
providers are unreachable there by construction and everything worth testing has to sit above
them.

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
2. Runner constructs the backend **once** and queries its `ScreenInfo`. The accessibility provider
   is constructed **lazily**, on the first action that needs it, so a run of pure coordinate
   actions never touches it.
3. For each action: if it carries a selector, snapshot the tree and resolve it **now** — one match
   or an error — then convert coordinates into actuation units (refuse if the scale is unknown),
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
- The platform binding is imported **inside the provider's constructor**, never at module import —
  the same rule as the backends, with the same consequence if broken: `use-computer --help` stops
  working on a machine without the extra.
- Selector resolution happens once per action, against a freshly read tree. Never cache a tree
  between actions to save a read: the layout moved, and that is the whole reason ids are
  fingerprint-checked.
- Declare a dependency floor that is actually tested, and verify it in CI.
