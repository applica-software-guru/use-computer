---
title: "CLI"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "2.1"
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
use-computer tree --format json --use laptop
use-computer click --role button --name "Invia" --use laptop
use-computer set-value --id 0/2/1 --value "mario@example.com" --use laptop
use-computer batch actions.json --use staging
use-computer config init
use-computer config show
use-computer skill install --scope project
```

## Output contract

- **stdout is text.** One line per action, or the read that was asked for.
- **stderr carries all diagnostics** — logs, warnings, progress, errors.
- **Exit codes**: `0` success, `1` failure, `2` bad usage. Unchanged, and the primary signal.

`--format json` returns the envelope instead, for anyone piping into a parser.

### Every run ends with what the envelope carried

```
click button 'Invia' at 0/2/1/3 via the platform API — 12 ms
ok — profile laptop, backend local, screen 1920x1080, scale 1
```

**Thirteen tokens** for the facts the 177-token envelope carried: whether it worked, which profile
and backend answered, the screen, and the scale. Cheap must not mean lossy — the envelope was
dropped for its price, not because those facts were worthless. The scale in particular is what an
agent needs the moment a coordinate lands somewhere surprising, and `scale unknown` is printed as
words, because refusing to guess is only useful if the caller can see that it happened.

On a failure the line says which action it was:

```
failed at action 3 — profile laptop, backend local, screen 1920x1080, scale 1
```

**stdout says what happened; stderr says why.** Neither repeats the other, so a reader scrolling
back never has to work out which stream is which.

### Why text, and not JSON

Measured on this tool, in tokens:

| | JSON | Text |
| --- | --- | --- |
| `screenshot` | **243** | **4** |
| `click --role button --name "Invia"` | **4,238** | **21** |
| `windows` | 363 | 128 |
| The envelope alone, contents removed | **177** | — |

JSON's cost is not verbosity: `{`, `"`, `:`, `,` and every repeated key are each their own token,
so `"role": "button"` spends five to say one thing. And 177 of those are spent before any content —
on `profile` and `backend` (constant for a session), `screen` (five numbers nobody reads per
action), `ok` and `failed_index` (which the exit code already carries), and the action echoed back
to the caller who just sent it.

The decisive argument is one this project already made: [vision.md](../vision.md) says these tools
are "driven by another AI agent through a CLI", and a **Python API** exists underneath for
programs. The CLI's consumer is a model. It was optimised for a machine parser that has somewhere
better to be.

`--format` is **never inferred from `isatty()`**. Agents run commands under a pty often enough that
switching format on them would surface as a parse error far from its cause, on the caller least
able to diagnose it.

## Global flags

| Flag | Meaning |
| --- | --- |
| `--use <profile>` | Select a named profile from the config. |
| `--dry-run` | Resolve and log without performing. |
| `--verify` | Enable change detection for the run. |
| `--space <screenshot\|actuation>` | Coordinate space of the coordinates given. |
| `--delay <seconds>` | Delay applied after each action. |
| `-v/-vv` | Verbosity on stderr. |
| `--human` | Print for a reader instead of a parser. |

## Reading flags

`tree` and `windows` take `--format text|json`, defaulting to **text**: the rendering is a string
field inside the same single JSON object, and it costs 39% of the tokens the structured form does.
`--format json` returns objects, for a caller that parses rather than reads.

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
