---
title: "Agent Skill"
status: synced
author: ""
last-modified: "2026-09-10T00:00:00.000Z"
version: "5.0"
---

# Agent Skill

The calling agent needs instructions for driving `use-computer`, and those instructions must match
the installed version. So the skill ships **inside the package** and is installed from it.

## Where it lives

`code/src/use_computer/skill/SKILL.md` — package data inside the package, **not** at the repository
root. A file at the repository root does not ship in the wheel, and a skill that is not in the
wheel does not exist for anyone who installed from PyPI. CI verifies its presence in the built
wheel before release.

## What it is for

`--help` lists the flags. What it cannot say is **which of two ways to look**, and that is the
skill's job:

- **Structure** — the OS says there is a button called "Invia", enabled, at a box, and pressable.
  Exact, cheap, addressable by name, and it reaches things that are not drawn at all.
- **Pixels** — a picture says what is actually rendered: a placeholder an application paints
  rather than exposes, an icon with no name.

Neither subsumes the other. The skill's spine is a table of what each knows and what each is blind
to, and the traffic between them: which error means *go and look*, and how to look at one node
instead of the screen.

Enumerating the surface would produce a second `--help`, longer than the first, that still would
not say when to stop reading the tree. So it names the commands and the flags that carry a
**judgement** — `--via` above all, which chooses the rung — and points at `--help` for the rest.

A flag that carries a judgement must be described **where it exists**. `--via` is not universal:
the element-only actions have no coordinate form and reject it, so presenting it as if every
command took it hands the agent a usage error in the middle of a task.

Saying the same thing in four places costs the smaller reader four times and teaches it once, so
each idea is stated where it is needed and nowhere else.

**A test asserts the skill's claims are real**, not that it is complete: every flag and command it
mentions must exist, on the command it is claimed for. That is the direction that matters. A skill
telling an agent to pass a removed flag is actively harmful; one that omits `collapse` is merely
thin, and `--help` covers thin.

## Who reads it

Two readers, and they fail differently.

A frontier model holds the whole argument at once and reasons by analogy from it. A 27B running
locally — Qwen, Gemma, whatever is on the same desk — does not. It takes what is in front of it and
acts, and when it has not followed the argument it does not say so: it emits a plausible command
with a wrong flag.

Neither reader is served by dropping the argument, because what is being taught **is** a judgement
and a judgement cannot be tabulated. Both are served by **order**. An agent acts on what it reads
first, so the executable procedure comes first and the reasoning follows it.

This is also why the skill is **one file**. Splitting the procedure from the reasoning is the usual
way to do progressive disclosure, and here it fails for the reader it would be for: a smaller model
does not notice it is under-informed and go and open the second file. The judgement would end up
behind a door that only the audience which does not need it ever opens, while the frontier model
pays an extra read for material it was already getting.

## What it teaches

The skill is the only reason any of this is reachable by the agent it was built for, so its
content is part of the specification, not a README:

1. **The opening procedure, before anything else in the document.** Six numbered steps, executable
   without reading further: `windows` for what is open and the `--window` value everything below
   needs; `activate` to bring that window forward; `tree` for roles, names, ids and boxes; act on an
   element by name; `tree` again to confirm; and a screenshot cropped to a node only when the tree
   cannot see the thing. Order is instruction. A comparison table is the right *second* thing to
   read and the wrong first, and a `tree` of the wrong window costs more than the list would have.
2. **Both addressing modes**, with a worked example of each, and the explicit statement that pixel
   coordinates remain correct and supported.
3. **`set-value` versus `type`**, because choosing wrong there fails silently in real applications.
4. **How to read the output.** Everything comes back as text: one line per node, per window or
   per action. The skill teaches those line formats, because they are what an agent looks at.
   It must **not** tell the agent to parse stdout, which is what it used to say first.
5. **What is abbreviated, and how to get the rest.** A `value` is clamped and marked with `…`; an
   off-screen subtree arrives as `offscreen_children` and expands with `--of`; a budgeted tree
   reports `truncated`. An agent that mistakes an abbreviation for the whole thing draws a wrong
   conclusion from a correct answer, so each one has to name its own escape hatch.
6. **What the errors mean** — ambiguity hands back candidates to choose between; no match is the
   signal to switch to vision, and it already carries the screenshot path.
7. **What a result is worth.** A result line reports what was *attempted*. An accessibility API
   answers "I invoked that action", never "the application did something", and an application is
   free to ignore it — so a success can be true and mean nothing. That gap is permanent: it is not
   a defect to be fixed but a property of every platform this tool sits on, and an agent that has
   not been told about it will trust exactly the reports that mislead it.

   Three things follow, and the skill states them where they are needed rather than as a list of
   caveats:

   - **`[actions]` is what the platform will accept, not what will work.** When a result and the
     screen disagree, the next move is **another action on the same node** — the widget that
     ignores `click` often honours `select` — not a jump to vision.
   - **Confirm by re-reading, not by diffing.** After an element action, `tree` says *what* the
     state is now; change detection only ever says that some pixels moved, has a floor below which
     it says nothing, and cannot tell a click apart from a clock.
   - **A coordinate enters whatever window is in front.** Pass `--window` so the tool brings the
     right one forward.

   The current skill teaches this asymmetry once — "a click that lands on nothing looks exactly
   like a click that worked" — filed under coordinates, where it reads as a caveat about rung
   three. The failures that cost a real session were on **rung one**, the rung the documentation
   calls exact and `--via auto` chooses by default.
8. **A rich tree with a hole in it.** The skill teaches two clean states: the tree answers, or it
   is empty and hands over a picture. The common state is neither — a full, correct tree around a
   region the platform does not describe. `?unexposed` names that region, it is the normal
   condition of a canvas, a map, a chart or a game, and it is the cue to switch to pixels **for
   that region only**.

9. **Nothing the agent cannot decide.** `--use` names which machine and which backend, and no
   result an agent can read tells `laptop` from `staging` — so the skill does not mention the flag
   at all, in prose or in an example. An example carrying `--use laptop` is worse than no guidance:
   a model that copies the nearest example invents a profile name for whatever machine it is
   actually running on, and gets a warning and a refusal for a decision it should never have been
   handed. Which profile to use is settled once, by whoever installed the tool — see
   [configuration.md](configuration.md).

   The skill says one thing about it, in the errors section: when the tool reports the machine is
   not configured, **stop and tell the user**. Do not guess a profile name, and do not run
   `config init` on somebody's machine to get past an error.

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

## What the `skill` command answers with

Text, like every other command, with `--format json` for a caller that parses:

```
status  project  outdated  /home/you/workspace/.agents/skills/use-computer/SKILL.md
```

This is the command an agent runs to find out whether its own instructions are current, and it was
the last one still replying with a JSON object after the contract was inverted. A contract with
three exceptions is not a contract.

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
