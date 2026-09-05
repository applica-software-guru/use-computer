---
title: "Agent Skill"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "1.2"
---

# Agent Skill

The calling agent needs instructions for driving `use-computer`, and those instructions must match
the installed version. So the skill ships **inside the package** and is installed from it.

## Where it lives

`code/src/use_computer/skill/SKILL.md` — package data inside the package, **not** at the repository
root. A file at the repository root does not ship in the wheel, and a skill that is not in the
wheel does not exist for anyone who installed from PyPI. CI verifies its presence in the built
wheel before release.

## What it teaches

The skill is the only reason any of this is reachable by the agent it was built for, so its
content is part of the specification, not a README:

1. **`windows`, then `tree`, then `screenshot`.** The opening decision procedure is: list the
   windows, read the tree of the one you want, act on what you find, and reach for a screenshot and
   ui-locator only when the tree cannot see the element. Order is instruction — an agent follows
   what it reads first, and a `tree` of the wrong window costs more than the list would have.
2. **Both addressing modes**, with a worked example of each, and the explicit statement that pixel
   coordinates remain correct and supported.
3. **`set-value` versus `type`**, because choosing wrong there fails silently in real applications.
4. **What is abbreviated, and how to get the rest.** A `value` is clamped and marked with `…`; an
   off-screen subtree arrives as `offscreen_children` and expands with `--of`; a budgeted tree
   reports `truncated`. An agent that mistakes an abbreviation for the whole thing draws a wrong
   conclusion from a correct answer, so each one has to name its own escape hatch.
5. **What the errors mean** — ambiguity hands back candidates to choose between; no match is the
   signal to switch to vision, and it already carries the screenshot path.

`x-skill-version` bumps whenever that guidance changes, so `skill status` reports installed copies
as outdated instead of leaving agents on stale instructions. The `description` line has to keep
naming what the skill can do, since that is what an agent reads when deciding whether it is
relevant at all.

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
