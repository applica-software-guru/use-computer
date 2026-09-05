---
title: "A view for the person running it"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# A view for the person running it

## Why

Everything so far was built for the agent, correctly. But a person types these commands too — to
set the tool up, to check a profile, to find out why a click went nowhere — and what they get is
this:

```
$ use-computer windows
{"profile": "local", "backend": "local", "screen": {"width": 1920, ... "windows": {"text": "# id role \"title\" pid x,y wxh *active\n0/19/0 window ...
```

The information is all there, and it is unreadable. The tool's own answer to "how do I look at
this?" is currently `| jq -r '.results[0].windows.text'`, which nobody should have to know, and
which is different for every command.

That matters beyond comfort. The first thing anyone does with this tool is run it by hand to see
whether it works at all, and that first impression is a wall of JSON with the useful part escaped
inside it.

## What changes

### `--human`

An explicit flag, on every command, that prints for a reader instead of a parser:

```
$ use-computer windows --human
id       role    title                                       pid    box                active
0/19/0   window                                              2067   0,0 1921x1080      *
0/26/0   window  Desktop                                     2121   0,0 1920x1038
0/29/0   window  ◐ Persona core text to speech ordinamento…  2379   0,0 1920x1038
```

```
$ use-computer click --role button --name "Invia" --human
clicked button 'Invia' at 0/2/1/3 — via the platform API, in 12 ms
```

```
$ use-computer click --role button --human
error: 7 nodes match role=button; narrow the selector or pass --nth
  0/0/0/0  menu  'File'      at (0, 32)
  0/0/0/1  menu  'Edit'      at (37, 32)
```

For `tree` it prints the rendering [CR-008](CR-008-render-the-tree-as-text.md) already produces,
with no JSON around it — which is the whole point: that text was always the readable form, it was
just wrapped in an envelope addressed to somebody else.

### The contract is unchanged, and that is the point

**`--human` is the only way to get anything but JSON on stdout.** Without it, every invocation
still prints exactly one JSON object, whatever happens. An agent never passes the flag, so nothing
an agent sees changes at all.

### Not auto-detected from the terminal

Deciding by `isatty()` is the obvious design and it is wrong here. Agents run commands under a pty
often enough — Claude Code among them — that the tool would silently switch formats on the caller
least able to cope with it, and the failure would be a parse error far from its cause. A flag is
explicit, greppable in a transcript, and cannot surprise anyone.

## Deliberately not done

**No `--format human`.** `--format` on `tree` and `windows` chooses how the *data* is shaped inside
the JSON. This chooses whether there is JSON at all. Overloading one flag with both would make
`--format json --human` a question with no good answer.

**No colour or tables beyond alignment.** rich is available and is exactly the wrong instinct here:
this output is read in terminals, pipes, and CI logs. Aligned columns survive all three; boxes and
colours survive the first. The project has already been bitten by rich twice — the newline inside a
JSON string, and `[tree]` eaten as markup — and both times the lesson was to hand it less, not
more.

**No `--human` on `batch`.** A batch is written by a program for a program. Printing prose for
twelve actions is a report nobody asked for; `--human` there prints the same one-line-per-action
summary and nothing cleverer.

## Documentation to update

- `product/features/cli.md` — `--human` as a global flag; a restatement that stdout is JSON in
  every invocation that does not ask otherwise.
- `product/features/ui-tree.md` — `--human` prints the rendering bare.
- `product/features/skill.md` — one line saying the skill must **not** teach `--human`: it exists
  for people, and an agent that used it would break its own parsing.
- `system/interfaces.md` — the flag, what each command prints under it, and the unchanged contract.
- `system/architecture.md` — where the human formatting lives, next to `render.py`.

## Agent Notes

- Exit codes do not change. `--human` changes what is written, never what is meant.
- Errors under `--human` go to **stderr** as they already do, and stdout gets nothing. A reader
  scrolling back should not have to work out which stream said what.
- The one-line action summary should name what an agent would have read: the matched node, the rung
  taken, the duration. It is a rendering of `ActionResult`, not a second source of truth.
- A name printed here is data and goes through the same escaping as everywhere else. That bug has
  been fixed once; it must not come back through a new print site.
