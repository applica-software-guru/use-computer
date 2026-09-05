---
name: use-computer
description: Read and act on a GUI — the accessibility tree of what is on screen (roles, names, clickable boxes), then click, focus, toggle, expand, select, set a value, type, press keys, drag, scroll, screenshot. Locally or over VNC. Ask the tree first and use ui-locator's pixel coordinates only when the tree cannot see the element. Bring a window forward before aiming at it, and confirm what happened by re-reading, not by trusting the line.
x-skill-id: use-computer
x-skill-version: "5"
---

# use-computer

You read and act on a screen through the `use-computer` CLI. It reads the accessibility tree the
operating system already maintains, and it moves a real pointer and types real keystrokes. It does
not decide *what* to do — you do.

## Two ways to know what is on the screen

They fail in different places, and choosing between them is most of using this tool well.

| | **Structure** (`tree`) | **Pixels** (`screenshot`) |
| --- | --- | --- |
| Tells you | roles, names, states, boxes, what is operable | what is *drawn*: painted text, icons, colour, layout |
| Reaches | things not on screen — a closed menu's items | only what is visible |
| Costs | a few hundred tokens | an image, and a vision pass |
| Blind to | anything an app paints instead of exposing | node ids, `enabled`, everything off screen |
| Acts by | name or id, **with no coordinates at all** | a coordinate you have to aim |

Structure first, always: it is cheaper and it is exact. Go to pixels when structure cannot answer,
and when you do, **crop to the node** rather than photographing the screen.

### How to move between them

- `reason: unavailable` or `empty` — this application exposes nothing (Qt, Electron, games do
  this). A screenshot is already attached to that answer. Go and look. **A tree emptied by your
  own `--depth` or by pruning is not this** — it says which limit did it, and carries no
  screenshot, because the way back is the limit it names.
- `?unexposed` on a node — the tree is fine and there is a region inside it the platform does not
  describe. Look at *that region*, not the screen.
- A selector matched nothing — same, and for the same reason. Do not try more selectors.
- **The tree sees a node but cannot name it.** Two anonymous text fields, say. Do *not* photograph
  the screen: `screenshot --of <id>` crops to that node. The tree knows exactly *where*; only
  *what* is missing.
- Before reaching for pixels at all, two things are usually enough:
  - **Geometry**, which is already in the tree. A message box is wide and at the bottom; a search
    box is narrow and near the top. A label sitting to the left of a field, on the same line, names
    it.
  - **Focus.** Click one of two identical fields, re-read the tree, and see which now says
    `!focused`.

## What a result is worth

**A result line reports what was attempted.** An accessibility API answers "I invoked that
action", never "the application did something", and an application is free to ignore it. No
platform offers the second answer, so this gap is permanent — not a bug waiting to be fixed.

An agent that believes every line pays for it. One measured session took fifteen commands for work
that needed three, and every detour came from a report that was true and meant nothing:

| It said | It was |
| --- | --- |
| `click radio 'Dark Brown' … via the platform API` | the colour never changed |
| `…-node.png 1920x885 of 0/0/2` | a picture of a different application |
| `no tree here (empty)` | sixty nodes, read a second earlier |

Three habits, and they cost almost nothing:

- **`[actions]` is what the platform will accept, not what will work.** A colour swatch that
  advertises `[click,focus,select]` accepts `click` and does nothing with it. When a result and
  the screen disagree, **try another action on the same node** — `select` where you tried `click`,
  or `--via coordinate` — before reaching for vision. `click` now prefers `select` on a `radio`,
  `listitem`, `option`, `treeitem`, `tab` or `menuitem`, which covers the common case.
- **Confirm by re-reading, not by diffing.** After an element action, `tree` says *what* the state
  is now. `--verify` only ever says that some pixels moved: it has a floor below which it says
  nothing, and it cannot tell your click from a clock.
- **A coordinate enters whatever window is in front.** Pass `--window` and the tool brings the
  right one forward first. Without it, a click aimed at one application lands in another and
  reports a perfectly ordinary success.

## The ladder

Take the highest rung you can reach. Each one is cheaper, faster and more accurate than the one
below it.

0. **`use-computer activate --window "..."`** — put the window you mean in front, before any
   coordinate goes near it. Cheap, idempotent, and a no-op when it is already there.
0. **`use-computer windows`** — what is open. A dozen windows cost about 1.4 KB; a single
   window's tree costs fifteen times that. Make this call first: it gives you the `--window` value
   everything else needs, and tells you which window `focused` will resolve to.
