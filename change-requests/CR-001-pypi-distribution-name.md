---
title: "Publish under the distribution name use-computer-cli"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-03T00:00:00.000Z"
---

# Publish under the distribution name `use-computer-cli`

## Why

The name `use-computer` is already taken on PyPI by an unrelated, actively maintained project
("Python SDK for use.computer sandboxes", 0.0.44). Uploading under that name is rejected, so the
distribution needs a different one.

`use-computer-cli` is free, and is the same suffix convention planned for the sibling project
(`ui-locator` → `ui-locator-cli`).

## What changes

Only the **distribution name** — the name on PyPI, the thing you `pip install`. Everything else
stays exactly as it is:

| | |
| --- | --- |
| Distribution (PyPI) | `use-computer` → **`use-computer-cli`** |
| Console command | `use-computer` (unchanged) |
| Import package | `use_computer` (unchanged) |
| Repository | `use-computer` (unchanged) |
| Extras | `[local]`, `[vnc]` (unchanged) |

## Documentation to update

- `product/features/backends.md` — the install commands, and a note that the distribution name
  and the command name deliberately differ.
- `product/users.md` — the `pip install` mention in the developer persona.
- `system/tech-stack.md` — record the distribution name alongside the packaging decisions, since
  that is where the release gate lives.

## Code that follows

- `pyproject.toml`: `name = "use-computer-cli"`. The `[project.scripts]` entry keeps pointing the
  `use-computer` command at `use_computer.cli:main`.
- `BackendNotAvailableError`: its message tells the user what to install, so it must name the
  distribution, not the import package — `pip install "use-computer-cli[vnc]"`.
- `README.md` and the bundled `SKILL.md`: the install instructions.

## Agent Notes

Do not rename the import package, the console script, or the repository. A distribution name
that differs from the command it installs is normal; renaming the rest would be a much larger
change and is explicitly not wanted here.
