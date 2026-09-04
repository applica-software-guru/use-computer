---
title: "Address an element by handle or by pixel, through one action set"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# Address an element by handle or by pixel, through one action set

## Why

[CR-005](CR-005-ui-tree.md) lets an agent *read* the interface without looking at it. This one lets
it *use* the interface without aiming at it.

With the tree alone the loop is still: read the tree, take a `center`, click that coordinate. That
works, and it throws away most of what the tree just told us. A coordinate click has to be aimed,
so it depends on the scale being known; it moves the user's real pointer; it fails on an element
scrolled out of view that the OS would happily activate; and there is a race in the gap between
reading the coordinate and clicking it, during which the layout can move.

The accessibility API answers all four: ask the button to press itself. No coordinate, no pointer,
no aiming, no gap.

So the ladder gets a rung at the top, and vision sinks to the bottom where it belongs:

1. **element, through the platform API** — the OS performs the action. No coordinates at all.
2. **element, by coordinate** — the tree can see it but exposes no usable action, so click its
   centre. Very common: custom-drawn widgets expose a name and nothing else.
3. **pixel, from vision** — no such element in the tree. Screenshot → ui-locator → click x,y.

Each rung is cheaper, faster and more accurate than the one below. Today every interaction starts
on rung three. **Rung three does not go away and is not deprecated** — it is the floor the whole
ladder stands on, and it must keep working exactly as it does now.

## What changes

### Addressing, not a new command

There is no `act` command and no `--do <verb>` parameter. The action set already made this
decision: `actions.md` keeps `double_click` and `right_click` as distinct actions rather than
parameters of `click`, "because that is how the calling agent thinks about them". A verb hidden
behind `--do` is the same mistake in a new place.

Instead, **every action that targets an element accepts either addressing mode**:

```bash
use-computer click --x 120 --y 340              # rung 3 — a pixel, from vision
use-computer click --id 0/2/1/3                 # a handle from `tree`
use-computer click --role button --name "Invia" # a description, resolved live
```

All three are permanent, supported paths. The first is what an agent uses when the tree cannot see
the element; the other two are what it uses when the tree can.

### The rule for which actions take a selector

| | Addressing |
| --- | --- |
| `click`, `double_click`, `right_click`, `scroll` | coordinate **or** element |
| `focus`, `toggle`, `expand`, `collapse`, `select`, `set_value`, `show_menu` | element only |
| `move`, `drag` | coordinate only — they aim a pointer, that is their whole meaning |
| `type`, `key` | neither — they target **the focus**, not an element |
| `screenshot`, `tree` | neither |

`type` deliberately takes no selector. `type --id X` would have to mean "focus it, then type",
and silent chaining is how automation becomes unreproducible. Focus it yourself, or use
`set_value`.

### New actions, as peers in the flat set

The verbs with no coordinate form join the action set directly: `focus`, `toggle`, `expand`,
`collapse`, `select`, `set_value`, `show_menu`. Each maps onto the three platforms the way key
syntax already maps onto every backend:

| Action | AT-SPI | UI Automation | macOS AX |
| --- | --- | --- | --- |
| `click` (rung 1) | `Action.do_action` (`click`/`press`/`activate`) | `InvokePattern` | `AXPress` |
| `focus` | `Component.grab_focus` | `SetFocus` | set `AXFocused` |
| `toggle` | `Action` (`toggle`) | `TogglePattern` | `AXPress` on a checkbox |
| `expand` / `collapse` | `Action` (`expand`/`collapse`) | `ExpandCollapsePattern` | `AXPress` on the disclosure |
| `select` | `Selection` | `SelectionItemPattern` | set `AXSelected` |
| `set_value` | `EditableText` / `Value` | `ValuePattern` | set `AXValue` |
| `scroll` (rung 1) | `Component` scroll-to | `ScrollItemPattern` | `AXScrollToVisible` |
| `show_menu` | `Action` (`menu`) | — | `AXShowMenu` |