1. **`use-computer tree --window "..."`** — ask the OS what is in that window. You get roles, names
   and boxes. Then act on an element by name:
   `use-computer click --role button --name "Invia"`.
2. **A coordinate from the tree** — the element is there but the platform will not operate it.
   `click` falls back to its centre on its own and tells you it did.
3. **Vision** — the tree cannot see it. Take a screenshot, ask ui-locator where the thing is, and
   click those pixels.

**Do not start with a screenshot.** Start with `tree`. A screenshot costs you a vision round trip
and gives you a coordinate that may be stale by the time you use it; the tree gives you a name
that still resolves.

## Contract

- **stdout is text.** One line per action, or the read you asked for. Read it; do not parse it.
- **stderr** is diagnostics and errors. Read it when something fails.
- **exit codes**: `0` success, `1` failure, `2` bad usage. This is the signal to branch on.

`--format json` returns a JSON envelope instead. You almost never want it: the same answers cost
three times the tokens, and 177 of those go on the envelope before anything is said.

Every run ends with one line saying whether it worked, which profile and backend answered, the
screen and the **scale** — `scale unknown` means coordinate conversion will refuse, and is worth
noticing.

`use-computer <command> --help` lists every flag. This document covers the ones that carry a
judgement; `--help` covers the rest.

Always pass `--use <profile>` unless a default profile is configured.

## Coordinates: the thing that goes wrong

A screenshot on a HiDPI display is larger than the space the OS clicks in. Coordinates from
`ui-locator` are in **screenshot** pixels — the space it looked at. That is the default here,
so pass them through unchanged. Pass `--space actuation` only if you already converted them
yourself, which you should not do.

If a run fails saying the scale is unknown, take a screenshot first (`use-computer screenshot`)
and read `screen` from the result; do not compute a factor and retry with different numbers.

## Listing the windows

```bash
use-computer windows --use laptop
```

```
id      app              role    title                  pid     box               active
0/29/0  TelegramDesktop  panel   Roberto Conterosito    15872   331,130 1152x784
0/34/0  Codex            window  ChatGPT                144775  0,0 1920x1038     *
```

Use the `title` as `--window` for everything that follows, and **`app` to tell windows apart** — a
title alone will not tell you which one is Telegram. The `*` marks the one `--window focused`
resolves to.

**`--window` refuses to guess.** A title matches as a substring, so if two windows match you get
the candidates and no action:

```
AmbiguousWindowError: 2 windows match 'ChatGPT'; use a longer title, or the window id from `windows`
  0/34/0 Codex 'ChatGPT' at (0, 0)
  0/34/1 Codex 'ChatGPT' at (1469, -86)
```

This is not rare: **a terminal puts the running command in its own title**, so a terminal running
`--window "X"` matches X too. When it happens use the **window id** from the first column —
`--window 0/34/0` — matched exactly, and tried before any title.

## Reading the tree

```bash
use-computer tree --window "Conferma"             # that window, pruned
use-computer tree --role button                   # only buttons
use-computer tree --window all --depth 3          # every window, shallow
use-computer tree --of 0/2/1                      # expand a subtree
use-computer tree --full                          # everything, unabbreviated
```

The tree arrives **rendered**, in the `text` field — one line per node, with a legend on top. It
costs 39% of the tokens the object form does, which is why it is the default:

```
# id role "name" !states [actions] x,y wxh +offscreen ?unexposed
0 window "Conferma" !modal 0,0 1920x1038
  0/0 panel 0,32 1920x1006
    0/0/0/0 menu "File" [click,select] 0,32 37x28 +5
    0/2/1/3 button "Invia" [click,focus] 412,260 88x32
```

Read a line left to right:

- **`id`** — pass it to `--id`, or to `--of` to expand.
- **`role`** and **`"name"`** — what you pass to `--role` and `--name`.
- **`!states`** appears only when there is something surprising to say: `!disabled`, `!checked`,
  `!selected`, `!expanded`. **No `!` means an ordinary, enabled, visible node** — do not read its
  absence as anything but "it is fine".
- **`[actions]`** — what the platform can do to this node. **No brackets** means it can only be
  clicked by coordinate; that is rung two and `click` handles it for you.
- **`x,y wxh`** — the box, in actuation units. To click it by coordinate aim at its centre,
  `x + w/2, y + h/2`, with `--space actuation`.
