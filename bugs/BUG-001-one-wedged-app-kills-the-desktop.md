---
title: "One unresponsive application kills the whole desktop snapshot"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# One unresponsive application kills the whole desktop snapshot

## What happens

`tree --window all` fails intermittently — roughly one run in three on a busy desktop:

```
UITreeUnavailableError: AT-SPI did not answer: atspi_error: timeout from dbind (1).
```

The traceback shows it raised inside `_build`, reading `get_role_name()` on one child.

## Why

`_root_for` already recovers per application: an application that will not answer is skipped, and
the desktop survives. `_build` has no such guard. AT-SPI is D-Bus and every property read is a
round trip, so a single wedged client — and there is one on this desktop, evidenced by the stale
`at-spi2-.../socket` warning — takes down a snapshot of everything.

The bounded call timeout from the previous change turned "hangs for 15 seconds" into "fails in
2.5 seconds", which is better and still wrong: the answer should be eleven applications and a note,
not an exception.

## What it should do

Skip the subtree that will not answer, exactly as `_root_for` skips the application that will not
answer, and return everything else. Losing one application is a much smaller loss than losing the
desktop — and the caller cannot tell the difference between "not there" and "did not answer"
today, which is the worse failure.

## Agent Notes

The guard belongs on each child in `_build`, not around the whole traversal: wrapping the
traversal would still lose every sibling after the first failure.
