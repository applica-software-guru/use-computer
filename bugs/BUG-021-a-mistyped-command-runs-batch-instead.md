---
title: "A mistyped command runs `batch` instead of saying it does not exist"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-23T00:00:00.000Z"
---

# A mistyped command runs `batch` instead of saying it does not exist

## What happens

```
$ use-computer bad-command --help
Usage: use-computer batch [OPTIONS] {PATH|-}

 Run a batch of actions over one connection.
...
```

`--help` for a command that does not exist shows help for `batch` — not an error, not a mention of
`bad-command` anywhere, exit code 0. Without `--help` it is just as wrong, only less visible:

```
$ use-computer bad-command
error: cannot read bad-command: [Errno 2] No such file or directory: 'bad-command'
```

The message names the literal string typed, so it can be decoded with enough context, but nothing
in it says "no such command" — the one thing that is actually true.

## Why

`apply_default_command` (`cli.py`) rewrites `argv` before typer ever sees it, so that a bare
argument such as `use-computer actions.json` reaches `batch` without naming it. The rewrite fired
whenever the first argument was not already a known command and did not start with `-`:

```python
if first in _COMMANDS or first.startswith("-") and first != "-":
    return argv
return [argv[0], DEFAULT_COMMAND, *argv[1:]]
```

That condition cannot tell a mistyped command from an intended batch source, because both are just
a bare word with no leading dash. Every typo of every command name -- `scrren`, `bda-command`,
`clcik` -- satisfied it and was rewritten into `batch <that word>`, so it ran (or showed the help
of) an entirely different command than the one asked for, with no indication that a rewrite had
happened at all.

## Expected

Rewriting to `batch` only when the argument actually looks like a batch source -- `-`, or a path
that exists -- and leaving everything else alone. An unrecognised word then reaches typer's normal
command dispatch and gets typer's normal answer: `No such command 'bad-command'.`, exit 2. The
trade is a batch file that does not exist yet: it now gets the same "no such command" instead of a
file-not-found, since nothing in the bare word itself says which mistake it is, and "no such
command" is the more common one to make by a wide margin.
