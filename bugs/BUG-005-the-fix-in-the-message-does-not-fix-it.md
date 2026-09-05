---
title: "The fix in the message does not fix it when the interpreter is the wrong minor version"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# The fix in the message does not fix it when the interpreter is the wrong minor version

## What happens

A user follows the message exactly, and nothing changes:

```
$ sudo apt install python3-gi gir1.2-atspi-2.0
python3-gi is already the newest version (3.42.1-0ubuntu1).
gir1.2-atspi-2.0 is already the newest version (2.44.0-3).

$ use-computer windows
UITreeUnavailableError: reading the UI tree needs 'gi', which is not installed. To fix it,
install the distro packages and let the virtualenv see them: `sudo apt install python3-gi
gir1.2-atspi-2.0` then `python3 -m venv --system-site-packages .venv`
```

Both packages are there. The advice is to install what is already installed.

## Why

`gi` is a **compiled** extension, built for one Python minor version:
`/usr/lib/python3/dist-packages/gi/_gi.cpython-310-...so`. Ubuntu 22.04 ships it for 3.10. The
virtualenv here is 3.12, so `--system-site-packages` would expose a `gi` that cannot be imported
anyway.

The message names the right packages and omits the constraint that actually decides whether they
work. It has now been wrong three times in a row for this one case — first offering an extra that
cannot build, then naming packages already present — because each fix addressed the sentence
rather than what the tool can actually observe.

## What it should do

Look, then speak. When `gi` will not import, the distro copy is findable on disk and its version is
in the filename. The message can then say the thing that is true:

```
reading the UI tree needs 'gi'. The distro's PyGObject is built for Python 3.10, but this
interpreter is 3.12, so --system-site-packages would expose a module it cannot import.
Create the environment with the matching interpreter:
  python3.10 -m venv --system-site-packages .venv
```

And when the packages are genuinely absent, keep saying what to install.

## Agent Notes

Look for `gi` beside a `_gi.cpython-<ver>-*.so` under the usual distro paths, take the version from
the filename, and compare it to the running interpreter. Say nothing about a version when nothing
was found — a guess here is what produced three wrong messages already.

This is not Debian trivia to be embarrassed about: an agent that cannot read the screen is stuck,
and the error is the only thing it has. Spending a `glob` on being right is cheap.
