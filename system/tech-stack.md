---
title: "Tech Stack"
status: synced
author: ""
last-modified: "2026-09-05T13:15:00.000Z"
version: "1.7"
---

# Tech Stack

Mirrors ui-locator. Every pin below exists because of something that broke.

## Distribution

Published to PyPI as **`use-computer-cli`** — `use-computer` is taken there by an unrelated
project. The console script stays `use-computer` and the import package stays `use_computer`.
Anything that tells a user what to install names the distribution.

## Runtime

- **Python 3.10 or newer**, with **3.12** as the runtime.
- **uv** for dependencies and builds. `uv.lock` is **left uncommitted**, so CI resolves the way a
  user installing from PyPI does.
- **hatchling** as the build backend.

## Core dependencies

| Package | Constraint | Why |
| --- | --- | --- |
| pydantic | 2.x | Every data model; result models frozen. |
| pydantic-settings | 2.x | Configuration under the `USE_COMPUTER` env prefix. |
| typer | **>= 0.16, never 0.12** | CLI. 0.12 lacks what this CLI relies on. |
| rich | >= 13 | Terminal output — **stderr only**, never JSON. |
| pillow | current | Screenshots and before/after comparison. |
| python-dotenv | current | `.env` layering. |
| tomli | **only below Python 3.11** | `tomllib` is stdlib from 3.11. |

## Optional extras

Backends are optional extras, imported lazily, so the package installs without them.

- **`local`** — `pynput >= 1.8` (input), `mss >= 10` (capture).
  Not pyautogui: its last release, 0.9.54, dates from 2023.
- **`vnc`** — `vncdotool >= 1.3`, which provides move, click, key, type and capture over RFB.
- **`tree`** — the accessibility bindings, one per platform behind a `sys_platform` marker:

  | Marker | Package | Why this one |
  | --- | --- | --- |
  | `win32` | `uiautomation >= 2.0` | Pure Python over comtypes, no compiler. 2.0.29 shipped August 2025. |
  | `darwin` | `pyobjc-framework-ApplicationServices >= 10` | `AXUIElement` from the source. 12.2.2 shipped August 2026. |

  **Linux is deliberately absent from the extra.** PyGObject has no Linux wheel, so naming it here
  made `pip install "use-computer-cli[tree]"` build from source, need pycairo and system headers,
  and fail outright — the user got no CLI at all, which is strictly worse than a CLI without one
  capability. The AT-SPI bindings come from the distro (`python3-gi`, `gir1.2-atspi-2.0`) and are
  reached with a `--system-site-packages` virtualenv. The error message says so.

  Not **dogtail**: it is the obvious Linux shortcut and is GPLv2 — fine for a test harness that
  runs it, wrong for a permissively licensed library that imports it. Not **atomacos**: its last
  release, 3.3.0, dates from May 2021, which is the same staleness argument that already ruled out
  pyautogui, and it should be applied consistently or not at all.

## Development

### The virtualenv has to be the distro's Python

`gi` is a **compiled** extension, built for one Python minor version, and it comes from the distro.
A virtualenv on any other interpreter cannot import it however `--system-site-packages` is set, so
`uv run use-computer tree` on a machine whose default is a different minor version fails with the
capability missing. Build the environment on the interpreter the distro built it for:

```bash
uv venv --python /usr/bin/python3 --system-site-packages
uv sync --all-extras
```

`uv sync` keeps the flag, so this is a one-off. **Do not commit a `.python-version`** pinning a
number: the right interpreter is whichever one that machine's distro packaged `gi` for, and a pin
would send uv off to download a standalone build that has no `gi` at all — the exact failure this
avoids.

There is a second reason to like it. On Ubuntu 22.04 this puts local development on **3.10**, the
declared floor, while CI covers 3.12. [BUG-002](../bugs/BUG-002-required-options-exit-1-on-the-typer-floor.md)
lived at the floor and was invisible on a newer typer until the release rehearsal found it; running
there by default is how that gets caught before CI rather than after.

- **pytest** + **pytest-mock**, with a **fake backend** that records the actions it was asked to
  perform.
- **ruff**, line length **100**, selecting **E, F, I, UP, B, SIM, C4**, with **B008 ignored in the
  cli module** for typer idioms.
- **mypy in strict mode**.

## CI / Release

Two GitHub Actions workflows, at the repository root because GitHub reads them nowhere else, both
running in `code/` where the package lives. Action majors are pinned to what is current and the
pin carries a comment saying so, so the next reader knows it was checked rather than copied.

**`ci.yml`** — every push and pull request. The matrix, lint, type check, tests, and a check that
the CLI works with **no extras installed**. Nothing is published.

**`publish.yml`** — releases and rehearsals. It runs the same matrix first, because publishing
untested code is the failure the whole gate exists to prevent, then builds, then uploads:

1. tests a **matrix over both ends of the supported typer range**;
2. builds;
3. uploads to PyPI **when a release is published**, gated on the git tag matching the version in
   `pyproject.toml` and on the bundled `SKILL.md` being present in the wheel;
4. on **manual dispatch**, uploads to TestPyPI instead, so the whole pipeline can be rehearsed
   before a version number is spent — PyPI never lets one be reused. With no TestPyPI token
   configured the run still builds and checks the artifacts, and says why it skipped the upload;
5. prefers **Trusted Publishing** over a long-lived token, with `id-token: write` for PEP 740
   attestations.

**A diagnostic step cannot fail the job.** CI prints the resolved dependency versions so a later
failure can be read against them, and for days it did nothing else: `rich` dropped its
module-level `__version__`, the step raised, and every leg went red *before pytest ran*. Versions
come from `importlib.metadata.version(...)` — packaging metadata rather than a convention a library
may drop — and the step swallows its own exit code. A red tick that has been red for days stops
being read, which is the real cost.

The job that proves the package installs **with no extras** installs into a venv, not with
`--system`: a hosted runner's system interpreter is externally managed and refuses. That failure
sat behind the diagnostic one and only appeared once it was fixed, which is the argument for not
leaving a red tick red.

`ruff` runs with a **cold cache** in CI. A stale cache once reported a clean tree while a real
lint error sat in the file it had already seen; CI is always a machine that has never linted the
file, so it is the one that finds out.

## Conventions that cost real debugging in ui-locator

- **Never import a transitive dependency without declaring it.** That is how an undeclared `click`
  import survived until typer dropped click.
- **Declare a dependency floor that is actually tested, and verify it in CI.**
- **In tests, strip ANSI escapes from CLI output and pin `TERM` and `COLUMNS`.** rich enables
  colour inside GitHub Actions, and its highlighter splits an option token across styled spans — so
  substring assertions pass locally and fail on CI.
- **Isolate the test environment** from ambient `USE_COMPUTER`, `CLAUDE` and `XDG` variables, and
  from any project root above the checkout.

## Agent Notes

These constraints are not preferences. Do not relax a pin, widen a floor, or "simplify" a test
fixture that exists for one of the reasons above without a change request.
