---
title: "The tree extra cannot install on Linux: PyGObject builds from source and fails"
status: open
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# The tree extra cannot install on Linux: PyGObject builds from source and fails

## What happens

```
$ pip install "use-computer-cli[tree]"
help: `pycairo` (v1.29.1) was included because `use-computer-cli[tree]` (v0.2.0)
      depends on `pygobject` (v3.58.0) which depends on `pycairo`
```

PyGObject has no Linux wheel, so it builds from source, needs pycairo, and needs GObject and cairo
development headers. On a machine without them the install **fails outright**.

## Why this is worse than documented

The docs say `pip install` alone "cannot finish the job" on Linux, because the AT-SPI typelib is a
system package. The reality is worse in two ways:

- It does not merely leave something missing, it **fails**, so the user never gets the CLI at all.
- On a machine that already has the distro's `python3-gi` — the normal case, and the one where all
  of this works — pulling PyGObject from PyPI is not just unnecessary, it is what breaks the
  install.

The recipe that actually works on Linux is the opposite of the documented one: **do not install the
`tree` extra**; use the distro's `python3-gi` and a virtualenv that can see it.

```bash
sudo apt install python3-gi gir1.2-atspi-2.0
python3 -m venv --system-site-packages .venv
.venv/bin/pip install "use-computer-cli[local]"
```

Verified against the published 0.2.0: `windows` and `tree` work this way, with no `tree` extra
installed at all.

## What it should do

Decide between two honest options, and say which:

1. **Drop `PyGObject` from the `tree` extra on Linux**, leaving the extra meaningful only on
   Windows and macOS, and document the distro packages as the Linux path. The provider already
   imports `gi` lazily and already raises a message naming what to install.
2. **Keep it and make it optional to the resolver**, so asking for `[tree]` on Linux cannot fail
   the whole install.

The first is closer to how this works in practice, and matches what the error message already
tells people to do.

## Agent Notes

Whatever is decided, the README and `product/features/backends.md` currently give an instruction
that does not work on the most common Linux setup. That is the part to fix first — a wrong install
line costs every new user their first ten minutes.
