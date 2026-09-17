---
title: "A secret the agent never reads"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-17T00:00:00.000Z"
---

# A secret the agent never reads

## Why

Half of what this tool is asked to automate ends at a login form. Today the only way through one
is:

```
use-computer type --text 'hunter2'
```

That single line puts the password in four places at once: the agent's context, the transcript the
agent's context is written to, the shell history, and — on the result line that comes back — the
agent's context a second time. Three of those four outlive the session. None of them was asked for.

So the feature is not "store a password". It is **one invariant**:

> A secret leaves the store into the keyboard, and never into stdout.

Everything below is either that invariant or a place the current code breaks it.

## Where the current code breaks it

Two of these are ours to fix. The third cannot be fixed, only taught — and leaving it untaught is
what would make this feature dangerous, because a feature named `--secret` is read as a promise.

**1. The result line prints the text.** `_payload` in `cli.py` renders every `type` as
`40 chars 'ghp_xxxxxxxxxxxx'`. That is the line the agent reads, on every action, by design —
CR-017 put the text there on purpose and was right to. It is also the exact place a secret would
surface, one line after being typed.

**2. The tree reports the value back.** A node carries its `value`, clamped to `tree-max-text`
(200 characters by default). A token typed into a field that is not a password field is in the
next `tree` the agent runs. The tool did not leak it; the tool handed it back when asked what is
on screen.

**3. The screenshot has it in pixels.** Same field, same problem, no clamp — and `--verify`
captures *before and after every action* without being asked per-action. An agent that turns on
verification to check its work has arranged for a picture of the secret to arrive in its context.

(2) and (3) are not bugs and have no fix inside this change: `tree` and `screenshot` answer
truthfully about what is on the screen, and the screen is where the secret now is. They are the
reason this CR changes the skill as much as it changes the CLI.

## What changes

### The store

```
use-computer secret set NAME      # reads the value from stdin, never from argv
use-computer secret list          # names only
use-computer secret rm NAME
```

`secret set` reads from a TTY with a hidden prompt, and from a pipe as a single line. **Never from
an argument**: an argument is visible in `ps` for the life of the process and is written to the
shell history verbatim.

`secret list` prints names, where each one is stored and when it was set. It never prints a value,
not even clamped, not even with a flag.

**There is no `secret get`, and its absence is the design.** A command that prints a secret to
stdout is a command an agent will call, and the invariant would be gone the first time one did. If
the value needs to leave the store, it leaves through the keyboard.

Storage is a `0600` file — `secrets.toml` in the XDG config directory by default, because a
credential is a fact about the person at the machine and not about the repository, and because a
file outside the working tree cannot be committed by accident. `--project` writes it to
`.use-computer/secrets.toml` instead, which is added to the `.gitignore` this tool already writes
into its own directory. `--secret NAME` resolves project-first, then global, the way every other
setting already layers.

For a machine with nobody sitting at it, `USE_COMPUTER_SECRET_<NAME>` supplies the value from the
environment. It reads at the same precedence as the rest of the `env` layer and is never written
anywhere.

### Using one

```
use-computer type --secret gh-token
use-computer set-value --id 0/0/3/1 --secret gh-token
```

`--secret` and `--text`/`--value` are mutually exclusive; giving both is a usage error rather than
a silent precedence rule. In a batch, the same action carries `"secret": "gh-token"` in place of
`"text"`.

`set-value` matters here as much as `type` does: putting a credential into a field through the
accessibility API is both quieter and more reliable than synthesising forty keystrokes into a
form that may steal focus halfway through.

### What the line says

```
type 40 chars (secret gh-token) — 812 ms
```

The character count stays, because the count is what catches a truncated or a doubled paste and
CR-017 added it for that reason. The name stays, because an agent debugging a rejected login needs
to know *which* secret it sent. The value is not there and no flag puts it there.

### When it is missing

```
error: no secret named 'gh-token'. Ask the user to run `use-computer secret set gh-token`.
Do not ask them for the value here.
```

The second sentence is not decoration. The obvious repair for a missing secret — asking the user to
paste it into the conversation — is the precise failure this whole change exists to prevent, and it
is what a helpful agent does by default unless told otherwise.

`--dry-run` resolves whether the name **exists** and fails on a missing one. A rehearsal that
cannot catch a typo in a secret's name would be a rehearsal of the wrong batch.

## What the skill teaches

The skill gets a section on the mechanism, not a mention of the flag. Four things, in this order:

1. **Never run `secret set` yourself.** If the agent is holding the value, it was already in the
   agent's context and the store bought nothing. A missing secret is a full stop: say which name is
   missing and which command the user should run, then wait.
2. **Never ask for a password in the conversation.** Not to store it, not to confirm it, not to
   check it looks right.
3. **`--secret` protects the keystroke, not the screen.** Once typed into a field that is not
   masked, the value is in `tree` as a node value and in any screenshot of that window. After
   sending a secret: do not run `tree` on that window, do not take a screenshot of it, and know
   that `--verify` takes one on its own — turn it off for that action.
4. **There is no way to read a secret back.** No command prints one. An agent that cannot find such
   a command has found the design, not a gap.

Point 3 is the one worth the most words, because it is the counterintuitive half. Points 1 and 2
are the ones a smaller model will drop first, so they go first and stay imperative — CR-020's
finding, applied here.

## Agent Notes

- Carry the resolved value in `pydantic.SecretStr` inside `TypeAction` and `SetValueAction`.
  Pydantic is already a dependency, and `SecretStr` masks itself in `repr`, in logs and in a
  traceback — defence in depth, instead of auditing every present and future call site that might
  render an action.
- Put the store behind an interface with the file as its first implementation. The OS keychain
  (`security` on macOS, libsecret on Linux) is the better answer and a worse first step: three
  platforms, three behaviours, and a plaintext `0600` file is already exactly the posture this tool
  takes with the VNC password in `.env`.
- `secret set` must create its file with `0600` at creation, not chmod it afterwards. The gap
  between the two is a readable secret.
- Add `secrets.toml` to `GITIGNORE_LINES` in `config.py`, so the project store is covered the way
  `.env` and `screens/` already are.
- `config show` must not grow a secrets section. It prints resolved configuration, and the store is
  not configuration.
- Docs this touches: `product/features/safety.md` (the invariant and the three leaks),
  `product/features/actions.md` (`--secret` on `type` and `set-value`),
  `product/features/configuration.md` (where the store lives and how it layers),
  `product/features/batch-execution.md` (the `secret` key),
  `product/features/cli.md` (the `secret` command group),
  `product/features/skill.md` (what the skill teaches), and `system/interfaces.md` (CLI surface,
  batch input JSON, environment variables, and the missing-secret error).