- **`+5`** — five descendants are off screen. See below.
- **`?unexposed x,y wxh`** — the platform describes nothing in that region. See below.
- Indentation is depth, and it is also in the id. Either will do.

`--format json` gives you `root` as nested objects instead, if you would rather parse than read.
stdout is one JSON object either way.

## Three things are abbreviated. Each says so, and each has a way back

An abbreviation mistaken for the whole thing turns a correct answer into a wrong conclusion, so
check for these before concluding anything is missing:

- **`offscreen_children: 5`** — this node has five descendants that are not on screen, most often
  the items of a closed menu. They are real and still operable: `--of <id>` expands them, and
  `click --name "Preferences"` works **without** opening the menu at all.
- **`truncated: true`** — the node budget cut the tree. `truncated_ids` says where; `--of <id>`
  re-enters. Never conclude an element is absent from a truncated tree.
- **A `value` ending in `…`** — the text was clamped. It is there to identify the element, not to
  read its contents; a terminal or an editor would otherwise send you its entire buffer.

`--full` turns all three off at once.

## A rich tree with a hole in it

The two clean states — the tree answers, or it is empty and hands you a picture — are not the
common case. The common case is a full, correct tree around a region the platform is not
describing:

```
0/0/2 panel 0,106 1920x885 ?unexposed 163,106 1757x885
```

That panel is 1920 px wide and its only child covers 163. The rest is a **canvas**, and it is in no
tree, under `--full` either. Without the marker the tree looks complete, which is worse than
looking empty.

`?unexposed` is the normal condition of a drawing program, a map, a chart, a game, a PDF view, a
video surface. It is not an error and there is nothing to expand. It is the cue to switch to
pixels **for that region only**:

```bash
use-computer screenshot --window "Drawing" --of 0/0/2   # look at just the canvas
use-computer drag --from-x 666 --from-y 660 --to-x 666 --to-y 545 --window "Drawing"
```

Everything around it stays addressable by name — the tools, the menus, the colours — so a canvas
application is usually **structure for the chrome, coordinates for the canvas**, not vision for
the whole window.

## When the tree cannot name something

Some applications paint their own text: Telegram's "Write a message…" is pixels, not a string, and
no amount of reading the tree finds it. But the tree knows exactly **where** the element is, so do
not photograph the whole screen to learn **what** it is:

```bash
use-computer screenshot --window "Chat" --of 0/1/0/0/0/13/0 --pad 8
→ /home/you/.local/share/use-computer/screenshots/…-node.png 653x28 of 0/1/0/0/0/13/0
```

18,284 pixels instead of 2,073,600, with the thing you are asking about filling the frame. Then act
on the same id. The loop is **`tree` to locate, `screenshot --of` to look, `click --id` to act**.

Two unnamed fields are also told apart by where they sit — a message box is wide and at the bottom,
a search box narrow and at the top — and by focus: click one, re-read the tree, see which now says
`!focused`.
- **`root: null`** with a `reason` means there is no tree here: `unavailable` (no provider, or a
  vnc profile), `denied` (permission), `empty` (the app exposes nothing). A `screenshot` path comes
  back with it — that is your cue to switch to ui-locator.

## Acting on an element

```bash
use-computer click --role button --name "Invia" --use laptop
use-computer click --id 0/2/1/3 --role button --name "Invia"   # id + fingerprint
use-computer focus --role text --name "Destinatario"
use-computer set-value --role text --name "Destinatario" --value "mario@example.com"
use-computer toggle --name "Ricordami"
use-computer expand --role combobox --name "Paese"
use-computer select --role listitem --name "Italia"
use-computer show-menu --id 0/1/4
```

`--name` is a case-insensitive substring; add `--exact` for equality, and `--nth N` to pick when
several match. `--window` takes `focused` (default), `all`, a window title, a window **id**, or
`@1234` for a pid. `collapse` closes what `expand` opened.

**`--via` chooses which rung**, and is the one flag worth understanding. It exists on the actions
that have both forms — `click`, `double-click`, `right-click`, `scroll` — and **not** on
`focus`, `toggle`, `expand`, `collapse`, `select`, `set-value` or `show-menu`, which have no
coordinate form at all. Passing it there is a usage error, not a preference:

- `--via auto` (default) — the platform API if the node supports it, otherwise a click at its
  centre. Almost always right.
- `--via action` — refuse rather than fall back. Use it when a coordinate click would be wrong,
  and note it **works even when the scale is unknown**, because it involves no coordinates.
