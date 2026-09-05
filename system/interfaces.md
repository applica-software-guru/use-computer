---
title: "Interfaces"
status: synced
author: ""
last-modified: "2026-09-05T14:20:00.000Z"
version: "4.2"
---

# Interfaces

## CLI

Console script: `use-computer`. A **default command** lets a bare action work alongside
subcommands, implemented by rewriting `argv` in the entry point.

### Action commands

```
use-computer move        --x INT --y INT [--window SCOPE]
use-computer click       [--x INT --y INT] [--button left|right|middle] [--window SCOPE]
use-computer double-click [--x INT --y INT] [--window SCOPE]
use-computer right-click  [--x INT --y INT] [--window SCOPE]
use-computer drag        --from-x INT --from-y INT --to-x INT --to-y INT [--window SCOPE]
use-computer scroll      --amount INT [--direction up|down|left|right] [--x INT --y INT]
                         [--window SCOPE]
use-computer type        --text STR [--rate FLOAT]
use-computer key         COMBO
use-computer screenshot  [--out PATH] [--of NODE_ID] [--pad INT] [--window SCOPE]
use-computer activate    --window SCOPE
```

`--window` on a **coordinate** action names the window the coordinate belongs to, and that window
is brought forward before the coordinate is sent. Omitted, the coordinate goes wherever the pointer
already is, which is what a bare coordinate has always meant. `type` and `key` take no `--window`:
they target the focus, and `activate` is how the focus is moved to a window.

`activate` is the only command whose target is a window rather than an element or a point. It
succeeds when the window is already in front (a no-op), and fails naming the window when nothing in
it can take focus.

### Element commands

```
use-computer windows     [--format text|json]
use-computer tree        [--window SCOPE] [--depth INT] [--role ROLE] [--name TEXT]
                         [--full] [--of NODE_ID] [--out PATH] [--no-fallback]
                         [--format text|json]
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
use-computer prune  [--keep N] [--dry-run]
use-computer batch  (PATH | -)  [--continue-on-error]
use-computer config init [--backend local|vnc] [--profile NAME]
                         [--host HOST] [--port PORT] [--allow-local]
                         [--dir PATH] [--no-probe] [--force]
use-computer config show [--format text|json]
use-computer skill  install|update|remove|status
                    [--scope user|project|agents|claude] [--dir PATH] [--force]
                    [--format text|json]
```

### Global options

`--use PROFILE`, `--dry-run`, `--verify`, `--space screenshot|actuation`, `--delay SECONDS`,
`-v/-vv`, `--format text|json`, `--version`.

`--version`, `config show` and `skill` obey `--format` like everything else: text by default
(`use-computer 0.2.2`, and aligned `key  value  layer  source` lines), the object under
`--format json`. A command that answers in JSON while stdout is text makes the contract worth what
its least consistent command is worth.

Text is aligned columns for `windows`, the rendering for `tree`, and one line per action for
everything else — the matched node, the rung taken, the duration, **and the payload of the action
itself**:

```
key ctrl+z — 125 ms
type 78 chars "/home/you/Desktop/workspace/20260905T140000-al…" — 2341 ms
drag (666, 660) → (666, 545) — 665 ms
move (666, 660) — 101 ms
click toggle 'Menu' at 0/0/3/0/0/0/0 via a coordinate (25, 1015) — 484 ms
activated window 'albero.png ~ Line' 0/37/0 — 210 ms
screenshot …/20260905T115147.490Z-screenshot.png 1920x1080
click at (200, 200) — changed 604x312 at 40,120 — 41 ms
```

A line is the only record of an action that cannot be read back off the screen, so it names the key
combination, the typed text (clamped, with its character count), both ends of a drag, and the
coordinate actually sent after scaling. `--verify` reports the changed **box**, not a percentage
that rounds a real change to `0%`. A `screenshot` prints its path and its size,
because the path is the answer and the size is not available anywhere else. Errors are on stderr and stdout stays empty for the action that
failed.

`--verify` writes the after-screenshot to a file and reports its path in `screenshot`, so an agent
that verified an action does not then have to ask for the screen it already paid to capture.
A screenshot is **never** returned as bytes; there is no base64 anywhere in this contract.

### Output contract

