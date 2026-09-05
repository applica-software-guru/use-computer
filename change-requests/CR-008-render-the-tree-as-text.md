---
title: "Render the tree as text, inside the JSON"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# Render the tree as text, inside the JSON

## Why

[CR-007](CR-007-cheap-reads.md) made the tree small by removing what nobody needed. This removes
what nobody *reads*: the punctuation.

Bytes were the wrong unit all along. Measured on the same window, in tokens rather than bytes —
because tokens are what an agent actually pays:

| | Bytes | Tokens | |
| --- | --- | --- | --- |
| Structured JSON (today) | 3,785 | 1,707 | 100% |
| The same tree as text | 1,744 | **555** | 33% |

JSON's overhead is not its verbosity, it is that `{`, `"`, `:`, `,` and every repeated key are
each their own token. `"role": "button"` costs five tokens to say one thing. A tree is thousands of
nodes saying the same eight things, which is the worst possible case for a format that names a
field every time it uses one.

## What changes

### The tree comes back rendered

```
# id role "name" !states [actions] x,y wxh +offscreen
0 window "Conferma" !modal 0,0 1920x1038
  0/0 panel 0,32 1920x1006
    0/0/0 menubar 0,32 1920x28
      0/0/0/0 menu "File" [click,select] 0,32 37x28 +5
      0/0/0/1 menu "Edit" [click,select] 37,32 39x28 +7
    0/0/1 button "Invia" [click,focus] 412,260 88x32
```

One line per node, one legend line at the top so the format explains itself to a reader who has
never seen it. Every field CR-007 kept is still here; only the syntax naming them is gone.

**Indentation stays.** It duplicates what the id already encodes, and it measured **free** — 555
tokens either way, because runs of spaces collapse into a token that would have been spent anyway.
Free readability is not a trade-off to agonise over.

### It travels inside the JSON, not instead of it

`stdout is JSON and nothing else` is the contract that lets an agent pipe this into a parser
unconditionally, and it is not worth trading. The rendering is a string field:

```json
{"tree": {"text": "# id role …\n0 window …", "node_count": 24, "truncated": false}}
```

Escaping the newlines costs 17% over raw text and still lands at **667 tokens against 1,707 — 39%**.
Almost all of the saving survives the contract, so there is no case for breaking it.

`root` is absent by default and returned by `--format json`, for a caller that wants objects. The
Python API is unaffected: it has had objects all along, and `TreeResult.root` stays the real thing.

### `windows` gets the same treatment

```
# id role "title" pid x,y wxh *active
0/29/0 window "Conferma" 4711 0,0 1920x1038 *
0/33/0 window "Posta" 5210 331,130 1152x784
```

Same reason, same shape, and it keeps the two reads looking like each other.

## Deliberately not done

**No `--format text` writing bare text to stdout.** That is the version that seems obvious and
costs the contract: an agent could no longer parse stdout without knowing which flags produced it,
and every error path would have to pick a format too. The measured price of keeping the contract is
112 tokens.

**No YAML, no TOML, no s-expressions.** They are JSON with different punctuation; the win here
comes from having no punctuation to name fields with, not from a different serialiser.

**No changes to the batch input format.** This is about what comes back, not what goes in. A batch
file is written by a program and read by a parser, and JSON is right for that.

## Documentation to update

- `product/features/ui-tree.md` — the rendering and its legend; `--format json`; the token
  measurements, because the whole rationale is quantitative.
- `product/features/cli.md` — `--format` on `tree` and `windows`.
- `product/features/skill.md` — the skill must teach reading the rendering, not the JSON.
- `system/interfaces.md` — `TreeResult.text`; `root` absent unless asked; the `windows` rendering;
  a restatement that stdout is still exactly one JSON object.
- `system/entities.md` — `TreeResult.text`; `WindowInfo` unchanged as a model.
- `system/architecture.md` — the renderer lives beside the rest of the reporting policy in
  `selectors.py`, or its own `render.py` if it grows past a screen.

## Agent Notes

- The legend is not decoration: it is what makes the format self-describing for a model that has
  never seen it, and it costs about twenty tokens once per call. Keep it on every rendering,
  including an empty one.
- A `name` containing a quote or a newline must not break a line. Escape minimally and only where
  it is ambiguous — a format that needs a parser has lost the argument it was making.
- The renderer takes an already-shaped tree: pruning, the budget, notable states and the off-screen
  summary all happen before it, exactly as they do now. It formats; it decides nothing.
- `truncated`, `node_count` and `reason` stay structured fields. They are read by code, they are
  three values rather than thousands, and burying them in prose would be the same mistake in the
  other direction.