- `--via coordinate` — resolve the element, then click it with a real pointer. For interfaces that
  only respond to genuine input: hover states, drag handles, canvases.

`--delay SECONDS` waits after each action, for an application that needs a moment to catch up.

When `--via auto` drops to a coordinate, the node's window is brought forward first — a coordinate
only means anything in the window it was measured in.

**Pass `--id` together with `--role` and `--name`** as they came out of `tree`. The id alone is
just a path, and paths shift when a row is inserted above; with the role and name it is checked,
and you are told the tree moved instead of acting on the wrong thing.

**And reuse the same `--window`.** An id is a path relative to the scope it was read from, so
`0/2/1/3` from `tree --window "Conferma"` is a different path under `--window all`. When in doubt,
re-read the tree with the scope you are about to act in.

### `set-value` is not `type`

`set-value` assigns the text atomically and sends **no keystrokes**. It is faster, and some
applications ignore it entirely because their validation only fires on key events. If a value is
visibly in the box but the form rejects it, `focus` the field and `type` instead.

## Acting on a coordinate

Still fully supported, and the right thing to do when the tree cannot see your target:

```bash
use-computer activate --window "Drawing"           # first, if you mean a particular window
use-computer click --x 120 --y 340 --window "Drawing"
use-computer double-click --x 120 --y 340 --window "Drawing"
use-computer right-click --x 120 --y 340 --window "Drawing"
use-computer move --x 120 --y 340 --window "Drawing"
use-computer drag --from-x 10 --from-y 20 --to-x 300 --to-y 400 --window "Drawing"
use-computer scroll --amount 3 --direction down --window "Drawing"
use-computer type --text "hello world"
use-computer key ctrl+s
use-computer screenshot                            # writes a file, prints its path
```

**`--window` on a coordinate action brings that window forward before the coordinate is sent.**
Pass it whenever you mean a particular window, which is nearly always. Without it the coordinate
goes wherever the pointer already is — that is what a bare coordinate has always meant, and it is
how a click aimed at a canvas ends up selecting text in a terminal.

`type` and `key` take no `--window`: they go to whatever holds the keyboard focus. `activate` or
`focus` is how you decide what that is.

`type` sends literal text. `ctrl+a` given to `type` types seven characters — use `key` for
shortcuts. `type` and `key` go to whatever holds focus; they take no element. Use `focus` first.

Give an action a coordinate **or** an element, never both.

## Key syntax

Modifiers `ctrl`, `alt`, `shift`, `cmd` (aliases: `control`, `option`, `super`, `win`, `meta`)
joined to a key with `+`: `ctrl+shift+t`, `cmd+space`, `alt+f4`, `enter`. Named keys: `enter`,
`tab`, `esc`, `space`, `backspace`, `delete`, `insert`, `home`, `end`, `pageup`, `pagedown`,
`up`, `down`, `left`, `right`, `f1`–`f24`. One spelling works on every backend.

## Batch — prefer this

Opening a VNC connection costs more than the action does. Send the whole plan in one run; it
executes over one connection.

```bash
echo '[
  {"action":"click","x":120,"y":340,"verify":true},
  {"action":"type","text":"hello","delay":0.2},
  {"action":"key","combo":"enter"}
]' | use-computer - --use staging
```

With elements, a whole interaction carries no coordinates at all — and the closing `tree` hands
you the resulting state without a screenshot:

```bash
echo '[
  {"action":"focus","role":"text","name":"Destinatario"},
  {"action":"type","text":"mario@example.com"},
  {"action":"click","role":"button","name":"Invia"},
  {"action":"tree"}
]' | use-computer - --use laptop
```

Action names take either spelling — `set-value` or `set_value`, `double-click` or `double_click` —
so what you type at the shell works inside a batch. An unknown one comes back as a sentence naming
the nearest match.

`batch` is the default command, so `use-computer -` and `use-computer actions.json` work. A
batch stops at the first failure and reports `failed_index`, so you can resume from a known
point. `--continue-on-error` runs the rest anyway.

## Screenshots are files

A screenshot is never returned to you as bytes. It is written to a file and you get the path:

```json
"screenshot": {"path": "/home/you/.local/share/use-computer/screenshots/20260904T103012.481Z-click.png",
               "width": 2560, "height": 1600, "space": "screenshot"}
```

Read the file when you actually need to look at the screen. Do not ask for the pixels by default —
a batch of verified clicks would otherwise bury your context in base64, which is why that option
does not exist.