- **stdout**: text. One line per action, or the read that was asked for.
- **stderr**: every diagnostic, log line and error.
- **exit codes**: `0` success, `1` failure, `2` bad usage — unchanged, and the primary signal.

`--format json` returns the envelope below instead, written with `json.dumps`. It is a global flag
on every command that performs actions or reads the screen, and it is never inferred from
`isatty()`.

Measured in tokens on this tool: `screenshot` is 243 as JSON and 4 as text; a `click` on an element
is 4,238 against 21; the envelope alone, contents removed, is 177 before anything is said. The
consumer of this CLI is a model, and a Python API exists underneath for programs.

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

### `windows` JSON

The `windows` field of the result. By default it carries a rendering:

```json
{
  "text": "# id app role \"title\" pid x,y wxh *active\n0/29/0 Ledger window \"Conferma\" 4711 0,0 1920x1038 *",
  "windows": []
}
```

`--format json` fills `windows` with objects instead:

```json
{"text": null, "windows": [
  {"id": "0/29/0", "title": "Conferma", "role": "window",
   "pid": 4711, "box": [0, 0, 1920, 1038], "active": true}
]}
```

**`active` is true for at most one window.** It answers "which window does `--window focused`
resolve to", so it is that decision made once, not a copy of a platform flag. AT-SPI reports
`focused` per application, which marks several windows at once; that is not an answer and is not
passed through. When it cannot be determined, no window is marked.

Measured at 119 bytes a window. It must survive an application that will not answer on the
accessibility bus: that application is missing from the list, the list still comes back.

### `tree` JSON

The `tree` field of the result. By default `root` is absent and the tree arrives rendered:

```json
{
  "text": "# id role \"name\" !states [actions] x,y wxh +offscreen ?unexposed\n0 window \"Conferma\" !modal 0,0 1920x1038\n  0/2/1/3 button \"Invia\" [click,focus] 412,260 88x32",
  "root": null,
  "node_count": 24,
  "truncated": false,
  "truncated_ids": [],
  "reason": null,
  "screenshot": null
}
```

Measured at **667 tokens against 1,707** for the structured form of the same tree — the rendering
carries every field, and spends none of them on syntax. The escaping of the newlines costs 112 of
the 1,040 tokens saved, which is what keeping `stdout is JSON and nothing else` is worth.

`truncated`, `node_count` and `reason` stay structured: they are read by code, not by a reader.

`reason` describes **the application**, never a limit the caller asked for. A tree emptied by
`--depth`, by pruning or by the node budget is reported as that limit and not as `empty`, because
`empty` is the signal to abandon the tree and pay for vision.

A node carries `unexposed: [x, y, w, h]` when its children do not account for its own area — the
region the platform is not describing, which is where a canvas lives. It is computed from
positioned children only, reported when the largest uncovered strip is at least 25% of the node and
at least 10,000 square pixels, and never suppressed by `--full`: it is not an abbreviation, it is a
statement about the platform's coverage.

With `--format json`:

```json
{
  "text": null,
  "root": {
    "id": "0",
    "role": "dialog",
    "name": "Conferma",
    "states": ["modal"],
    "box": [300, 200, 400, 180],
    "children": [
      {
        "id": "0/2/1/3",
        "role": "button",
        "name": "Invia",
        "actions": ["click", "focus"],
        "box": [412, 260, 88, 32]
      },
      {
        "id": "0/2/2",
        "role": "menu",
        "name": "File",
        "actions": ["click"],
        "box": [0, 32, 37, 28],
        "offscreen_children": 5
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

When no tree can be produced, `root` and `text` are both `null`, `reason` is `unavailable`,
`denied` or `empty`, and `screenshot` carries the fallback capture unless `--no-fallback` was
given.

**stdout is still exactly one JSON object**, under every format. That is the whole reason the
rendering is a field rather than a replacement for it: an agent parses stdout without knowing which
flags produced it, and every error path keeps one shape.

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
      {"id": "0/1/2", "role": "button", "name": "OK", "box": [100, 90, 60, 24]},
      {"id": "0/4/2", "role": "button", "name": "OK", "box": [520, 300, 60, 24]}
    ]
  }
}
```

