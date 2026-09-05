---
title: "--window returns the first substring match, and the terminal running the command matches everything"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# `--window` returns the first substring match, and the terminal running the command matches everything

## What happens

```
$ use-computer tree --window "Roberto Conterosito – (1381)"
0 window "uv run use-computer tree --window \"Roberto Conterosito – (1381)\" --human" ...
```

The window asked for is Telegram, and `windows` lists it:

```
0/33/0  panel   Roberto Conterosito – (1381)   15872  331,130 1152x784
```

What came back is the terminal.

## Why

Two things compound, and the second is the nasty one.

`_root_for` returns the **first** window whose title contains the value. Two windows matched here,
and it silently picked one — the thing this tool refuses to do everywhere else. An ambiguous
selector returns its candidates; an unknown coordinate scale refuses; an unpositioned node will not
be clicked. `--window` guesses.

And a terminal puts the running command in its own title. So **the terminal executing
`use-computer --window "X"` always contains X**, always matches, and usually sorts first. Every
`--window` from a terminal is ambiguous, and the wrong answer is the one the user is looking at.

## What it should do

The same as everywhere else: exactly one match performs, none is an error, more than one is an
error carrying the candidates.

The candidates must also be *distinguishable*, which they are not today: `windows` reports title,
role, pid and box, but never which application a window belongs to, so a user cannot tell that
`0/33/0` is Telegram except by reading the title they already typed. AT-SPI knows — the window's
parent is the application — and it is not reported.

Two ways out of an ambiguity, then: a tighter title, or the window **id** from `windows`, which
`--window` should accept as an exact match.

## Agent Notes

Match ids before titles: an id is exact and a title is a substring, so a value that is one must
never be tested as the other.

Do not "fix" this by excluding the calling terminal. It is a real window, an agent may legitimately
want to drive it, and a rule that silently skips one window is the same class of mistake as
silently picking one.
