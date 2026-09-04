---
title: "Configuration"
status: synced
author: ""
last-modified: "2026-09-04T00:00:00.000Z"
version: "1.2"
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
resolves through the same layers as everything else and defaults to the XDG **data** directory,
`use-computer/screenshots` — never a cache directory, and never inside the repository, because a
screenshot of somebody's desktop is not something to leave lying in a working tree.

Files are named by capture time and action, `20260904T103012.481Z-click.png`, so they sort and do
not collide. They are not pruned.

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
