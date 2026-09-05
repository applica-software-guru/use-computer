---
title: "A GLib warning from AT-SPI leaks onto stderr on every run"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# A GLib warning from AT-SPI leaks onto stderr on every run

## What happens

Every command that reads the tree prints this first:

```
(process:355108): dbind-WARNING **: 10:54:37.469: AT-SPI: Unable to open bus connection:
Failed to connect to socket /run/user/1000/at-spi2-04OAV3/socket: No such file or directory
```

Then it works perfectly. The socket in the message is stale; the library falls back and connects.

## Why

The warning comes from GLib inside the C library, not from Python, so it bypasses everything the
CLI does with its own diagnostics. `stderr` is supposed to carry *our* diagnostics; this is a
third-party library talking over them about a condition it has already recovered from.

It is not cosmetic. An agent reading stderr to understand a failure sees a scary message about a
missing socket immediately before output that is entirely fine, which is exactly the sort of thing
that turns into a wrong conclusion and a retry.

## What it should do

Silence the `dbind` domain while the provider is being constructed, and let a real failure surface
as `UITreeUnavailableError` — which already says what to do about it.

## Agent Notes

Install a GLib log handler rather than redirecting file descriptor 2: redirection would also
swallow anything else written during that window, including our own errors.
