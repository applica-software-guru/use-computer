---
title: "Tech Stack"
status: synced
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
---

# Tech Stack

Mirrors ui-locator. Every pin below exists because of something that broke.

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

## Development

- **pytest** + **pytest-mock**, with a **fake backend** that records the actions it was asked to
  perform.
- **ruff**, line length **100**, selecting **E, F, I, UP, B, SIM, C4**, with **B008 ignored in the
  cli module** for typer idioms.
- **mypy in strict mode**.

## CI / Release

A GitHub Actions workflow that:

1. tests a **matrix over both ends of the supported typer range**;
2. builds;
3. uploads to PyPI **when a release is published**, gated on the git tag matching the version in
   `pyproject.toml` and on the bundled `SKILL.md` being present in the wheel;
4. prefers **Trusted Publishing** over a long-lived token.

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
