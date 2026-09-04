---
title: "Interfaces"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.3"
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
use-computer screenshot  [--out PATH]
```

### Element commands

```
use-computer tree        [--window SCOPE] [--depth INT] [--role ROLE] [--name TEXT]
                         [--all] [--of NODE_ID] [--out PATH] [--no-fallback]
use-computer focus       SELECTOR
use-computer toggle      SELECTOR
use-computer expand      SELECTOR
use-computer collapse    SELECTOR
use-computer select      SELECTOR
use-computer set-value   SELECTOR --value STR
use-computer show-menu   SELECTOR
```

`click`, `double-click`, `right-click` and `scroll` accept `SELECTOR` **instead of** their
coordinates. Passing both is exit code `2`.

### SELECTOR

```
[--id NODE_ID] [--role ROLE] [--name TEXT] [--exact] [--nth INT]
[--window focused|all|TITLE|@PID] [--via auto|action|coordinate]
```

At least one of `--id`, `--role`, `--name` is required. `--window` defaults to `focused`, `--via`
to `auto`. `--name` matches a case-insensitive substring unless `--exact`.

### Other commands

```
use-computer batch  (PATH | -)  [--continue-on-error]
use-computer config init [--backend local|vnc] [--profile NAME]
                         [--host HOST] [--port PORT] [--allow-local]
                         [--dir PATH] [--no-probe] [--force]
use-computer config show
use-computer skill  install|update|remove|status
                    [--scope user|project|agents|claude] [--dir PATH] [--force]
```

### Global options

`--use PROFILE`, `--dry-run`, `--verify`, `--space screenshot|actuation`, `--delay SECONDS`,
`-v/-vv`, `--version`.

`--verify` writes the after-screenshot to a file and reports its path in `screenshot`, so an agent
that verified an action does not then have to ask for the screen it already paid to capture.
A screenshot is **never** returned as bytes; there is no base64 anywhere in this contract.

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
      "screenshot": {
        "path": "/home/you/.local/share/use-computer/screenshots/20260904T103012.481Z-click.png",
        "width": 2560, "height": 1600, "space": "screenshot",
        "captured_at": "2026-09-04T10:30:12.481Z"
      },
      "tree": null,
      "matched": null,
      "via": null,
      "error": null
    }
  ]
}
```

### `tree` JSON

The `tree` field of the result:

```json
{
  "root": {
    "id": "0",
    "role": "dialog",
    "name": "Conferma",
    "value": null,
    "states": ["enabled", "showing"],
    "actions": [],
    "box": {"x": 300, "y": 200, "width": 400, "height": 180, "space": "actuation"},
    "center": {"x": 500, "y": 290, "space": "actuation"},
    "children": [
      {
        "id": "0/2/1/3",
        "role": "button",
        "name": "Invia",
        "value": null,
        "states": ["enabled", "focusable", "showing"],
        "actions": ["click", "focus"],
        "box": {"x": 412, "y": 260, "width": 88, "height": 32, "space": "actuation"},
        "center": {"x": 456, "y": 276, "space": "actuation"},
        "children": []
      }
    ]
  },
  "node_count": 2,
  "truncated": false,
  "truncated_ids": [],
  "reason": null,
  "screenshot": null
}
```

When no tree can be produced, `root` is `null`, `reason` is `unavailable`, `denied` or `empty`, and
`screenshot` carries the fallback capture unless `--no-fallback` was given.

### Element-addressed result

```json
{
  "action": {"action": "click", "selector": {"role": "button", "name": "Invia"}, "via": "auto"},
  "resolved": null,
  "performed": true,
  "duration_ms": 12.4,
  "matched": {"id": "0/2/1/3", "role": "button", "name": "Invia", "actions": ["click", "focus"]},
  "via": "action",
  "error": null
}
```

`resolved` is `null` when the action went through the platform API, because no coordinate was
involved. With `via: "coordinate"` it carries the centre of the matched node, in actuation units.

### Selector errors

`AmbiguousNodeError` is exit code `1`, and its payload is the part that matters:

