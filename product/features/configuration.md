---
title: "Configuration"
status: synced
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
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
