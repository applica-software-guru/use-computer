---
title: "Safety"
status: synced
author: ""
last-modified: "2026-09-17T00:00:00.000Z"
version: "1.5"
---

# Safety

`use-computer` types real keystrokes and moves a real pointer. On the local backend it does so on
the machine the user is sitting at. Safety here is not a policy layer; it is how the tool is built.

## Dry run

`--dry-run` resolves and logs every action — profile selection, coordinate scaling, key
normalisation — without performing any of it. Results are returned with `performed: false`, so an
agent can rehearse a whole batch and inspect exactly what would happen.

## Pacing

- **Per-action delays** so the application under control can react.
- **A typing rate applications do not drop characters from.** Typing a string as fast as the API
  allows loses characters in real applications; the rate is deliberate and configurable.

## Explicit opt-in for local

The `local` backend controls the user's own machine. It refuses to act unless it has been enabled
explicitly — a setting in the profile or an environment variable, never a silent default. A local
profile without the opt-in fails with an error explaining exactly what to set.

`config init` asks for that opt-in **out loud** rather than writing it into a file on the user's
behalf, and declining aborts the setup instead of producing a profile that cannot run. An opt-in
nobody was asked for is not an opt-in.

## Secrets

Half of what this tool is asked to automate ends at a login form, and the only way through one used
to be `type --text 'hunter2'`. That single line puts the password in the agent's context, in the
transcript that context is written to, in the shell history, and — on the result line that comes
back — in the agent's context a second time. Three of those four outlive the session.

So secrets are not a storage feature. They are **one invariant**:

> A secret leaves the store into the keyboard, and never into stdout.

The value is put there out of band by the person at the machine, and from then on it is referred to
by name: `type --secret gh-token`. The agent composes the command, the tool reads the value, the
keyboard receives it, and nothing in between is ever printed. See
[configuration.md](configuration.md) for where the store lives.

**There is no command that prints a secret, and its absence is the design.** A `secret get` would be
called by the first agent that wanted to check its work, and the invariant would be gone. If a value
needs to leave the store, it leaves through the keyboard.

### Encrypted at rest, and what that is worth

The stored values are encrypted, with the key in the XDG **data** directory while the ciphertext
sits in the XDG **config** directory. The separation is the substance of it.

**It does not stop a process running as you.** That process can read the key file, and it does not
need to: it can run `use-computer type --secret gh-token` and read the credential out of a text
field. No local encryption fixes that, because whatever types the secret must be able to decrypt it.
Any claim otherwise is a claim that the key is somewhere the program cannot reach.

**It stops accidental disclosure**, which is how credentials actually leak — a `~/.config`
synchronised to a service or committed to a dotfiles repository, a config file pasted into an issue
or a support thread, a `cat` with somebody watching, a disk image handed to somebody else. That is a
real and ordinary failure and it is worth closing.

Both sentences are in the documentation on purpose. "Encrypted" is a word a reader completes with
their own threat model, and the one they supply is usually wider than the one that holds.

### What this protects, and what it does not

`--secret` protects the keystroke. It does not protect the screen, and the difference is the part
that has to be taught rather than built:

- **The result line** would have printed the text — `_payload` renders every `type` with its
  content, deliberately, because a line that omits what was done is useless when the screen and the
  agent's model disagree. With `--secret` the line carries the character count and the secret's
  **name**, never the value.
- **The tree reports the value back.** A node carries its `value`, clamped to `tree-max-text`. A
  token typed into a field that is not a password field is in the next `tree` the agent runs.
- **The screenshot has it in pixels**, with no clamp.

`--verify` is the sharpest edge of that last one: it captures before and after *every* action
without being asked per action, so an agent turning on verification to check its work would arrange
for a picture of the credential to arrive in its context. And there is no flag that turns
verification off once configuration has turned it on.

So **an action carrying a secret is never verified.** Not a default — a property of the action. The
report it would produce is "some pixels moved", which a login already tells you, and it produces it
by photographing the field. The line says `not verified (secret)` where the change report would
have been, because silence there would read as *unchanged*, and a safety decision that leaves no
trace in the output is the one thing this tool does not do.

The other two are not defects and are not fixed here. `tree` and `screenshot` answer truthfully about what is
on the screen, and after a successful `--secret` the screen is where the secret is. Refusing to
answer would make them useless for the ninety-nine cases that have nothing to do with a credential.
They are the reason the bundled skill teaches the mechanism and not merely the flag — see
[skill.md](skill.md).

## Element actions are still real actions

Operating an element through the accessibility API moves no pointer, which makes it *quieter* than
a click, not safer:

- `--dry-run` still **resolves** the selector and reports the node it would have acted on and the
  rung it would have taken. A dry run that skips resolution tells the agent nothing it did not
  already know.
- **`focus` is a side effect.** It takes focus from whatever the user was doing, and on the local
  backend that is their real desktop. No action quietly focuses an element first to make itself
  work; if a toolkit requires focus, the error says so.
- On macOS the accessibility API will act on an application that is **not frontmost**. That is a
  genuine advantage and a genuine footgun: nothing visibly comes forward when it happens.

## The one command that deletes

`prune` removes screenshots, so it is the only command here that destroys anything. It is safe by
construction rather than by warning:

- it removes only files matching the **names this tool writes**, never everything in the directory;
- it never removes the directory itself;
- it counts what it left alone, out loud, because silence would look like deletion;
- `--dry-run` says what would go and removes nothing, like everywhere else.

There is no flag that makes it delete something it does not recognise. `screenshot-dir` is
configurable, and a `prune` that emptied whatever it pointed at would be a footgun the first time
somebody aimed it at their Pictures folder.

## Permission errors

Reading the tree needs the same Accessibility permission on macOS that input synthesis does, and on
Linux it needs the accessibility bus running: GTK applications expose nothing over AT-SPI when
`org.a11y.Bus` is absent. An empty tree that actually means "you have it switched off" is the worst
possible answer, so that case is an error naming what to enable, never an empty result.

macOS gates input synthesis behind Accessibility and screen capture behind Screen Recording. When
the permission is missing, the underlying libraries typically do nothing at all — a click that
never happens and never errors. `use-computer` detects the denial and raises a clear error naming
the permission and where to grant it, rather than reporting success for an action that did not
occur.

## Agent Notes

Every safety behaviour is observable in the JSON result: `performed`, the resolved coordinates, the
delay applied. Never make a safety decision that leaves no trace in the output.
