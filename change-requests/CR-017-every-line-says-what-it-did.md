---
title: "Every line says what it did, and says it in text"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# Every line says what it did, and says it in text

## Why

CR-010 made stdout text because an agent reads text. It did not finish the job: the lines are
text, but several of them **omit the thing that was done**.

From one real session, verbatim:

```
key — 125 ms                                     which key?
type — 2341 ms                                   which text? it was a 78-character path
drag at (666, 545) — 665 ms                      from where? a drag has two points
click toggle 'Menu' at 0/0/3/0/0/0/0 via a coordinate — 484 ms    which coordinate?
```

Each of these is the only record of an action that cannot be undone by reading it back. When an
agent is trying to work out why the screen does not match its model — which is most of the time
this tool is used — those lines are the evidence, and they are blank in exactly the place where
the answer would be.

`click` names the node it resolved. `key` and `type` name nothing at all. A batch of eleven
actions produced eleven lines from which the sequence could not be reconstructed.

Two more, from the same session:

- **`changed 0%`.** A real change of a few thousand pixels renders as zero, which reads as a
  denial. The percentage was never the useful part; **where** it changed is. (See BUG-009.)
- **`screenshot` reports no size**, while `screenshot --of` reports `1920x885 of 0/0/2`. The plain
  form is the one where the agent has no other way to learn it.

## And the contract is not held everywhere

Three commands still answer in JSON when stdout is supposed to be text:

- `use-computer --version` → `{"version": "0.2.2"}`
- `use-computer config show` → a single 2 KB JSON line. This is the command the skill names
  **first** when a profile misbehaves, so it is the worst one to leave dense.

And the batch parser rejects the CLI's own spelling:

```
$ echo '[{"action":"set-value", …}]' | use-computer -
error: - is not a valid action list: 1 validation error for
list[tagged-union[MoveAction,function-after[_one_target(), ClickAction],…
```

The CLI command is `set-value`; the batch demands `set_value`. Same action, two spellings, and the
error is a dump of the internal union — 400 characters that name every action type except the one
the caller should have written.

## What changes

**Each line carries its payload.**

```
key ctrl+z — 125 ms
type 78 chars "/home/bimbobruno/Desktop/workspace/20260905T14…" — 2341 ms
drag (666, 660) → (666, 545) — 665 ms
click toggle 'Menu' at 0/0/3/0/0/0/0 via a coordinate (25, 1015) — 484 ms
screenshot …/20260905T115147.490Z-screenshot.png 1920x1080
```

Typed text is clamped the way a node's `value` is, and the character count is given, because the
count is what catches a truncated or doubled paste. A drag prints both points. A coordinate action
prints the coordinate it actually sent, after scaling — which is the number a coordinate-space bug
turns on.

**`--verify` reports where, not what fraction.**

```
drag (300, 350) → (480, 450) — changed 182x104 at 299,349 — 500 ms
```

**The contract holds everywhere.** `--version` and `config show` render as text by default;
`--format json` still returns the machine form of both, and `config show` keeps every value, its
layer, its source and its environment variable — laid out as lines rather than as one long object.

**The batch accepts the CLI's spelling.** `set-value`, `double-click` and `right-click` are
accepted alongside the underscored forms, and an unrecognised action is one sentence:

```
error: unknown action 'set-valeu' at index 1. Did you mean 'set-value'?
```

## Agent Notes

- Rendering stays in `render.py` and `cli.py`; nothing here changes what an action *does*.
- Everything interpolated into a line goes through the existing escaping boundary. A node named
  `[tree]` or a typed string full of brackets must not be eaten by the renderer, which is the bug
  BUG-004 already cost us once.
- The closing summary line stays as it is. It answers a different question.
