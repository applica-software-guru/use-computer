---
title: "Say which label sits next to an unnamed field"
status: pending
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# Say which label sits next to an unnamed field

## Why

The question that started this was: given two text fields, which one is the search box and which is
the message box? The first guess was that the tool was leaving information unread — `description`,
the `placeholder-text` attribute, the `LABELLED_BY` relation. That guess was measured and is
**wrong**: across 226 text fields on this desktop, and again on a purpose-built GTK form, **not one**
carries any of them.

But a real GTK form shows where the information actually lives:

```
0/0/0/0/0 text                       949,551 168x28
0/0/0/0/1 label "Password"           860,551  58x28     ← same y
0/0/0/0/2 text                       949,517 168x28
0/0/0/0/3 label "Email"              860,517  33x28     ← same y
0/0/0/0/4 text  !focused             949,483 168x28
0/0/0/0/5 label "Nome utente"        860,483  79x28     ← same y
```

The labels are right there, as siblings, each vertically aligned with its field. Every one of those
fields is anonymous, and every one of them is unmistakably identified — by geometry, in a tree the
agent already has.

An agent can do this pairing itself. It should not have to, three fields at a time, on every form
it meets.

## What changes

`UINode` gains **`near: str | None`**: the text of the label that sits immediately beside or above
this node, when the node has no name of its own.

```
0/0/0/0/4 text ~"Nome utente" !editable,focused [click,focus,set_value] 949,483 168x28
```

The rule, deliberately narrow:

- only for a node with **no name**, because a real name always wins;
- only from a sibling whose role is `label` and which **carries text**;
- only when it is **vertically aligned** (overlapping y ranges) and immediately to the left, or
  **horizontally aligned** and immediately above — the two arrangements forms actually use;
- only when **exactly one** label qualifies. Two candidates means no answer, as everywhere else.

## It is not a name, and must not be printed as one

This is the part that matters. `name` is what the application says about itself; `near` is what
`use-computer` inferred from where things sit. Merging them would launder a guess into a fact, and
an agent acting on `--name "Email"` would be selecting on something the application never said.

So it is a separate field, with its own marker in the rendering (`~"Email"`), and **selectors match
`name`, never `near`**. `near` is there to be *read* — it is how an agent decides which id to use,
not something it can address.

## Deliberately not done

**No reading `description`, `placeholder-text` or `LABELLED_BY`.** Measured on 226 fields and on a
GTK form: zero hits. If a toolkit ever does populate them they should feed `name` directly, not
this, and that is a different change request written against evidence rather than hope.

**No inference beyond one adjacent label.** No nearest-by-distance, no walking up to a group's
heading, no reading a whole row. Each of those is plausible, each is another guess, and a wrong
`near` is worse than an absent one — it reads as certainty.

**Nothing for painted placeholders.** Telegram's "Write a message…" is pixels and no amount of
geometry finds it. That is [CR-011](CR-011-crop-the-screenshot-to-a-node.md)'s job, and the two
answer different halves of the same question.

## Documentation to update

- `product/features/ui-tree.md` — `near`, the rule, and why it is not `name`.
- `product/features/element-addressing.md` — selectors match `name` and never `near`, and why.
- `product/features/skill.md` — `~"Email"` means *inferred from position*; use it to pick an id,
  do not pass it to `--name`.
- `system/entities.md` — `UINode.near`.
- `system/interfaces.md` — the field and its rendering.
- `system/architecture.md` — the pairing is policy over a built tree, so it lives in
  `selectors.py` with pruning and the rest, and tests without a desktop.

## Agent Notes

- Run the pairing **before** pruning drops the labels. A label that only exists to name a field is
  exactly the kind of node pruning removes, and after pruning the information is gone.
- "Exactly one candidate" is the whole safety of this. A row of three fields and three labels must
  pair each with its own by alignment, and anything ambiguous must yield nothing.
- Aligned means overlapping ranges, not equal coordinates: a 28px field beside a 16px label share
  no exact y and are plainly on the same line.
