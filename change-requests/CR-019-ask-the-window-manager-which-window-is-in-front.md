---
title: "Ask the window manager which window is in front, and finish the text contract"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# Ask the window manager which window is in front, and finish the text contract

## Why, part one: refusing is honest, and it is not the best available answer

[BUG-010](../bugs/BUG-010-every-window-is-active.md) established that AT-SPI cannot say which
window is on top: it reports `active` per *application*, so three windows carried the mark at once,
and neither `focused` nor a focused descendant told them apart. The fix was to mark **none** when
several claim it, and to refuse `--window focused` with the candidates rather than take the first.

That is truthful and it made the tool worse to use. On a normal desktop `use-computer tree` with no
arguments now stops instead of answering, and the agent pays a `windows` call and a decision for
something the operating system knows exactly.

**The operating system does know.** It is simply not AT-SPI that knows it. On X11 the window
manager publishes `_NET_ACTIVE_WINDOW` on the root window, and it is unambiguous. Measured on the
desktop that produced the bug:

```
active X id: 0x4e00006
pid: 2379
name: ◑ Estrazione albero UI multipiattaforma
```

— which is exactly `0/29/0 gnome-terminal-server … pid 2379` in the AT-SPI list, the one window a
human would have named.

## What changes

**A provider may offer a hint about which window is in front, and the policy above it decides.**

```python
class AccessibilityProvider(Protocol):
    def active_window(self) -> ActiveWindow | None: ...
```

`ActiveWindow` carries a `pid` and a `title` — what a window manager can say — and `None` means
"this platform has nothing better than the per-window flags". `selectors.mark_active(entries,
hint)` then does the matching, so all three platforms share one rule and it tests without a
desktop:

- Exactly one window with that pid → that one, whatever the flags said.
- Several with that pid → the one whose title matches exactly. Still ambiguous → **none**, as now.
- No hint, or no match → the existing rule: one claim is honoured, several are not.

The refusal does not go away; it stops being the common case.

### The hint is optional, and it stays optional

On Linux it comes from `python-xlib` — a pure-Python wheel with no build step, which is what
PyGObject was not. It is **imported softly**: present and on X11, the answer improves; absent, or
under Wayland where the property is not published, everything behaves exactly as it does today.

This finally gives the Linux `tree` extra something to install. The extra has been empty there
since [BUG-003](../bugs/BUG-003-tree-extra-cannot-install-on-linux.md), for a reason that does not
apply to a package with no compiled parts:

```toml
tree = [
    "python-xlib>=0.33; sys_platform == 'linux'",
    …
]
```

`gi` still comes from the distribution. Nothing about that changes, and the error that names the
system packages stays exactly as it is.

## Why, part two: the contract does not hold everywhere yet

[CR-017](CR-017-every-line-says-what-it-did.md) said "every command, without exception", named
`--version` and `config show`, and missed the one command an agent runs to find out whether its own
instructions are current:

```
$ use-computer skill status
{"action": "status", "scope": "project", "path": "…/SKILL.md", "status": "outdated",
 "installed": true, "up-to-date": false}
```

`install`, `update`, `remove` and `status` all answer this way. They render as text like everything
else, with `--format json` for a caller that parses:

```
status  project  outdated  /home/you/workspace/.agents/skills/use-computer/SKILL.md
```

A contract with three exceptions is not a contract, and "without exception" has to be true or it
should not have been written.

## Agent Notes

- The soft import belongs in the provider, the matching in `selectors.py`. A rule that lives in a
  provider is a rule the other two platforms will drift from — that has already happened once,
  with window matching.
- `mark_active` must be a pure function of the list and the hint, so the ambiguity cases are tested
  without a session bus.
- Do not let the hint override a *single* unambiguous claim into nothing: it is an improvement on
  the tie-break, not a replacement for the flags.
