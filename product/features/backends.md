---
title: "Backends"
status: synced
author: ""
last-modified: "2026-09-10T00:00:00.000Z"
version: "1.5"
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

## Reading and operating the interface

Actuation is one capability; reading the accessibility tree and operating elements through it is
another, and the two do not belong to the same backend split. `local` has it, per platform; `vnc`
structurally cannot, because RFB carries pixels and nothing else.

So it is a second Protocol, `AccessibilityProvider`, chosen by the **running platform** rather than
by configuration — a profile does not get to claim macOS accessibility on Linux:

| Platform | API | Binding | How to install it |
| --- | --- | --- | --- |
| Windows | UI Automation | `uiautomation` | `pip install "use-computer-cli[local,tree]"` |
| macOS | `AXUIElement` | `pyobjc-framework-ApplicationServices` | the same |
| Linux | AT-SPI 2 | the distro's PyGObject | **not the extra** — see below |

**Linux is not a pip problem, and the `tree` extra deliberately covers nothing there.** PyGObject
has no Linux wheel, so listing it in the extra made `pip install "use-computer-cli[tree]"` build
from source, need pycairo and system headers, and *fail* — leaving the user with no CLI at all
rather than a CLI missing one capability. The bindings are already on almost every desktop; a
virtualenv only has to be allowed to see them:

```bash
sudo apt install python3-gi gir1.2-atspi-2.0
python3 -m venv --system-site-packages .venv     # the distro's python3, not another minor version
.venv/bin/pip install "use-computer-cli[local]"
```

**`gi` is a compiled extension**, built for one Python minor version — Ubuntu 22.04 ships it for
3.10 — so a 3.12 virtualenv with `--system-site-packages` exposes a module it cannot import. That
is the constraint that actually decides whether any of this works, and it is invisible: both
packages report as installed.

So the error **looks before it speaks**. `gi` on disk sits next to a
`_gi.cpython-310-…so` whose name carries the version, and the message says which of the three
situations this is: nothing installed, installed for this interpreter but not visible, or installed
for a different one. Advice that tells somebody to install what they already have is worse than no
advice: they follow it, nothing changes, and they conclude the tool is broken.

`UITreeUnavailableError` says exactly that when the bindings are missing, and does **not** offer an
extra that would not help — a wrong install line costs every new user their first ten minutes.

On a vnc profile, `tree` and every element-addressed action fail immediately with that error and
the agent uses coordinates. No emulation, no pretending.

## One interface

Every backend implements a runtime-checkable `Protocol` covering `screenshot`, `move`, `click`,
`drag`, `scroll`, `type_text` and `key`, plus reporting its own coordinate space and screen size.

Backends are **optional extras, imported lazily**, so the package installs without them:

```bash
pip install use-computer-cli            # no backend
pip install "use-computer-cli[local]"   # pynput + mss
pip install "use-computer-cli[vnc]"     # vncdotool
```

The distribution is named `use-computer-cli` because `use-computer` is taken on PyPI by an
unrelated project. The command it installs, and the package it imports, stay `use-computer` and
`use_computer` — a distribution name that differs from its command is normal, and renaming the
rest would buy nothing.

Constructing a backend whose dependency is missing raises `BackendNotAvailableError`, whose message
names the exact extra to install. That message is what a stuck agent reads, so it must name the
**distribution** — `pip install "use-computer-cli[vnc]"` — not the import package.

## Named profiles

A backend is selected by a **named profile** in the project-local config file. `--use` names one
explicitly, and where only one is defined it is selected without being named:

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
