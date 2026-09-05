---
title: "UI Tree"
status: synced
author: ""
last-modified: "2026-09-05T00:00:00.000Z"
version: "3.0"
---

# UI Tree

A screenshot has to be *looked at*. The operating system already knows there is a button at
(412, 260) labelled "Invia", enabled, inside a dialog titled "Conferma" — asking a vision model to
rediscover that from pixels costs tokens, latency and accuracy.

`use-computer` is the half of the pair that touches the machine, so it is the half that can ask the
machine. `tree` is how it asks.

This does not replace the screenshot; it demotes it. **Ask the tree first, look at the picture only
when the tree cannot answer.**

## What comes back is rendered, not serialised

Bytes were the wrong unit. Measured on one window, in **tokens**, which is what an agent pays:

| | Bytes | Tokens | |
| --- | --- | --- | --- |
| Structured JSON | 3,785 | 1,707 | 100% |
| The same tree as text | 1,744 | 555 | 33% |
| That text inside the JSON | 1,817 | **667** | **39%** |

JSON's cost is not verbosity: `{`, `"`, `:`, `,` and every repeated key are each their own token,
so `"role": "button"` spends five tokens to say one thing — and a tree says it thousands of times.

```
# id role "name" !states [actions] x,y wxh +offscreen
0 window "Conferma" !modal 0,0 1920x1038
  0/0 panel 0,32 1920x1006
    0/0/0 menubar 0,32 1920x28
      0/0/0/0 menu "File" [click,select] 0,32 37x28 +5
    0/0/1 button "Invia" [click,focus] 412,260 88x32
```

One line per node, and a legend line so the format explains itself to a reader that has never seen
it. Every field is still there; only the syntax naming them is gone.

**Indentation stays** — it duplicates what the id already encodes, and it measured *free*: 555
tokens either way, because runs of spaces collapse into a token that would have been spent anyway.

**It travels inside the JSON.** `stdout is JSON and nothing else` is what lets an agent pipe this
into a parser without knowing which flags produced it, and escaping the newlines costs 112 tokens
of the 1,040 saved. The rendering is a string field; `--format json` returns `root` as objects
instead, and the Python API has had objects all along.

`truncated`, `node_count` and `reason` stay structured. They are read by code, they are three
values rather than thousands, and burying them in prose would be the same mistake backwards.

## `use-computer windows` — read this first

The cheapest question is "what is open?", and it should not cost a tree.

```
# id role "title" pid x,y wxh *active
0/29/0 window "Conferma" 4711 0,0 1920x1038 *
0/33/0 window "Posta" 5210 331,130 1152x784
```

Twelve windows measured at **1,429 bytes** — less than a fifteenth of a single window's tree. It
yields the `--window` value every later call needs, and `active` says which one `focused` resolves
to. `pid` lives here and not on `UINode`: a window list is where it earns its bytes.

## `use-computer tree`

```bash
use-computer tree                                  # the focused window, pruned
use-computer tree --role button                    # only buttons
use-computer tree --name Invia                     # name contains "Invia"
use-computer tree --window all --depth 3           # every window, shallow
use-computer tree --of 0/2/1                       # expand one subtree
use-computer tree --full                           # everything, unpruned, all fields
```

By default it snapshots the **focused window**, not the whole desktop.

## A node

```json
{
  "id": "0/2/1/3",
  "role": "button",
  "name": "Invia",
  "actions": ["click", "focus"],
  "box": [412, 260, 88, 32]
}
```

The node is deliberately terse, because a tree is only useful if an agent can afford to read it.
Measured over the same 73 nodes: 271 bytes each in the obvious shape, 150 in this one.

- **`box` is `[x, y, width, height]`** in **actuation** units — always, so the space is not
  repeated on every node. The point to click is its centre.
- **`states` carries only what is surprising.** `showing`, `enabled`, `focusable` and their like
  are what almost every node says, so they say nothing and are omitted. `checked`, `selected`,
  `expanded`, `modal` and **`disabled`** appear when they apply.
- **`disabled` is emitted, not inferred.** The platforms report *enabled* and simply say nothing
  when a control is not, so leaving it out would hide the one case an agent must not miss. The
  absence is turned into a presence.
- Empty fields are omitted rather than sent as `null`.
- **`id`** — a structural path in the *full* tree, **relative to the scope that was read**. It
  addresses the node in `--of` and in [element addressing](element-addressing.md), where it is
  fingerprint-checked before use. An id from one `--window` does not mean the same thing under
  another.