```json
{
  "error": {
    "type": "AmbiguousNodeError",
    "message": "3 nodes match role=button name~=OK; narrow the selector or pass --nth",
    "candidates": [
      {"id": "0/1/2", "role": "button", "name": "OK",
       "box": {"x": 100, "y": 90, "width": 60, "height": 24, "space": "actuation"}},
      {"id": "0/4/2", "role": "button", "name": "OK",
       "box": {"x": 520, "y": 300, "width": 60, "height": 24, "space": "actuation"}}
    ]
  }
}
```

`NodeNotFoundError` carries the fallback `screenshot` path, because a selector that matched nothing
is exactly the signal to switch to vision.

### Batch input JSON

A JSON array of action objects, discriminated on `action`:

```json
[
  {"action": "click", "x": 120, "y": 340, "space": "screenshot", "verify": true},
  {"action": "type", "text": "hello", "delay": 0.2},
  {"action": "key", "combo": "enter"}
]
```

An element-addressed batch, carrying no coordinates at all:

```json
[
  {"action": "focus",  "role": "text",   "name": "Destinatario"},
  {"action": "type",   "text": "mario@example.com"},
  {"action": "click",  "role": "button", "name": "Invia"},
  {"action": "tree"}
]
```

Selector fields are flat in the batch JSON — `role`, `name`, `id`, `exact`, `nth`, `window`, `via`
— and are collected into a `NodeSelector` by the model validator, so the file reads the way the CLI
flags do.

### `config init` JSON

```json
{
  "action": "init",
  "config-file": "/work/.use-computer/config.toml",
  "env-file": null,
  "profile": "staging",
  "backend": "vnc",
  "probe": {
    "ok": true,
    "screen": {
      "width": 1280, "height": 800,
      "screenshot_width": 1280, "screenshot_height": 800,
      "scale": 1.0
    },
    "error": null
  }
}
```

`env-file` is the path a password was written to, or `null`. `probe` is `null` when `--no-probe`
was given. Exit `0` when the config was written and the probe succeeded or was skipped, `1` when
the probe failed — the file is still on disk, so it can be corrected by hand — and `2` on bad
usage.

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

## Accessibility Protocol

```python
@runtime_checkable
class AccessibilityProvider(Protocol):
    name: str
    def snapshot(self, scope: TreeScope, depth: int) -> UINode: ...
    def perform(self, node_id: str, action: str, value: str | None) -> bool: ...
    def close(self) -> None: ...
```

`snapshot` returns the **unpruned** tree; pruning and the node budget are applied above it by
`selectors.py`, so ids stay addressable and the policy is testable without a desktop.

`perform` returns whether the platform actually carried the action out. It is a boolean rather than
`None` because several of these APIs report failure by returning false rather than raising, and a
provider that only catches exceptions would report success for an action that did nothing at all.
A `False` return is what triggers the fallback to a coordinate click under `--via auto`.

Construction raises `UITreeUnavailableError` naming the extra — and, on Linux, the system package
as well. The provider is chosen by the running platform, never by configuration.

## Python API

```python
from use_computer import Session, ClickAction, TypeAction

with Session.from_profile("staging") as s:
    result = s.run([
        ClickAction(x=120, y=340, space="screenshot", verify=True),
        TypeAction(text="hello"),
    ])
```

Addressing elements instead of pixels:

```python
from use_computer import Session, ClickAction, FocusAction, NodeSelector, TreeAction

with Session.from_profile("laptop") as s:
    result = s.run([
        FocusAction(selector=NodeSelector(role="text", name="Destinatario")),
        TypeAction(text="mario@example.com"),
        ClickAction(selector=NodeSelector(role="button", name="Invia")),
        TreeAction(),
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
tree-max-nodes = 400
tree-depth = 20
tree-fallback = true

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
renaming or removing one requires a change request. `tree`, `matched` and `via` are additions and
are `null` on every action that does not use them, so an existing consumer is unaffected.

Coordinate addressing is unchanged and stays that way: an agent holding pixels from ui-locator
behaves exactly as it did before any of this existed.
