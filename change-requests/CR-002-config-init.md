---
title: "Add a guided setup: config init"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-03T00:00:00.000Z"
---

# Add a guided setup: `config init`

## Why

Today the only way to get a config is to already know how to write one. That is a bad first
contact for a project whose whole claim is that adding a backend target is configuration rather
than code — the configuration is the feature, and it has no on-ramp.

There is a second reason, specific to this tool. The most expensive failure here is a coordinate
space whose ratio cannot be derived: every click lands in the wrong place and nothing about the
failure looks like a scaling bug. Setup is the right moment to discover that, not the first click.

## What to add

A `use-computer config init` command that writes `.use-computer/config.toml` and then proves it
works.

### Interactive, when stdin is a TTY

Questions on stderr, so the output contract is untouched:

1. Which backend — `local` or `vnc`.
2. For `vnc`: host, and port (default 5900). Then, optionally, a password, entered hidden and
   written to `.use-computer/.env` — never to the committed TOML.
3. For `local`: the opt-in is **asked out loud** — this backend moves this machine's pointer and
   types on its keyboard. Declining aborts rather than writing a profile that cannot run.
4. The profile name, defaulting to the backend name.

### Non-interactive, from flags

`config init --backend vnc --host 10.0.0.5 --profile staging` so an agent can do it too, and so it
scripts. Flags win over prompting: if `--backend` is given, nothing is asked. Missing required
information — `vnc` with no host, `local` without `--allow-local` — is a usage error (exit 2), not
a prompt on a pipe.

There is deliberately no `--password` flag: a password on a command line lands in shell history.
Interactive setup prompts for it; otherwise the command reports the environment variable to set.

### Then it probes

After writing, the command opens the backend it just configured, asks for the screen, and reports
the geometry and the scale. A scale that cannot be derived is reported as the failure it is, at
setup, with the file already written so it can be corrected by hand.

`--no-probe` skips it.

### Rules

- Refuses to overwrite an existing config without `--force`, like `skill install` already does.
- `--dir` chooses where `.use-computer` is created; the default is the current directory.
- Adding a profile to an existing config stays a manual edit for now — `init` creates a config,
  it does not merge into one.

### Output

JSON on stdout as always: the config file written, the .env file if one was written, the profile,
the backend, and the probe result. Exit `0` when the config was written and the probe succeeded
(or was skipped), `1` when the probe failed, `2` on bad usage.

## Documentation to update

- `product/features/configuration.md` — the command, both modes, the refusal, and the probe.
- `product/features/cli.md` — the command list.
- `product/features/safety.md` — the local opt-in is asked out loud, not written silently.
- `system/interfaces.md` — the CLI contract and the init payload.

## Agent Notes

Prompts belong in the CLI layer; writing the file belongs in the config layer. Nothing about this
command may print to stdout except the final JSON object.
