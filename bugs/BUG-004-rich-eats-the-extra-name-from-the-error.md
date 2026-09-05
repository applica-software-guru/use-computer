---
title: "rich eats the extra name out of the error that exists to name it"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# rich eats the extra name out of the error that exists to name it

## What happens

The same error, printed twice by the same run. In the JSON, correct:

```
"message": "reading the UI tree needs 'gi', which is not installed.
            Install it with: pip install \"use-computer-cli[tree]\" ..."
```

On stderr, where a human reads it:

```
UITreeUnavailableError: reading the UI tree needs 'gi', which is not installed.
Install it with: pip install "use-computer-cli" On this platform you also need ...
```

`[tree]` is gone. The message whose entire job is to name the extra to install does not name it,
and what is left is a command that installs the wrong thing without complaining.

## Why

Every diagnostic goes through `rich`, which parses `[...]` as markup. `[tree]`, `[local]`, `[vnc]`
are all valid-looking tags, so rich consumes them. Nothing errors; the text just quietly loses the
part that mattered.

This is the sibling of a rule the project already wrote down: *JSON is printed with plain
`json.dumps`, never through rich.* The same reasoning was never applied to error text, and error
text is where an extra name lives.

Any interpolated value can trigger it, not just extras: a window titled `[draft] Report` or a
button named `[x]` loses its brackets in the candidate list of an `AmbiguousNodeError` — which is
the list an agent uses to choose between them.

## What it should do

Escape every dynamic value before it reaches rich. Styling is ours and stays markup; messages,
names, titles and paths are data and must be printed literally.

## Agent Notes

Fix it at the boundary rather than at each of the two dozen call sites, or the next `_err.print`
reintroduces it. A test should assert on a message that *contains* brackets, since one that does
not proves nothing.
