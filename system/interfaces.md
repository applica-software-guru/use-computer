---
title: "Interfaces"
status: new
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
---

# Interfaces

## CLI

Console script: `use-computer`. A **default command** lets a bare action work alongside
subcommands, implemented by rewriting `argv` in the entry point.

### Action commands

```
use-computer move        --x INT --y INT
use-computer click       [--x INT --y INT] [--button left|right|middle]
use-computer double-click [--x INT --y INT]
use-computer right-click  [--x INT --y INT]
use-computer drag        --from-x INT --from-y INT --to-x INT --to-y INT
use-computer scroll      --amount INT [--direction up|down|left|right] [--x INT --y INT]
use-computer type        --text STR [--rate FLOAT]
use-computer key         COMBO
use-computer screenshot  [--out PATH] [--base64]
```

### Other commands

```
use-computer batch  (PATH | -)  [--continue-on-error]
use-computer config show
use-computer skill  install|update|remove|status
                    [--scope user|project|agents|claude] [--dir PATH] [--force]
```

### Global options

`--use PROFILE`, `--dry-run`, `--verify`, `--space screenshot|actuation`, `--delay SECONDS`,
`-v/-vv`, `--version`.

### Output contract

- **stdout**: exactly one JSON object per run, written with `json.dumps`.
- **stderr**: every diagnostic, log line and human-readable error.
- **exit codes**: `0` success, `1` failure, `2` bad usage.

### Run JSON

```json
{
  "profile": "staging",
  "backend": "vnc",
  "screen": {
    "width": 1280, "height": 800,
    "screenshot_width": 2560, "screenshot_height": 1600,
    "scale": 2.0
  },
  "ok": true,
  "failed_index": null,
  "results": [
    {
      "action": {"action": "click", "x": 120, "y": 340, "space": "screenshot"},
      "resolved": {"x": 60, "y": 170, "space": "actuation"},
      "performed": true,
      "duration_ms": 41.2,
      "change": {"changed": true, "magnitude": 0.18, "threshold": 0.002, "bbox": [40, 120, 600, 400]},
      "screenshot": null,
      "error": null
    }
  ]
}
```

### Batch input JSON

A JSON array of action objects, discriminated on `action`:

```json
[
  {"action": "click", "x": 120, "y": 340, "space": "screenshot", "verify": true},
  {"action": "type", "text": "hello", "delay": 0.2},
  {"action": "key", "combo": "enter"}
]
```

## Backend Protocol

```python
@runtime_checkable
class Backend(Protocol):
    name: str
    def screen_info(self) -> ScreenInfo: ...
    def screenshot(self) -> Screenshot: ...
    def move(self, x: int, y: int) -> None: ...
    def click(self, x: int | None, y: int | None, button: MouseButton, count: int) -> None: ...
    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, button: MouseButton) -> None: ...
    def scroll(self, amount: int, direction: ScrollDirection, x: int | None, y: int | None) -> None: ...
    def type_text(self, text: str, rate: float) -> None: ...
    def key(self, combo: KeyCombo) -> None: ...
    def close(self) -> None: ...
```

Coordinates crossing this boundary are always in **actuation** units — conversion happens above it.
Construction raises `BackendNotAvailableError` naming the extra to install.

## Python API

```python
from use_computer import Session, ClickAction, TypeAction

with Session.from_profile("staging") as s:
    result = s.run([
        ClickAction(x=120, y=340, space="screenshot", verify=True),
        TypeAction(text="hello"),
    ])
```

`Session.run` returns a frozen `RunResult` — the same object the CLI serialises.

## Config file

`.use-computer/config.toml` (committed):

```toml
default-profile = "laptop"
delay = 0.1
verify-threshold = 0.002
typing-rate = 0.02

[profiles.laptop]
backend = "local"
allow-local = true

[profiles.staging]
backend = "vnc"
host = "10.0.0.5"
port = 5900
scale = 1.0
```

`.use-computer/.env` (gitignored) carries secrets such as `USE_COMPUTER_PROFILES__STAGING__PASSWORD`.

## Environment variables

Prefix `USE_COMPUTER_`, mirroring the config keys — e.g. `USE_COMPUTER_DEFAULT_PROFILE`,
`USE_COMPUTER_DELAY`, `USE_COMPUTER_ALLOW_LOCAL`. `config show` prints the exact variable name for
every field.

## Agent Notes

The Run JSON shape is the contract the calling agent depends on. Adding fields is compatible;
renaming or removing one requires a change request.
