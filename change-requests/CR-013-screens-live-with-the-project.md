---
title: "Screenshots live with the project, and prune removes them"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# Screenshots live with the project, and `prune` removes them

## Why

Screenshots go to the XDG data directory today, which is right for a tool with no project and wrong
for one working inside a repository. The pictures belong beside the work that produced them: easy
to open, easy to throw away, and separate from another project's.

The token argument for this has just evaporated and should not be used: now that a run names the
screenshot directory once instead of once per file, a relative path saves one or two tokens, not
twenty-three. **Do it for the locality, not for the price.**

Two things stand in the way, and both are answerable rather than fatal.

**The existing prohibition is a real one.** `configuration.md` says: *never inside the repository,
because a screenshot of somebody's desktop is not something to leave lying in a working tree.* A
capture here is the whole screen — open conversations, mail, whatever is on it — and in a working
tree one `git add -A` commits it.

**And nothing writes a `.gitignore`.** The docs describe `.env` as gitignored; `config init` does
not create one, and `.use-computer/` contains only `config.toml`. So today the protection is
described and not implemented.

## What changes

### `.use-computer/screens/`, not `.screens/`

When a project root exists, screenshots go to `.use-computer/screens/`. Otherwise the XDG data
directory, exactly as now.

Under `.use-computer/` rather than a second hidden directory at the root, because the tool already
owns that one: it sits beside `config.toml` and `.env`, which is where somebody already looks for
this tool's things. One hidden directory per tool is enough.

### A `.gitignore` that makes the objection answerable

`.use-computer/.gitignore` is written when the directory is created, and by the first screenshot if
it is missing:

```
.env
screens/
```

This also **closes a gap that predates this change**: the docs have promised `.env` was gitignored
since the beginning and nothing has ever made it so.

The tool never touches a `.gitignore` outside its own directory. Editing the project's is the
user's business, not a side effect of taking a picture.

### `use-computer prune`

The name the docs already use: *"they are not pruned"*. Reusing the project's own word costs
nothing and saves a reader learning a second one.

CR-004 left this open — *"they are not pruned. The directory grows, and that is the user's to manage
for now"*. With the pictures inside the project, "for now" has run out.

```bash
use-computer prune              # remove them
use-computer prune --dry-run    # say what would go, remove nothing
use-computer prune --keep 20    # leave the most recent 20
```

It reports what it did, in the format everything else uses:

```
removed 34 screenshots (12.4 MB) from /work/.use-computer/screens
```

**It deletes only files it recognises as its own**: the timestamped `*.png` names it writes, inside
the configured directory, and never the directory itself. That is the whole safety of the command.
A `prune` that emptied whatever path `screenshot-dir` pointed at would be a footgun the first time
somebody aimed that setting at their Pictures folder — and this tool refuses to guess everywhere
else, so it will not guess about deleting.

## Deliberately not done

**No `--force` to delete anything else.** There is no flag that makes `prune` remove a file it does
not recognise. If something else is in there, it stays, and the count says how many were skipped.

**No automatic pruning.** A cap that quietly deletes the screenshot an agent is about to read is a
worse bug than a directory that grows. `prune` is a thing you run.

**No `.screens/` at the project root.** Discussed and rejected above: a second hidden directory for
the same tool, when it already has one.

## Documentation to update

- `product/features/configuration.md` — the new default, the fallback, the `.gitignore`, and a
  correction to the sentence that currently forbids this outright.
- `product/features/actions.md` — `prune` is not an action on a screen; say where it does live.
- `product/features/cli.md` — the `prune` command and its flags.
- `product/features/safety.md` — a command that deletes, and why it only deletes what it wrote.
- `product/features/skill.md` — the skill has to teach `prune` and where pictures now go.
- `system/interfaces.md` — `use-computer prune [--dry-run] [--keep N]` and what it prints.
- `system/architecture.md` — where the screenshot directory is resolved, now that it depends on
  the project root.

## Agent Notes

- Recognising its own files is a **pattern match on the name it writes**, not "everything with a
  .png extension". The names are timestamped and shaped; anything else in that directory belongs to
  somebody else.
- `--keep N` keeps the *most recent* N by the timestamp in the name, which is why the name sorts.
  Do not stat the filesystem for it: the name is the record.
- The directory is resolved once per run and is already reported in the closing line, so `prune`
  and every other command agree on where it is without a second lookup.
