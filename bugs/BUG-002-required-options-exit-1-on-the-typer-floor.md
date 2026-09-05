---
title: "A missing required option exits 1 with a traceback on the supported typer floor"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# A missing required option exits 1 with a traceback on the supported typer floor

## What happens

On **typer 0.16.0**, the declared floor, an option declared required is not enforced. It arrives as
`None`, reaches the pydantic model, and raises:

```
$ use-computer type          # no --text
exit=1, a traceback on stderr
$ use-computer drag          # no coordinates
exit=1
$ use-computer scroll        # no --amount
exit=1
```

The contract says `0` success, `1` failure, `2` bad usage. A missing option is bad usage, and an
agent that branches on the exit code is told the action failed rather than that the call was wrong
— so it will retry it.

Found by the TestPyPI rehearsal, on the matrix leg that exists for exactly this. Locally, with a
newer typer, all three are correct: this is only visible at the floor.

## Why

typer enforces required options differently across the supported range. The CLI leaned on that
enforcement, so the behaviour follows whichever typer is installed — which is the same class of
problem as the undeclared `click` import: relying on a dependency's behaviour without testing the
version that is actually supported.

## What it should do

Not depend on typer for it. Declare the option optional, check it, and exit `2` with a message
naming the flag — the pattern the element commands already use for their selector.

## Agent Notes

Cover it with tests that run in the matrix, not only locally: the whole point is that the floor
behaves differently, and a test that only ever sees the newest typer proves nothing here.
