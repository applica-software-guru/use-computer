---
title: "Agent Skill"
status: new
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
---

# Agent Skill

The calling agent needs instructions for driving `use-computer`, and those instructions must match
the installed version. So the skill ships **inside the package** and is installed from it.

## Where it lives

`code/src/use_computer/skill/SKILL.md` — package data inside the package, **not** at the repository
root. A file at the repository root does not ship in the wheel, and a skill that is not in the
wheel does not exist for anyone who installed from PyPI. CI verifies its presence in the built
wheel before release.

## The `skill` command

```bash
use-computer skill install [--scope <scope>] [--dir <path>] [--force]
use-computer skill update  [--scope <scope>] [--dir <path>]
use-computer skill remove  [--scope <scope>] [--dir <path>]
use-computer skill status  [--scope <scope>] [--dir <path>]
```

## Scopes

`--scope` accepts `user`, `project`, `agents` or `claude`.

- **project** follows the layout the target project already uses — `.claude/skills/` if that is
  what is there, `.agents/skills/` if that is — and defaults to the neutral **`.agents/skills`**
  when neither exists.
- `--dir` overrides the destination entirely.

## Rules

- `install` **refuses to overwrite** an existing skill without `--force`.
- Neither `install` nor `remove` ever touches a directory that does not carry this skill's
  **frontmatter marker**. Removing a directory someone else owns is unrecoverable; the marker is
  the proof of ownership.
- `status` reports installed / missing / outdated per scope, comparing against the bundled copy.

## Agent Notes

Load the skill as package data (`importlib.resources`), never by path relative to `__file__` — the
package may be zipped.
