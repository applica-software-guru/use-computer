# use-computer

Reads and acts on a screen for computer-use agents. It reads the **accessibility tree** the
operating system already maintains -- roles, names, states and clickable boxes -- and it moves the
mouse, clicks, drags, scrolls, types text, presses key combinations, and captures screenshots.

Every interaction takes the highest rung it can reach:

1. **Element, through the platform API** -- the OS presses the button itself. No coordinates, so
   nothing to aim and no scale to get wrong.
2. **Element, by coordinate** -- the tree can see the control but exposes no way to operate it, so
   `use-computer` clicks its centre and tells you it did.
3. **Pixel, from vision** -- the tree cannot see it. Screenshot,
   [ui-locator](https://github.com/applica-software-guru/ui-locator), click those pixels.

Each rung is cheaper, faster and more accurate than the one below. Rung three is the floor the
whole ladder stands on and is not going anywhere; it is simply no longer the only rung. Everything
is driven by another AI agent through a CLI that emits JSON on stdout and diagnostics on stderr,
with a Python API underneath.

## Install

```bash
pip install use-computer-cli            # no backend
pip install "use-computer-cli[local]"   # drive this machine's display (pynput + mss)
pip install "use-computer-cli[vnc]"     # drive a remote framebuffer over RFB (vncdotool)
pip install "use-computer-cli[tree]"    # read the accessibility tree (Windows, macOS)
```

Backends and the accessibility bindings are optional extras, imported lazily, so the package
installs without them.

**On Linux, do not use the `tree` extra.** PyGObject has no Linux wheel, so pip would build it from
source and fail. The bindings are already on almost every desktop; the virtualenv just has to see
them:

```bash
sudo apt install python3-gi gir1.2-atspi-2.0
python3 -m venv --system-site-packages .venv
.venv/bin/pip install "use-computer-cli[local]"
```

The distribution is `use-computer-cli` because `use-computer` is taken on PyPI by an unrelated
project. The command it installs is `use-computer`, and the package it imports is `use_computer`.

## Use

```bash
use-computer tree --use laptop                          # what is on screen, structurally
use-computer click --role button --name "Invia"         # act on it by name
use-computer set-value --role text --name "Email" --value "mario@example.com"
use-computer click --x 120 --y 340 --use staging        # or by pixel, when the tree cannot see it
use-computer type --text "hello" --use staging
use-computer key ctrl+s --use staging
use-computer screenshot --use laptop                    # writes a file, returns its path

# a batch runs over one connection -- the default command, so `batch` may be omitted
echo '[
  {"action":"focus","role":"text","name":"Destinatario"},
  {"action":"type","text":"mario@example.com"},
  {"action":"click","role":"button","name":"Invia"},
  {"action":"tree"}
]' | use-computer - --use laptop
```

An action names its target by coordinate **or** by element, never both. A selector that matches
nothing comes back with a screenshot -- the signal to switch to vision. A selector that matches
several comes back with the candidates, because two buttons named "OK" in two dialogs is the
ordinary case and picking one silently fails a hundred runs later.

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
  `--verify` compares the screen before and after and reports whether it changed -- and an action
  that went through the accessibility API reports the element it actually operated.

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
