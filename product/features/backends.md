---
title: "Backends"
status: synced
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
---

# Backends

Two interchangeable backends sit behind one interface. Adding a third should be configuration and a
new module, never a change to the action layer.

## local

Drives the display of the machine `use-computer` runs on.

- Input via **pynput** (1.8+), capture via **mss** (10+).
- pyautogui is deliberately *not* used: its last release, 0.9.54, dates from 2023.
- Requires an **explicit opt-in** — this backend types on the user's own keyboard and moves their
  own pointer. See [safety.md](safety.md).
- On macOS it needs Accessibility and Screen Recording permissions; when the host denies them the
  backend raises a clear error naming the permission, rather than silently doing nothing.

## vnc

Drives a remote framebuffer over RFB.

- Uses **vncdotool** (1.3+), which provides move, click, key, type and capture over RFB.
- Connection setup dominates the cost of a single action, which is why a run performs a whole
  batch over one connection. See [batch-execution.md](batch-execution.md).
- Credentials come from the environment or `.env`, never from the committed config file.

## One interface

Every backend implements a runtime-checkable `Protocol` covering `screenshot`, `move`, `click`,
`drag`, `scroll`, `type_text` and `key`, plus reporting its own coordinate space and screen size.

Backends are **optional extras, imported lazily**, so the package installs without them:

```bash
pip install use-computer            # no backend
pip install "use-computer[local]"   # pynput + mss
pip install "use-computer[vnc]"     # vncdotool
```

Constructing a backend whose dependency is missing raises `BackendNotAvailableError`, whose message
names the exact extra to install.

## Named profiles

A backend is selected by a **named profile** in the project-local config file, chosen with a
`--use` flag:

```toml
[profiles.laptop]
backend = "local"

[profiles.staging]
backend = "vnc"
host = "10.0.0.5"
port = 5900
```

Adding a backend target is editing this file — not writing code. See
[configuration.md](configuration.md).

## Agent Notes

- Never import a backend's dependency at module import time; the import happens inside the
  backend's constructor so that `use-computer --help` works with no extras installed.
- Both backends normalise the same key syntax — see [key-syntax.md](key-syntax.md).
