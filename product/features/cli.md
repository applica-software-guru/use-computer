---
title: "CLI"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.3"
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
use-computer windows --use laptop
use-computer tree --use laptop
use-computer click --role button --name "Invia" --use laptop
use-computer set-value --id 0/2/1 --value "mario@example.com" --use laptop
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

## Selector flags

Actions that can address an element share one set of flags — see
[element-addressing.md](element-addressing.md):

| Flag | Meaning |
| --- | --- |
| `--id <path>` | A node id from `tree`. Fingerprint-checked against role and name. |
| `--role <role>` | Match by role. |
| `--name <text>` | Match by name (substring, case-insensitive; `--exact` for equality). |
| `--nth <n>` | Disambiguate between candidates the other flags could not separate. |
| `--window <focused\|all\|TITLE\|@PID>` | Restrict the search. |
| `--via <auto\|action\|coordinate>` | Which rung to take. Default `auto`. |

Giving both a coordinate and a selector to the same action is a usage error: the target is one
thing or the other.

## Agent Notes

Two hard-won implementation constraints:

- The default command is implemented by **rewriting `argv` in the console-script entry point**, so
  a bare action works alongside subcommands. It is **never** implemented by subclassing
  `TyperGroup`: typer 0.27 stopped being click-based and that approach breaks silently.
- JSON is printed with plain `json.dumps`, **not** through rich. rich soft-wraps long strings and
  can emit a newline inside a JSON string, corrupting the output an agent parses.
