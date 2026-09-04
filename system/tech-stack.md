---
title: "Tech Stack"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.3"
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
  | `linux` | `PyGObject >= 3.46` | The supported AT-SPI binding — but see below. |

  **Linux needs a system package too.** There is no `pyatspi` on PyPI: the bindings ship as
  `gir1.2-atspi-2.0` (plus `python3-pyatspi` on Debian and Ubuntu) and PyGObject reaches them
  through GObject Introspection. `pip install` alone cannot finish the job, so
  `UITreeUnavailableError` names both halves.

  Not **dogtail**: it is the obvious Linux shortcut and is GPLv2 — fine for a test harness that
  runs it, wrong for a permissively licensed library that imports it. Not **atomacos**: its last
  release, 3.3.0, dates from May 2021, which is the same staleness argument that already ruled out
  pyautogui, and it should be applied consistently or not at all.

## Development

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