`NodeNotFoundError` carries the fallback `screenshot` path, because a selector that matched nothing
is exactly the signal to switch to vision.

`AmbiguousWindowError` is the same shape for `--window`, carrying the matching windows in a
`windows` field. It is not a rare case: a terminal puts the running command in its own title, so
the terminal executing `--window "X"` matches X.

### Batch input JSON

A JSON array of action objects, discriminated on `action`. The discriminator accepts **the CLI's
own spelling as well as the underscored form** — `set-value` and `set_value`, `double-click` and
`double_click`, `right-click` and `right_click` — because an agent that has just read
`use-computer set-value --help` has no reason to expect a different name here. An unrecognised
action is one sentence naming the input, its index and the nearest match, never a dump of the
internal union:

```
error: unknown action 'set-valeu' at index 1. Did you mean 'set-value'?
```


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

### `prune`

One line, like everything else:

```
removed 34 screenshots (12.4 MB) from /work/.use-computer/screens, kept 20, left 1 file this tool did not write
```

It removes only files matching the names the tool writes, never the directory, and reports what it
left alone. Exit `0` even when there was nothing to remove: an empty directory is not a failure.

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
    def windows(self) -> list[WindowInfo]: ...
    def snapshot(self, scope: TreeScope, depth: int) -> UINode: ...
    def perform(self, node_id: str, action: str, value: str | None) -> bool: ...
    def activate(self, window_id: str) -> bool: ...
    def active_window(self) -> ActiveWindow | None: ...
    def close(self) -> None: ...
```

`snapshot` returns the **unpruned** tree with every state; pruning, the node budget, the notable
state filter and the off-screen summary are applied above it by `selectors.py`, so ids stay
addressable and every one of those decisions is testable without a desktop.

`windows` is a shallow read of the same tree and must tolerate an application that does not answer:
it loses that application, never the list.

**It reads the desktop once.** Everything a caller needs about a window comes out of that pass,
including the `focused` fallback used when nothing claims `active` — a second walk costs as much as
the first, and there is no state here worth re-reading. Measured when this was got wrong: 879 D-Bus
calls against 145, on the branch taken while an application is starting up, which is when calls are
least likely to be answered and each one costs the full per-call bound.

`perform` returns whether the platform actually carried the action out. It is a boolean rather than
`None` because several of these APIs report failure by returning false rather than raising, and a
provider that only catches exceptions would report success for an action that did nothing at all.
A `False` return is what triggers the fallback to a coordinate click under `--via auto`.

**`True` means the action was invoked, not that the application did anything with it.** No platform
offers the second answer. A GTK colour swatch advertises `click`, accepts it, returns true and does
nothing; `select` is the action that carries its meaning. So `perform` is honest about what it
knows, and the layer above it does two things it can do: a `click` command prefers the `select`
action on a node whose role makes selection the activation (`radio`, `listitem`, `option`,
`treeitem`, `tab`, `menuitem`), and where the action should have left a trace on the node —
`checked`, `selected` — the node is re-read and the result says when nothing moved.

`active_window` is a **hint**, not an answer: what the window manager says is in front, as a pid
and a title. `None` means this platform has nothing better than the per-window flags, and is the
honest reply on Wayland or without the binding. The matching from hint to window lives in
`selectors.mark_active`, so all three platforms share it and the ambiguity cases test without a
session bus.

`activate` brings a window forward and gives it keyboard focus. A window object exposes no actions
on any of the three platforms, so the general implementation is `grab_focus` on the first focusable
descendant, which raises the top-level window on all of them; macOS prefers `AXRaise` on the window
itself where it is accepted. It returns false when nothing in the window can take focus, and is a
no-op when the window is already in front.

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
renaming or removing one requires a change request. `tree`, `windows`, `matched` and `via` are
additions and are `null` on every action that does not use them.

The **node** shape is not additive, and was changed deliberately: `box` is an array, empty fields
are omitted, and `states` carries only the notable ones. A tree carries thousands of nodes, and the
obvious shape measured 271 bytes each against 150 — five times the whole payload once off-screen
subtrees are counted rather than expanded. `--full` restores everything.

Coordinate addressing is unchanged and stays that way: an agent holding pixels from ui-locator
behaves exactly as it did before any of this existed.
