---
title: "Key Syntax"
status: new
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
---

# Key Syntax

One spelling of a shortcut must work on both backends. `use-computer` defines a single key-name
syntax and each backend normalises it into whatever its own library expects — pynput's enum on
local, vncdotool's X11 keysym names on vnc.

## The syntax

A key combination is modifiers and a key joined by `+`:

```
ctrl+shift+t
cmd+space
alt+F4
enter
```

- **Modifiers**: `ctrl`, `alt`, `shift`, `cmd` (aliases: `control`, `option`, `super`, `win`, `meta`).
- **Named keys**: `enter`, `return`, `tab`, `esc`, `space`, `backspace`, `delete`, `home`, `end`,
  `pageup`, `pagedown`, `up`, `down`, `left`, `right`, `f1`–`f24`.
- **Literal characters**: a single character is itself — `a`, `7`, `/`.
- Names are case-insensitive and aliases resolve to one canonical name.

## Rules

- An unknown key name is an error naming the key and listing the closest valid names. It is never
  passed through to the backend to fail obscurely.
- The canonical name is what appears in results and logs, so a log line is reproducible input.
- Modifiers are pressed in order and released in reverse order.

## Agent Notes

Keep the mapping tables in one module, one table per backend, both keyed by the same canonical
names — so a missing entry is a visible hole rather than a divergence between backends.
