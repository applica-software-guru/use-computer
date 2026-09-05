---
title: "The skill covers the whole surface"
status: pending
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# The skill covers the whole surface

## Why

The skill is the only thing that makes any of this reachable by the agent it was built for. It has
been extended four times today, each time for whatever had just changed, and never checked as a
whole. Checking it as a whole:

| | In the CLI | In the skill |
| --- | --- | --- |
| `collapse` | yes | **no** |
| `skill` (install/update/remove/status) | yes | **no** |
| `--via` | yes | **never mentioned** |
| `--delay` | yes | **never mentioned** |
| `--nth`, `--exact` | yes | once each, in passing |

An agent cannot use what it has not been told about. `--via` is the flag that chooses which rung of
the ladder an action takes — the central idea of the whole tool — and the skill has never named it.
`collapse` is simply absent, so anything expanded stays expanded.

This is a predictable failure of extending a document per change: each edit is locally correct and
nobody reads the result end to end. The fix is to write it against the surface rather than against
the diff, and to keep something that fails when they drift apart.

## What changes

**The skill is rewritten against the command list, not against what changed recently.** Every
command, every flag, once, in the order an agent meets them:

1. The ladder, and the decision procedure — `windows`, `tree`, act, and vision only when the tree
   cannot see it.
2. Reading: `windows`, `tree` and every flag that shapes them.
3. Acting on an element: the selector flags, `--via`, and the one-line-per-verb list including
   `collapse`.
4. Acting on a coordinate: the pointer and keyboard actions, `--space`, `--delay`.
5. Looking: `screenshot`, `--of`, `--verify`, and where the files go and how to remove them.
6. Batches.
7. Errors, and what to do about each.
8. Setup: `config init`, `config show`, and the `skill` command itself.

**And a test asserts the coverage.** Every command typer knows about, and every option name the CLI
declares, must appear in `SKILL.md`. It fails when a flag is added and the skill is not updated,
which is exactly how the five gaps above arrived.

## Deliberately not done

**No generated skill.** A dumped `--help` is not instruction: it lists flags without saying which
rung to take or which error means switch to vision, and that judgement is most of what the skill is
for. The test checks that everything is *mentioned*, not that the prose was machine-written.

**No second document.** There is one skill, and it ships in the wheel. A separate "advanced" page
would be the thing nobody updates next time.

## Documentation to update

- `product/features/skill.md` — that the skill is written against the surface, and that a test
  enforces it.
- The bundled `code/src/use_computer/skill/SKILL.md` — rewritten, and `x-skill-version` bumped so
  installed copies report as outdated.

## Agent Notes

- Get the command and option names from the typer app itself, not from a hand-kept list. A list
  would drift in exactly the way this test exists to catch.
- Some options genuinely do not belong in prose — `-v`, `--version`. Keep the exemptions in one
  named set with a reason beside it, so an exemption is a decision rather than an omission.
- The skill is read by a model with a budget. Covering everything is not licence to pad it: one
  line per flag, and the ladder gets the space instead.
