---
title: "Text is the output; JSON is the thing you ask for"
status: pending
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# Text is the output; JSON is the thing you ask for

## Why

`stdout is JSON and nothing else` was defended on the grounds that an agent can then parse it
unconditionally. That reasoning is sound in the abstract and wrong for this tool, and the numbers
are not close:

| Command | JSON | Text |
| --- | --- | --- |
| `screenshot` | **243 tokens** | **4** |
| `click --role button --name "Invia"` | **4,238** | **21** |
| `windows` | 363 | 128 |
| The envelope alone, contents removed | **177** | — |

Two hundred and forty-three tokens to say where a file is. Four thousand to say a button was
pressed, because the result echoes back the action that was just sent and the whole matched node.

**177 tokens of fixed overhead on every call**, spent on `profile` and `backend` (constant for a
session), `screen` (five numbers nobody reads per action), `ok` and `failed_index` (which the exit
code already carries), and the echoed action object with every null field written out.

The decisive argument is one the project already made and then ignored. [vision.md](../product/vision.md)
says these tools "are driven by another AI agent through a CLI"; a **Python API** exists underneath
for programs. So the CLI's consumer is a model — and the CLI was optimised for a machine parser
that has somewhere better to be. [CR-008](CR-008-render-the-tree-as-text.md) already found text
worth 3× on the tree and stopped at the envelope out of loyalty to a contract, when the envelope
was the more expensive half for every command except `tree`.

## What changes

**Text becomes the output. `--format json` becomes how you ask for the other thing.** The
`--human` flag from [CR-009](CR-009-a-view-for-the-person-running-it.md) disappears into the
default it should always have been.

```
$ use-computer screenshot
/home/you/.local/share/use-computer/screenshots/20260905T084235.481Z-screenshot.png

$ use-computer click --role button --name "Invia"
click button 'Invia' at 0/2/1/3 via the platform API — 12 ms

$ use-computer batch plan.json
1 focus text 'Destinatario' via the platform API — 8 ms
2 type "mario@example.com" — 240 ms
3 click button 'Invia' via the platform API — 12 ms
4 tree — 24 nodes, 1 truncated
```

`tree` and `windows` print what they already render. Nothing new has to be designed: this change is
mostly deletion.

### What the envelope carried, and where it goes

| Field | Now |
| --- | --- |
| `profile`, `backend` | `-v` on stderr, and `config show`. Constant for a session; not news. |
| `screen` | `--format json`, and the scale error already explains itself when it matters. |
| `ok`, `failed_index` | The exit code, and for a batch the line number that failed. |
| the echoed `action` | Gone. The caller sent it. |
| `matched`, `via`, `duration_ms` | The line. |

### What must not be lost

- **Exit codes are unchanged** and stay the primary signal: `0`, `1`, `2`.
- **Errors stay on stderr**, with their candidate lists and screenshot paths, exactly as today.
- **`--format json` returns the shape that exists now**, envelope included, for anyone piping to a
  program. It is one flag, not a compatibility mode with its own quirks.
- **The Python API does not change at all.** `Session.run` still returns a frozen `RunResult`; that
  is the interface for programs and always was.

## Deliberately not done

**No half-measure where text is the default only for reads.** `tree` and `windows` cheap, actions
still 4,000 tokens, would be the worst of both: an agent could not predict which shape it was
about to get, and the expensive case is the one that repeats in a loop.

**No machine-readable text.** No key=value, no delimiters chosen for splitting. The moment the text
is designed to be parsed it starts growing punctuation again, and `--format json` already exists
for anyone who wants to parse.

**No dropping `--format json`.** The unconditional-parse argument was not wrong, only outvoted. It
stays available and stays exactly one flag away.

## Documentation to update

- `product/features/cli.md` — the output contract inverts. This is the file that says "stdout is
  JSON and nothing else"; it now says text, with JSON one flag away, and says why.
- `product/features/ui-tree.md` — `tree` and `windows` print their rendering; `--format json` for
  objects.
- `product/features/actions.md` — what one action prints.
- `product/features/batch-execution.md` — what a batch prints, and how a failure reads.
- `product/features/skill.md` — the skill must stop telling the agent to parse stdout, which is the
  first thing it currently says.
- `product/vision.md` — one line, because "emits JSON on stdout" appears in the opening
  description of both halves of the pair.
- `system/interfaces.md` — the output contract, per-command text, and the JSON shape under the
  flag.
- `system/architecture.md` — the text views live in `render.py`; the CLI stops reaching for
  `as_json` by default.

## Agent Notes

- Delete `--human` rather than aliasing it. It shipped one commit ago, nobody depends on it, and a
  flag that silently does nothing is worse than one that errors.
- A line must never be a truncated JSON object. If a field cannot be said in prose it belongs in
  `--format json`, not abbreviated into the line.
- Every value printed still goes through the escaping from
  [BUG-004](../bugs/BUG-004-rich-eats-the-extra-name-from-the-error.md). More text through the
  formatter means more chances to reintroduce it.
- Keep the JSON tests. They now cover a flag rather than the default, and they are the only thing
  that will notice if `--format json` quietly rots once nothing exercises it by default.