- **`actions`** — the canonical actions this node actually supports. An empty list means the
  platform exposes no way to operate it, so it must be clicked by coordinate. This is what makes
  element addressing discoverable instead of guesswork.
- **`offscreen_children`** — how many descendants hang off this node that are not on screen.

With `--role` or `--name` the result is the scope root carrying the matches as a flat list, which
is what "only buttons" should mean. `--out PATH` writes the tree JSON to a file and returns its
path instead of the tree itself, for when it is large and the agent wants to page through it.

## Pruning is the feature

An unpruned desktop tree is thousands of nodes. Poured into an agent's context it is worse than the
base64 that screenshots no longer return, because it *looks* useful.

The default keeps a node when it is on-screen and either **interactable** (an actionable role, or
focusable, or editable) or **carries text** (a name, a label, a value) — **or** when the platform
can operate it, wherever it is. A container whose only contribution is nesting is collapsed into
its child. A node budget caps the total.

That last clause matters. The items of a closed menu have no position and are still the thing an
agent came for: reaching **File > Preferences** without opening the menu first is the whole point
of acting through the platform API. They are kept, and their `box` is honestly empty.

## A node that is nowhere

A platform reports an element it is not currently rendering with a sentinel rather than a position
— AT-SPI uses `INT_MIN`. Such a box is normalised to zero size, and `positioned` is false. An
element like that can be operated through the API and **cannot be clicked**: an action that would
have to fall back to its centre refuses instead, because that centre is arithmetic and not a place.
Clicking it is precisely the failure [coordinate-spaces.md](coordinate-spaces.md) exists to
prevent.

A node's `name` and `value` are clamped to `tree-max-text`, with a `…` marking what was cut. They
are there to identify an element, not to read it: one terminal window otherwise contributes more
bytes than the other seventy nodes together. Matching is unaffected — a selector is resolved
against the full text, and only what is reported back is clamped.

## What is not on screen is counted, not expanded

Of the 73 nodes in one measured terminal window, **55 were the items of closed menus**: real,
operable through the platform, and not visible. Expanding them costs three quarters of the payload
before anybody asks.

So a subtree hanging off a node with no on-screen position is reported as a count:

```json
{"id": "0/0/0/0", "role": "menu", "name": "File",
 "actions": ["click", "select"], "box": [0, 32, 37, 28], "offscreen_children": 5}
```

`--of 0/0/0/0` expands it, exactly as a truncated subtree is re-entered. Nothing is hidden — the
count is right there — and **nothing is lost to a selector**: `click --name "Preferences"` still
resolves with the menu closed, because summarising decides what to *report*, not what exists. That
is the whole point of operating an element through the platform.

Measured: 73 nodes and 10,948 bytes become **24 nodes and 3,777 bytes**.

## `--full` is the escape hatch

One flag, and it means everything: no pruning, no node budget, every state, every field, every
subtree expanded. It is not a slightly-less-compact middle setting, and there is no second flag for
half of it.

**Truncation is never silent.** The result carries `truncated`, `node_count` and the ids that were
cut, and `--of ID` re-enters at any of them — so a truncated tree is a starting point, not a dead
end.

## When there is no tree, there is a screenshot

Some surfaces expose nothing: canvas apps, game engines, a remote framebuffer, an Electron build
with accessibility switched off. When `tree` has nothing to return it captures the screen instead
and says why:

| `reason` | Meaning |
| --- | --- |
| `unavailable` | No provider for this platform, or the backend cannot have one (vnc). |
| `denied` | The OS refused the accessibility permission. |
| `empty` | The provider works and the application exposes nothing. |

In each case the result carries the path of a screenshot it took for you, so handing it to
ui-locator costs no extra round trip. `--no-fallback` turns this off for a caller that wants
structure or an error and nothing else.

In one sentence: **an agent runs `tree` and either gets structure cheaply, or is told there is none
and handed the picture.**

## In a batch

`tree` is an action, so a batch can do click → tree and hand back the *new* state without a
screenshot. That is the cheapest feedback loop this tool offers — cheaper than change detection,
because it says *what* changed rather than merely *that* something did.

## Agent Notes

- Boxes and centres are **actuation** units, always. Never hand one back as screenshot pixels —
  that is the bug class [coordinate-spaces.md](coordinate-spaces.md) exists to prevent, and it is
  easy to miss because on a 1:1 display the two agree.
- Ids are paths in the **full** tree, not indices into the pruned one, or `--of` cannot re-enter a
  node that pruning removed.
- The node budget matters more than any other single decision here. Report truncation; never hide
  it.