`set_value` is not `type`, and the docs must say so where an agent will read it: `set_value`
assigns the text atomically and emits **no keystrokes**, which is faster and which some
applications ignore, because their validation only fires on key events. `type` emits real
keystrokes into whatever holds focus. Both are correct; they are correct for different fields.

### `--via` decides which rung, and the result says which one it used

On an element-addressed action:

- `--via auto` (default) — the platform API if the node supports it, otherwise a click at its
  centre;
- `--via action` — rung one only; error rather than fall back;
- `--via coordinate` — resolve the element, then click its centre with a real pointer. This exists
  because some interfaces only respond to genuine pointer input (hover states, drag affordances,
  canvas handlers), and an agent needs to be able to insist.

Every result carries the rung actually taken: `"via": "action" | "coordinate"`. An agent that
ignores it still works; one that reads it learns which parts of an application are structurally
addressable and stops paying for vision on the parts that are not.

### Resolution is strict, and that is the point

A selector resolves against a tree read **at the moment of the action**, never against an old
snapshot — which is what makes handles safe here where CR-005 refused them.

- **exactly one match** — perform it;
- **no match** — error, plus the CR-005 screenshot fallback, because "the tree cannot see it" is
  exactly the signal to drop to rung three;
- **more than one match** — error listing every candidate with role, name, id and box.

Refusing on ambiguity is a feature. Two buttons named "OK" in two dialogs is the ordinary case, and
a tool that silently picks the first fails a hundred runs later in a way nobody can reproduce. It
hands back the candidates; the agent narrows with `--name`, `--window` or `--nth`. Same stance the
tool already takes when the coordinate scale is unknown: **refuse rather than guess.**

`--id` is an accelerator and is **fingerprint-checked**: the node still at that path must still
carry the same role and name, or the action refuses and says the tree moved underneath it. A path
is not an identity — a row inserted above shifts every index below it.

### The tree advertises what each node can do

`UINode` gains `actions: list[str]` — the action names this node actually supports. That is what
makes rung one discoverable instead of guesswork: the agent reads
`{"role": "button", "name": "Invia", "actions": ["click", "focus"]}` and knows before it tries.
An empty list is the visible signal that this node is a rung-two node.

### Coordinates stop being mandatory

Rung one uses no coordinates, so an element-addressed action with `--via action` succeeds on a
display whose scale factor is unknown — the one situation where this tool otherwise refuses to do
anything at all. That is a property worth stating in the docs, not an implementation accident.

### In a batch, an interaction can now contain no coordinates at all

```json
[
  {"action": "focus",     "role": "text",   "name": "Destinatario"},
  {"action": "type",      "text": "mario@example.com"},
  {"action": "click",     "role": "button", "name": "Invia"},
  {"action": "tree"}
]
```

One connection, one live resolution per action, and a closing `tree` that hands back the resulting
state — no screenshot anywhere in the loop.

### The skill must teach the ladder, or none of this is reachable

`code/src/use_computer/skill/SKILL.md` is the only thing that makes any of this usable by the agent
it was built for, and it currently teaches exactly one method: get coordinates from ui-locator and
click them. Left alone, it would keep every agent on rung three while the other two rungs sat
unused in the binary.

It gains, in this order, because order is instruction:

1. **Start with `tree`, not `screenshot`.** The opening decision procedure becomes: read the tree;
   act on what you find; reach for a screenshot and ui-locator only when the tree cannot see it.
2. **Both addressing modes**, with a worked example of each, and the explicit statement that pixel
   coordinates remain correct and supported for rung three.
3. **`set_value` versus `type`**, since choosing wrong here fails silently in real applications.
4. **What the errors mean** — ambiguity hands back candidates to choose from; no-match is the
   signal to switch to vision, and it already includes the screenshot path.

Its frontmatter `x-skill-version` bumps to `"2"`, so `use-computer skill status` reports every
already-installed copy as outdated rather than leaving agents on stale instructions. The
`description` line also has to change: it currently promises only pointer and keyboard input, and
that line is what an agent reads when deciding whether this skill is relevant at all.

