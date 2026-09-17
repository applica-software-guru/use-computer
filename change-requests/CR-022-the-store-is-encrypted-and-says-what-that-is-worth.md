---
title: "The store is encrypted, and says what that is worth"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-17T00:00:00.000Z"
---

# The store is encrypted, and says what that is worth

## Why

CR-021 stored credentials in `~/.config/use-computer/secrets.toml`, mode `0600`, in clear text, and
called that the same posture the tool already took with the VNC password in `.env`. That was true
and it was the wrong bar.

`~/.config/` is the directory people **synchronise**. It is versioned in a dotfiles repository,
pushed to Dropbox, copied to a new laptop, and pasted into a bug report when somebody asks what the
configuration looks like. A password sitting in clear text there does not leak because an attacker
broke something; it leaks because the file did exactly what that directory is for.

So the values are encrypted.

## What this is worth, and what it is not

This has to be said plainly or the feature becomes the thing CR-021 warned about — a promise read
wider than it is.

**It does not stop a process running as you.** That process can read the key file, and it does not
need to: it can run `use-computer type --secret gh-token` and watch the credential appear in a text
field. No local encryption can fix that, because the thing that types the secret must be able to
decrypt it. Anything claiming otherwise is claiming the key is somewhere the program cannot reach.

**It stops accidental disclosure**, which is how credentials actually leak:

- a `~/.config` synced to a service, or committed to a dotfiles repository;
- a configuration file pasted into an issue, a chat, or a support thread;
- a `cat` of the wrong file with somebody watching;
- a backup or a disk image handed to somebody else.

That is a real and common failure, and it is worth closing. The documentation says this in these
words rather than saying "encrypted" and letting the reader supply their own threat model.

## What changes

**The value is a Fernet token; the name is not.**

```toml
[secrets.gh-token]
value = "gAAAAABmK3..."
set-at = "2026-09-17T09:12:04Z"
```

Names and timestamps stay in clear text on purpose: `secret list` must work, and hiding which
credentials exist was never the goal. Encrypting the whole file would buy nothing and would make
the list command need the key.

**The key lives in a different directory from the ciphertext.** This is the entire point, not a
detail:

```
~/.config/use-computer/secrets.toml       ciphertext — the directory people sync
~/.local/share/use-computer/secret.key    the key — the directory they do not
```

A key beside the data is theatre: whatever copies one copies the other, so a synced dotfiles
repository would carry both halves. The XDG **data** directory is the one place already established
in this tool as "not configuration", it is not what a dotfiles repository tracks, and separating the
two is what makes the difference between obfuscation and a property worth documenting.

`USE_COMPUTER_SECRET_KEY_FILE` overrides the path, so the key can go on a removable drive or into a
directory with a different sync policy — which is the setup where this stops being merely
accidental-disclosure protection.

The key is 32 random bytes, generated on first use, written `0600` **at creation**. Losing it means
losing the secrets, and `secret set` is how they come back; there is no recovery and no escrow,
because an escrow is a second copy of the thing being protected.

**`cryptography` becomes a core dependency, not an extra.** The backends are extras because a
missing one costs a capability and says so. A store that is *sometimes* encrypted is not a security
property anybody can plan around, and the BUG-003 argument that ruled out listing PyGObject does not
apply here: `cryptography` ships wheels for every platform and Python this package supports, so
there is no build step to fail and no user left with a broken CLI.

**A value written before this change is refused, by name.** The old file is readable TOML with a
plain value in it; silently treating it as ciphertext would fail somewhere less useful. It reports
what happened and what to do:

```
the stored value for 'gh-token' is not readable with the current key. If it was stored before
encryption, run `use-computer secret set gh-token` to store it again.
```

The same message covers the other way to get here — a key file that was replaced or lost — because
the remedy is identical and the tool cannot tell the two apart.

## What does not change

The invariant, and everything CR-021 built on it. There is still no `secret get`. The result line
still trades the text for the name. An action carrying a secret is still never verified. Encryption
is a property of the file at rest; it does not touch what leaves the store, which is still only the
keyboard.

## Agent Notes

- Fernet, from `cryptography`. Authenticated (AES-CBC plus HMAC), which is what makes the "wrong
  key" case a clean failure rather than a plausible wrong string reaching a login form.
- Encrypt and decrypt **inside `FileStore`**, so `Secrets`, the runner and the CLI never see a
  ciphertext and never see a key. The store's interface is unchanged, which is what keeps a keychain
  implementation available later.
- Generate the key lazily, on the first `put`, never on a read. A `secret list` on a machine with no
  secrets must not create a key file.
- Decryption failure raises its own error, never `InvalidToken` — the caller is mid-task and cannot
  see the code.
- The key file's directory is the XDG **data** directory, which `xdg_data_dir()` already resolves.
- Docs this touches: `product/features/configuration.md` (where the key lives and why it is not
  beside the ciphertext), `product/features/safety.md` (what encryption is and is not worth),
  `system/interfaces.md` (the file format, the key file, the environment variable, the refusal),
  `system/entities.md` (`FileStore` holds the cipher), and `system/tech-stack.md` (the dependency).