## Verify — how you know it worked, and what the screen looks like now

A click that lands on nothing looks exactly like a click that worked. With `--verify` (or
`"verify": true` on one action) each action reports:

```
click at (200, 200) — changed 604x312 at 40,120 — 41 ms
```

**The box, not a percentage.** A box can be compared against what you expected: `604x312` is a
dialog, `12x18` in a corner is a clock. Judge it against the change you were trying to cause.

**`--verify` also gives you the screenshot taken after the action**, at the `screenshot` path in
the same result. It captured that screen to do the comparison, so you already paid for it: do not
follow a verified action with a `screenshot` call. That is the round trip verify exists to save.

- `unchanged` after a click → the coordinate was probably stale. **Ask ui-locator again. Do not
  click the same pixel twice.** But check the obvious first: was the right window in front?
- A box much smaller than the change you intended is the same signal. A click meant to open a
  dialog that reports `12x18 at 1904,8` moved a clock, not a dialog.
- An action performed through the accessibility API (`"via": "action"`) moves no pointer and paints
  no hover state, so it changes fewer pixels than the same click would. A small `magnitude` there
  is **not** failure. When you acted on an element, re-run `tree` instead: it tells you *what*
  changed, not merely that something did.
- `changed: true` with a tiny `magnitude` in a corner → a clock or a caret, not a response.

Verification costs two screenshots per action, so use it on the actions whose effect you need
to confirm, not on every one.

## Where the pictures go, and getting rid of them

Inside the project, in `.use-computer/screens/`, which the tool keeps out of git for you. Without a
project, the XDG data directory. A run names the directory once and then just filenames.

```bash
use-computer prune                # remove them
use-computer prune --dry-run      # say what would go
use-computer prune --keep 20      # leave the most recent 20
```

`prune` only ever removes files this tool wrote, and never the directory. Anything else in there is
counted and left alone.

## Before you act on something risky

`--dry-run` resolves and logs everything — profile, scaled coordinates, normalised keys, and the
selector — without performing any of it. Results come back with `"performed": false`, plus the
`matched` node and the `via` it would have taken. Rehearse a batch you are unsure about; a dry run
of an element action is also the cheapest way to check a selector is unambiguous.

## When it refuses

- **`AmbiguousNodeError`** — several nodes matched. The error lists every candidate with its id,
  role, name and box. **Choose one** — a tighter `--name`, `--exact`, a `--window`, or `--nth N` —
  and run it again. Two "OK" buttons in two dialogs is normal; this is not a bug.
- **`NodeNotFoundError`** — nothing matched. A `screenshot` path comes with it. This is the signal
  to drop to vision: ui-locator that screenshot rather than trying more selectors.
- **`ActionNotSupportedError`** — the node does not offer that action. The message lists what it
  does offer. `click` already falls back to a coordinate on its own, so this means you asked for
  something with no coordinate form, like `set-value` on a node that is not editable.
- **`UITreeUnavailableError`** — no accessibility here. On a vnc profile that is permanent: use
  screenshots and coordinates. Otherwise the message names exactly what to install: an extra on
  Windows and macOS, and on Linux the distro packages plus a `--system-site-packages` virtualenv,
  because the extra does not help there.
- **`AmbiguousWindowError` on `focused`** — several windows claim to be active, which on Linux
  means the platform reports it per application and cannot say which is on top. Read `windows` and
  pass `--window ID`. When it is ambiguous, `windows` shows **no** `*` at all rather than a
  guess — an empty column is the answer, not a missing one.
- **`BackendNotAvailableError`** — the extra is not installed. The message names it.
- **Local backend not enabled** — the `local` backend controls the user's own machine and needs
  an explicit opt-in. Tell the user to set `allow-local = true` in the profile; do not work
  around it.
- **Permission denied** — macOS Accessibility or Screen Recording. The message names which. Only
  the user can grant it.
- **Coordinate space error** — see above. Take a screenshot; do not guess a factor.

## Configuration

`use-computer config show` prints every resolved value, the layer it came from, its source and the
exact environment variable that would override it, as aligned lines. Run it first when a profile behaves unexpectedly.

If there is no config at all, you can create one without a human:

```bash
use-computer config init --backend vnc --host 10.0.0.5 --profile staging
```

It refuses to overwrite an existing config, and it will not enable the local backend for you —
that opt-in is the user's to give. After writing, it opens the backend and reports the screen and
its scale; a failed probe means the config is on disk but wrong.
