# use-computer

Executes input on a screen for computer-use agents: move, click, double-click, right-click,
drag, scroll, type text, press key combinations, and capture a screenshot.

`use-computer` is the **acting** half of a pair. [ui-locator](https://github.com/applica-software-guru/ui-locator)
answers *where* the Invia button is and returns pixel coordinates; `use-computer` performs the
click there. Both are driven by another AI agent through a CLI that emits JSON on stdout and
diagnostics on stderr, with a Python API underneath.

## Install

```bash
pip install use-computer-cli            # no backend
pip install "use-computer-cli[local]"   # drive this machine's display (pynput + mss)
pip install "use-computer-cli[vnc]"     # drive a remote framebuffer over RFB (vncdotool)
```

Backends are optional extras, imported lazily, so the package installs without them.

The distribution is `use-computer-cli` because `use-computer` is taken on PyPI by an unrelated
project. The command it installs is `use-computer`, and the package it imports is `use_computer`.

## Use

```bash
use-computer click --x 120 --y 340 --use staging
use-computer type --text "hello" --use staging
use-computer key ctrl+s --use staging
use-computer screenshot --use laptop            # writes a file, returns its path

# a batch runs over one connection -- the default command, so `batch` may be omitted
echo '[{"action":"click","x":120,"y":340},{"action":"key","combo":"enter"}]' \
  | use-computer - --use staging --verify
```

stdout is one JSON object per run; every diagnostic goes to stderr. Exit codes: `0` success,
`1` failure, `2` bad usage.

Screenshots are files, never bytes in the JSON. `--verify` writes the screen it captured after the
action and reports the path, so a verified action does not need a `screenshot` call after it.

## Three problems it solves

- **Coordinate spaces.** A screenshot on a HiDPI display is larger than the space the OS clicks
  in. Every coordinate carries its space, `use-computer` scales between them, and it refuses to
  guess when the ratio is unknown.
- **Setup cost.** Opening a VNC connection dominates a single action, so one run performs a
  batch of actions over one connection.
- **Blind actuation.** A click that lands on nothing looks exactly like a click that worked, so
  `--verify` compares the screen before and after and reports whether it changed.

## Configure

```bash
use-computer config init                                  # asks, then proves it works
use-computer config init --backend vnc --host 10.0.0.5    # doesn't ask
use-computer config init --backend local --allow-local
```

`config init` writes the file below, then opens the backend it just configured and reports the
screen geometry and scale — so a coordinate space whose ratio cannot be derived surfaces at setup
rather than at the first click that lands in the wrong place.

It writes `.use-computer/config.toml` at the project root (found by walking up, the way git finds
its own):

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

Secrets go in `.use-computer/.env`, which is not committed. `use-computer config show` prints
every resolved value, the layer it came from and the variable that would override it.

## The agent skill

Instructions for the calling agent ship inside the package and are installed from it, so they
always match the installed version:

```bash
use-computer skill install --scope project
```

## Documentation

This package is developed with [SDD](https://github.com/applica-software-guru/sdd). The specs
it implements live in `product/` and `system/` at the repository root.
