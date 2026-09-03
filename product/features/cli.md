---
title: "CLI"
status: synced
author: ""
last-modified: "2026-09-03T00:00:00.000Z"
version: "1.1"
---

# CLI

The CLI is the interface the calling agent actually uses. Its contract is machine-first.

## Shape

A **default command** means a bare action works alongside subcommands:

```bash
use-computer click --x 120 --y 340 --use staging
use-computer type --text "hello" --use staging
use-computer key ctrl+s --use staging
use-computer screenshot --use laptop
use-computer batch actions.json --use staging
use-computer config init
use-computer config show
use-computer skill install --scope project
```

## Output contract

- **stdout is JSON and nothing else.** One object per run.
- **stderr carries all diagnostics** — logs, warnings, progress, human-readable errors.
- **Exit codes**: `0` success, `1` failure, `2` bad usage.

An agent can therefore pipe stdout into a JSON parser unconditionally.

## Global flags

| Flag | Meaning |
| --- | --- |
| `--use <profile>` | Select a named profile from the config. |
| `--dry-run` | Resolve and log without performing. |
| `--verify` | Enable change detection for the run. |
| `--space <screenshot\|actuation>` | Coordinate space of the coordinates given. |
| `--delay <seconds>` | Delay applied after each action. |
| `-v/-vv` | Verbosity on stderr. |

## Agent Notes

Two hard-won implementation constraints:

- The default command is implemented by **rewriting `argv` in the console-script entry point**, so
  a bare action works alongside subcommands. It is **never** implemented by subclassing
  `TyperGroup`: typer 0.27 stopped being click-based and that approach breaks silently.
- JSON is printed with plain `json.dumps`, **not** through rich. rich soft-wraps long strings and
  can emit a newline inside a JSON string, corrupting the output an agent parses.
