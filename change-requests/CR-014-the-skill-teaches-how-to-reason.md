---
title: "The skill teaches how to reason, not what --help already says"
status: pending
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# The skill teaches how to reason, not what `--help` already says

## Why

There are two ways to know what is on a screen, and they fail in different places:

- **Structure.** The operating system says there is a button called "Invia" at a box, that it is
  enabled, and that it can be pressed. Exact, cheap, addressable by name, and it reaches things
  that are not even drawn — the items of a closed menu are operable without opening it.
- **Pixels.** A picture says what is actually rendered: a placeholder an application paints rather
  than exposes, an icon with no name, which of two identical fields looks like a search box.

Neither subsumes the other, and choosing between them is the whole skill of using this tool.
Telegram exposes nothing for its message box — verified: name, description, attributes, the text
interface, relations and the entire child subtree are all empty — while a GTK form exposes labels
but leaves the fields anonymous, so the answer is in the geometry the tree already reports.

**None of that is in `--help`, and none of it can be.** `--help` lists flags. It cannot say which
of two ways to look, what each one is blind to, or what a particular error means about which to try
next.

The skill currently teaches the ladder and the commands, and an audit found real gaps in the
commands — `collapse` and `skill` absent, `--via` never mentioned. But the gaps are the symptom.
Filling them by enumerating the surface would produce a worse document: a second `--help`, longer
than the first, that still does not say when to stop reading the tree and take a picture.

## What changes

**The skill is rewritten around the two modes and the traffic between them.** Its spine becomes:

### What each way knows, and what it cannot know

| | Structure (`tree`) | Pixels (`screenshot`) |
| --- | --- | --- |
| Tells you | roles, names, states, boxes, what is operable | what is drawn: painted text, icons, colour, layout |
| Reaches | things not on screen — a closed menu's items | only what is visible |
| Costs | a few hundred tokens | a picture, and a vision pass |
| Blind to | anything the application paints instead of exposing | node ids, `enabled`, anything off screen |
| Acts by | name or id, with no coordinates at all | a coordinate you have to aim |

### How to move between them

- Start with `windows`, then `tree`. It is cheaper and it is exact.
- `reason: unavailable` or `empty` means this application exposes nothing — go and look, the
  screenshot is already attached to that answer.
- A selector that matches nothing arrives with a screenshot for the same reason.
- **The tree sees a node but cannot name it** — two anonymous text fields — then do not photograph
  the screen: `screenshot --of <id>` crops to that node. The tree still knows exactly *where*; only
  *what* is missing.
- Geometry answers more than it looks: a composer is wide and at the bottom, a search box narrow
  and at the top, and both are in the tree already.
- `!focused` moves when you click. Clicking one of two identical fields and re-reading is often
  cheaper than looking at either.

### And the judgement that has no flag

`--via` chooses which rung an action takes, and the skill has never mentioned it — which is the
single worst omission, because it is the central idea of the tool expressed as a flag.

## The test inverts

The obvious test — assert every command and flag appears in the skill — is the wrong direction, and
would enforce exactly the `--help`-duplicating document this change request exists to avoid.

**The useful test is the opposite: every command and flag the skill mentions must actually exist.**
A skill that tells an agent to pass `--human` after it was removed is actively harmful; a skill
that does not mention `collapse` is merely thin, and `--help` covers thin. Rot in the direction of
lying is what needs a test.

## Deliberately not done

**No enumeration of the surface.** The skill names the commands an agent needs in order to reason —
and says `--help` lists the rest. Duplicating a generated list is how it would rot.

**No generated skill.** A dumped `--help` is not instruction. The judgement is the content.

**No second document.** One skill, shipped in the wheel. An "advanced" page is the thing nobody
updates next time.

## Documentation to update

- `product/features/skill.md` — what the skill is for: the two ways of knowing and the traffic
  between them, not a flag list; and the test that its claims are real.
- The bundled `code/src/use_computer/skill/SKILL.md` — rewritten around that spine, with
  `x-skill-version` bumped.

## Agent Notes

- Take the real names from the typer app when checking the skill's claims, not from a hand-kept
  list — a list drifts in exactly the way this test exists to catch.
- The comparison table is the part to get right. Everything else in the skill is reference; that
  table is the thing an agent actually reasons with, and it is what no `--help` can produce.
- Covering the reasoning is not licence to pad. One line per flag that carries a judgement, and
  nothing at all for the flags that do not.