### The Protocol gains the acting half

`AccessibilityProvider` — named that way in CR-005 precisely because of this change request — gains
`perform(node_ref, action, value) -> bool`. It returns whether the platform actually carried the
action out, so the rung-two fallback triggers on a refusal and not only on an exception.

## Deliberately not done

**No waiting.** No `--wait-for`, no retry until a node appears. Resolution happens once against the
tree in front of it. An agent that needs to wait re-runs `tree`.

**No selector language.** `--role`, `--name`, `--nth`, `--window`. Not XPath. When those are not
enough, read the tree and use `--id`.

**No chained repair.** Nothing scrolls an element into view, dismisses an overlay, or focuses a
parent window to make an action work. One action, or an explanation.

**No tree-diff verify.** Comparing trees before and after would be a better change signal than
comparing pixels — it says *what* changed rather than *that* something did. It is also a whole
feature with its own noise problems, and it deserves its own change request.

**Nothing on vnc.** RFB carries no accessibility, so an element-addressed action on a vnc profile
errors immediately and the agent uses coordinates. No emulation, no pretending.

## Documentation to update

- `product/vision.md` — the ladder, near the top: element through the API, element by coordinate,
  pixel from vision. It is what the tool now is.
- `product/features/actions.md` — the seven new actions; the addressing table; `set_value` versus
  `type`; `--via`.
- `product/features/element-addressing.md` — **new**. Selectors, resolution rules, ambiguity,
  fingerprinted ids, the rungs and what `via` reports.
- `product/features/ui-tree.md` — nodes advertise their `actions`.
- `product/features/cli.md` — the new commands and the shared selector flags.
- `product/features/coordinate-spaces.md` — rung one needs no coordinates, and therefore no scale;
  pixel addressing is unchanged.
- `product/features/skill.md` — a "what the skill teaches" section: the ladder is its primary
  decision procedure, and the version marker bumps when that guidance changes.
- `product/features/safety.md` — element actions under dry-run; `focus` is a real side effect;
  acting on an application that is not frontmost.
- `system/entities.md` — `NodeSelector`, `Via`, the seven new `Action` variants, `ActionResult.via`
  and `matched`, `AmbiguousNodeError`, `NodeNotFoundError`, `ActionNotSupportedError`;
  `UINode.actions`.
- `system/interfaces.md` — `AccessibilityProvider.perform`, the CLI contract for the new actions
  and flags, the JSON shapes, the coordinate-free batch example above.
- `system/architecture.md` — action normalisation beside key normalisation in `accessibility/`;
  selector resolution as its own pure, testable module.

## Agent Notes

- **Ambiguity is an error, never a first match and never a "best" match.** The candidate list is
  the useful part of that error: role, name, id and box for each, so the agent chooses without a
  second round trip.
- Pixel addressing must not regress. It is rung three, it is the floor, and every change here is
  additive to it — an agent holding coordinates from ui-locator behaves exactly as it does today.
- `--dry-run` must still **resolve**, and report the node it would have acted on and the `via` it
  would have used. A dry run that skips resolution tells the agent nothing it did not know.
- Acting through the API moves no pointer and paints no hover state, so `--verify`'s pixel
  comparison sees less change than a coordinate click would for the same outcome. A small
  `magnitude` must not be read as failure; say so where change detection is documented.
- `focus` has consequences — it takes focus from whatever the user was doing, and on the local
  backend that is their real desktop. `click --via action` must not quietly focus first to make
  itself work; if a toolkit requires focus, say so rather than doing it invisibly.
- macOS AX will act on an application that is not frontmost. Genuine advantage, genuine footgun,
  document both.
- `perform` returns a boolean because several of these APIs report failure by returning false
  rather than raising. A provider that only catches exceptions will report success for actions that
  did nothing at all.
- The skill is package data and ships in the wheel; CI already gates the release on its presence.
  Bumping `x-skill-version` without updating the body, or the reverse, leaves `skill status` lying.
