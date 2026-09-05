---
title: "Configuration"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "2.0"
---

# Configuration

Configuration is what makes adding a backend target an edit rather than a code change — and
`config show` is what makes a misconfiguration debuggable in one command.

## Project root

The project root is discovered by **walking up from the current directory the way git finds its
own**: the first ancestor containing a `.use-computer` directory wins. That directory holds:

- `config.toml` — **committed**. Profiles and settings.
- `.env` — **gitignored**. Secrets: VNC passwords, hosts that are not public.

When no project root is found, XDG fallbacks apply: the XDG **config** directory for
`config.toml` and the XDG **data** directory for anything stored. Never a cache directory —
configuration is not disposable.

## Creating one: `config init`

The only way to get a config should not be to already know how to write one.

```bash
use-computer config init                                       # asks
use-computer config init --backend vnc --host 10.0.0.5         # doesn't
use-computer config init --backend local --allow-local
```

**Interactive**, when stdin is a TTY. The questions go to stderr, so the output contract is
untouched: which backend; for `vnc` the host and port, then optionally a password entered hidden;
for `local` the opt-in **asked out loud**, because that backend moves this machine's pointer, and
declining aborts rather than writing a profile that cannot run; finally the profile name,
defaulting to the backend name.

**Non-interactive**, from flags, so an agent can do it and so it scripts. Flags win over
prompting: given `--backend`, nothing is asked. Missing required information — `vnc` with no host,
`local` without `--allow-local` — is a usage error, not a prompt on a pipe. There is deliberately
no `--password` flag, because a password on a command line lands in shell history; interactive
setup prompts for it, and otherwise the command reports the environment variable to set.

**Then it probes.** After writing, `init` opens the backend it just configured, asks for the
screen, and reports the geometry and the scale. A scale that cannot be derived is the most
expensive failure this tool has — every click lands in the wrong place and nothing about it looks
like a scaling bug — so setup is where it should surface, not the first click. `--no-probe` skips
it.

It refuses to overwrite an existing config without `--force`, and `--dir` chooses where
`.use-computer` is created. Adding a profile to an existing config is a manual edit: `init`
creates a config, it does not merge into one.

## Named profiles

```toml
default-profile = "laptop"
delay = 0.1

[profiles.laptop]
backend = "local"
allow-local = true

[profiles.staging]
backend = "vnc"
host = "10.0.0.5"
port = 5900
```

A profile is selected with `--use`, falling back to `default-profile`.

## Where screenshots go

`screenshot-dir` sets the directory screenshots are written to when no explicit path was given. It
resolves through the same layers as everything else and defaults to **`.use-computer/screens/`**
when a project root exists, and to the XDG **data** directory otherwise — never a cache directory,
because a screenshot of somebody's desktop is not disposable.

Beside the work that produced them: easy to open, easy to throw away, and separate from another
project's. Under `.use-computer/` rather than a second hidden directory at the root, because the
tool already owns that one — it sits next to `config.toml` and `.env`, where somebody already looks
for this tool's things.

**This used to be forbidden, for a reason that has not gone away.** A capture is the whole desktop —
open conversations, mail, whatever is on the screen — and in a working tree one `git add -A`
commits it. So the answer travels with the setting rather than being left as a warning:
`.use-computer/.gitignore` is written when the directory is created, containing `.env` and
`screens/`. It also closes a gap that predates all of this — `.env` has been *described* as
gitignored since the beginning and nothing ever made it so.

The tool never touches a `.gitignore` outside its own directory, and never overwrites one that
already exists. Editing the project's is the user's business, not a side effect of taking a
picture.

Files are named by capture time and action, `20260904T103012.481Z-click.png`, so they sort and do
not collide.

## Getting rid of them

```bash
use-computer prune                # remove them
use-computer prune --dry-run      # say what would go, remove nothing
use-computer prune --keep 20      # leave the most recent 20
```

```
removed 34 screenshots (12.4 MB) from /work/.use-computer/screens, left 1 file this tool did not write
```

**It removes only files it recognises as its own** — the timestamped names it writes — and never
the directory itself. That is the whole safety of the command: `screenshot-dir` is configurable,
and the first person to point it at their Pictures folder must not lose anything. Anything else in
there is counted out loud, because silence would look like it had been deleted.

`--keep N` keeps the most recent N by the timestamp **in the name**, not by the filesystem: the
name is the record, which is why it was made to sort.

There is deliberately **no automatic pruning**. A cap that quietly deleted the screenshot an agent
was about to read would be a worse bug than a directory that grows.

**The directory is named once per run, not once per file.** A path is 23 tokens, and a batch of
five verified actions would repeat the same directory in every one of them — 70 tokens of it, five
times what the whole closing line costs. So when a run wrote more than one screenshot to the same
place, the action lines carry filenames and the closing line says where they are. One file keeps
its whole path: there is nothing to save, and an indirection to read would cost more than it
returns.

## Reading the tree

Three settings bound what `tree` returns, resolved through the same layers as everything else:

| Key | Default | Meaning |
| --- | --- | --- |
| `tree-max-nodes` | `400` | The node budget. Beyond it the tree is truncated and says so. |
| `tree-depth` | `20` | Maximum depth from the scope root. |
| `tree-max-text` | `200` | Longest `name` or `value` a node reports. |
| `tree-fallback` | `true` | Capture a screenshot when the tree cannot answer. |

These exist for the same reason base64 screenshots were removed: a tree poured into an agent's
context is expensive and looks useful.

None of these is what made the tree affordable, though. **The shape did**: a terser node, and
counting what is off screen instead of expanding it, took one measured window from 19,752 bytes to
3,777. A budget bounds the worst case; it does not make the ordinary case cheap.

**Two budgets, because nodes are the wrong unit on their own.** A terminal or an editor reports its
entire buffer as one node's `value` — thirteen kilobytes from a single node defeats a budget of
four hundred. `tree-max-text` bounds what each node carries; `tree-max-nodes` bounds how many there
are. A `name` and a `value` identify an element, they are not a way to read its contents.

## Precedence

Highest to lowest:

1. CLI flags
2. Environment variables (`USE_COMPUTER_` prefix)
3. `.env` files
4. The selected profile
5. Top-level config keys
6. The global (XDG) config
7. Field defaults

## `config show`

Prints **every resolved value and the layer it came from**, naming the exact environment variable
that would override it, and **masking secrets**. It warns on stderr about unknown keys —
**including keys inside profiles that are not selected**, because a typo in an unused profile is
exactly the kind of thing that is discovered at the worst moment.

## Agent Notes

- Settings are a pydantic-settings model under the `USE_COMPUTER` env prefix.
- The layer of each value must be tracked as data, not reconstructed for display — `config show`
  reports what the resolution actually did.
