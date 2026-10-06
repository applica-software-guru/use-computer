---
title: "A secret the agent passes without reading"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-10-06T00:00:00.000Z"
---

# A secret the agent passes without reading

## Why

`type --secret` sends a credential through the keyboard, and the keyboard goes wherever focus is.
In a browser driven by Playwright that is the wrong channel: the page is often not the frontmost
window, focus moves under the agent while forty keystrokes are being synthesised, and Playwright
already has a way to fill a field by selector that needs no focus at all — it just needs the value.

CR-021 refused `secret get` on the grounds that a command printing a secret would be called by the
first agent that wanted to check its work. CR-022 then said, correctly, what the store is and is
not worth: **it does not stop a process running as you**, which can run `type --secret` into any
text field and read the value back. So `get` adds nothing to what a local process can already do.
The only thing it changes is the risk that the value lands in the **agent's context** — and that
risk is held by how the command is used, which is the skill's job, exactly as it already holds the
`tree`/screenshot leak after a `type --secret`.

The invariant is therefore restated around what it was always protecting:

> A secret never enters the agent's context.

It leaves the store into the keyboard, or into another command's argument through shell
substitution — never into output the agent reads.

## What changes

### The command

```
use-computer secret get NAME
```

Prints the value to stdout, **with no trailing newline** and nothing else, so it composes:

```
playwright-cli fill e12 "$(use-computer secret get gh-token)"
```

The shell expands the substitution; the agent composes and sees the command, never the value.

- Resolution is the same as `--secret`: environment, then project store, then global store.
- A missing name is the same `SecretNotFoundError`, exit `1`, with the same message — ask the user
  to run `secret set`, do not ask for the value.
- An unreadable value is the same `SecretUnreadableError`.
- The value is written raw to stdout, never through rich, so nothing wraps it or eats brackets.

`type --secret` and `set-value --secret` stay as they are: for a native window with focus they are
still the channel that keeps the value off the command line entirely.

### What the skill teaches

Rule 4 ("there is no way to read one back") is replaced by:

- **`secret get` only ever runs inside `$(...)`, as an argument to the command that uses it.**
  Never on its own, never piped into something that prints, never echoed "to check". Its stdout
  is the value; a bare `secret get` puts the password in this conversation.
- **The receiving command's output is your context too.** If the tool echoes its arguments, logs
  the code it ran, or returns a snapshot that includes the field's value, the secret comes back
  that way. After filling a secret, do not snapshot or screenshot that field — the same rule as
  after `type --secret`.
- **Prefer `type --secret` / `set-value --secret` when focus is reliable;** use `secret get` when
  another tool fills the field by selector (a browser driven by Playwright).

Rules 1–3 are unchanged and stay first.

## Agent Notes

- `secret get` resolves through `Secrets().require(name)` — no new path into the store.
- Write with `sys.stdout.write(value.get_secret_value())` and flush; no newline, so a pipe receives
  the exact bytes and `$(...)` needs nothing stripped.
- Replace the test asserting `secret get` is absent with tests for: the value printed exactly, the
  environment overriding the stores, the missing-name error and its exit code.
- The comment heading the secrets group in `cli.py` and the module docstring in `secrets.py` state
  the old invariant; restate both.
- Docs this touches: `product/features/safety.md` (the invariant restated, why `get` adds no
  attack surface, where the risk now lives), `product/features/cli.md` and
  `product/features/configuration.md` (the command, and the "no `secret get`" sentences removed),
  `product/features/skill.md` (the replaced rule), and `system/interfaces.md` (CLI surface, the
  `secret` section).
