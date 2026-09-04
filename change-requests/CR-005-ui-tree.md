---
title: "The UI tree, not just pixels"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# The UI tree, not just pixels

## Why

Today the only way an agent learns what is on the screen is a screenshot, and a screenshot has to
be *looked at* — by a vision model, or by ui-locator. That is the expensive path, and on a great
many screens it is the *wrong* path: the operating system already knows there is a button at
(412, 260) labelled "Invia", enabled, inside a dialog titled "Conferma". Making a vision model
rediscover that from pixels costs tokens, latency and accuracy — the mislocated coordinate is
exactly the failure the OS would never have made.

`use-computer` is the half of the pair that touches the machine. It is therefore the half that can
*ask* the machine. It should.

Pixels stay necessary. Canvas apps, game engines, a remote framebuffer, an Electron build with
accessibility switched off — none of them expose anything. So the tree does not replace the
screenshot; it demotes it. The order becomes **ask the tree first, look at the picture only when
the tree cannot answer**.

## What changes

### `use-computer tree`

A new command, and a new member of the action set:

```
use-computer tree [--window focused|all|TITLE|@PID] [--depth N]
                  [--role ROLE] [--name TEXT] [--all] [--of NODE_ID]
                  [--out PATH] [--no-fallback]
```

By default it snapshots the **focused window**, not the desktop, and returns a pruned tree. Every
node carries what an agent needs to act:

```json
{
  "id": "0/2/1/3",
  "role": "button",
  "name": "Invia",
  "value": null,
  "states": ["enabled", "focusable", "showing"],
  "box": {"x": 412, "y": 260, "width": 88, "height": 32, "space": "actuation"},
  "center": {"x": 456, "y": 276, "space": "actuation"},
  "children": []
}
```

`center` is the payoff: the agent goes straight from `tree` to
`click --x 456 --y 276 --space actuation`, with no picture and no vision model in between.

### Pruning is the feature, not a detail

An unpruned AT-SPI desktop tree is thousands of nodes. Dumped into an agent's context it is worse
than the base64 that [CR-004](CR-004-screenshots-are-files.md) removed, because it *looks* useful.

The default keeps a node when it is on-screen and either **interactable** (an actionable role, or
focusable/editable) or **carries text** (a name, a label, a value). A container whose only
contribution is nesting is collapsed into its child. A node budget caps the result.

Truncation is never silent. The result reports `truncated`, `node_count`, and the ids that were cut
— and `--of NODE_ID` re-enters at any of them, so a truncated tree is a starting point rather than
a dead end. `--all` disables pruning and the budget for the caller who really wants everything.

### The screenshot becomes the fallback, and says so

When `tree` has nothing to return it captures the screen instead and says why, in one JSON object:

- `unavailable` — no provider for this platform, or the backend cannot have one (vnc);
- `denied` — the OS refused the accessibility permission;
- `empty` — the provider works and the application exposes nothing.

In every one of those cases the result carries the path of a screenshot it took for you, so the
agent's next move — hand it to ui-locator — costs it no extra round trip. `--no-fallback` turns
this off for a caller that only wants structure or an error.

This is the whole shape of the change in one sentence: **an agent runs `tree` and either gets
structure cheaply, or gets told there is none and handed the picture.**

### A capability beside the backend, not inside it

The vnc backend can never do this — RFB carries pixels and nothing else. So this is not a method on
the `Backend` Protocol; it is a second, optional Protocol with its own module tree:

```
accessibility/
  base.py    AccessibilityProvider Protocol + UITreeUnavailableError
  atspi.py   Linux   — AT-SPI 2
  uia.py     Windows — UI Automation
  ax.py      macOS   — AXUIElement
```

The provider is chosen by the **running platform**, never by config — a profile does not get to
claim macOS accessibility on Linux. The `local` backend resolves the one for its platform; `vnc`
resolves none and says so.

A new extra carries the bindings, with per-platform environment markers:

```bash
pip install "use-computer-cli[local,tree]"
```

| Platform | Binding | Why this one |
| --- | --- | --- |
| Windows | **`uiautomation >= 2.0`** | Pure Python over comtypes, no compiler; released 2.0.29 in August 2025, so it is alive. |
| macOS | **`pyobjc-framework-ApplicationServices >= 10`** | `AXUIElement` straight from the source, no wrapper in between; released 12.2.2 in August 2026. |
| Linux | **`PyGObject >= 3.46`** + the system `Atspi` typelib | The supported AT-SPI binding. See the caveat below — this is the one that is not purely a pip install. |

Linux is the awkward one and the docs must say so plainly. There is no `pyatspi` on PyPI: the
Python AT-SPI bindings ship as a distro package (`gir1.2-atspi-2.0`, plus `python3-pyatspi` on
Debian and Ubuntu), and PyGObject reaches them through GObject Introspection. `pip install` alone
therefore cannot finish the job on Linux, and `UITreeUnavailableError` must name **both** halves —
the extra and the system package — because the agent reading that message is the one that has to
get unstuck.

### `tree` in a batch

`TreeAction` joins the discriminated action union, so a batch can do click → tree and hand the
agent the *new* state without a screenshot — which is the cheapest feedback loop this tool can
offer, cheaper even than change detection, because it says *what* changed and not merely *that*
something did.

## Deliberately not done

**No acting on a node id.** `click --node 0/2/1` stays out. A node id is valid only for the
snapshot it came from, and an agent clicking a stale id gets a wrong click wearing a
confident-looking argument. The agent takes `center` and clicks a coordinate, under the same
coordinate contract as everything else here.

Invoking a node through the accessibility API itself (AT-SPI `do_action`, UIA `Invoke`) is a real
and more reliable thing to want, and it answers the staleness objection by resolving against a live
tree rather than an old snapshot. That is [CR-006](CR-006-element-addressing.md), which builds on
this one: there, `click` itself accepts an element handle alongside `--x/--y`, and `UINode` gains
an `actions` field. The Protocol is called `AccessibilityProvider` here rather than
`UITreeProvider` for that reason — it will not only read, and a name that has to be corrected one
change request later is a name that was wrong when it was chosen.

**No query language.** `--role` and `--name` are filters. Not XPath, not CSS. An agent that needs
more reads the tree it already has.

**No waiting.** No `--wait-for`, no polling until an element appears. `use-computer` is not a test
runner.

**No caching between runs.** A tree is a snapshot of a moment. A stale one is more dangerous than
no tree at all.

**No DOM, no CDP.** A browser's interior is whatever it chooses to expose through the platform
accessibility API. Chrome sometimes needs `--force-renderer-accessibility`; that is worth
documenting and not worth working around.

**Not dogtail, and not atomacos.** dogtail is the obvious Linux shortcut and is GPLv2 — fine for a
test harness that runs it, wrong for a permissively licensed library that imports it. atomacos
would have saved the pyobjc plumbing on macOS, but its last release is 3.3.0 from May 2021; that
is the same staleness argument that already ruled out pyautogui, and it should be applied
consistently or not at all.

**Not the pure-D-Bus route on Linux.** Speaking `org.a11y.atspi` directly would avoid a system
typelib, and it is a lot of work for a protocol that is chatty enough to be slow either way. The
supported binding wins; the error message pays the cost by naming the system package.

## Documentation to update

- `product/vision.md` — the boundary between the pair moves. `use-computer` now answers *where*
  when the OS will say so; ui-locator is for when pixels are all there is. The non-goal narrows
  from "element detection" to **visual** element detection.
- `product/features/ui-tree.md` — **new**. Scoping, pruning, the node shape, the fallback.
- `product/features/actions.md` — `tree` joins the action set.
- `product/features/backends.md` — the tree as a capability the local backend has per platform and
  vnc structurally cannot; the `tree` extra.
- `product/features/cli.md` — the `tree` command and its flags.
- `product/features/coordinate-spaces.md` — accessibility boxes arrive in actuation units.
- `product/features/configuration.md` — `tree-max-nodes`, `tree-depth`, `tree-fallback`.
- `system/entities.md` — `UINode`, `Box`, `TreeScope`, `TreeResult`, `TreeAction`,
  `UITreeUnavailableError`.
- `system/interfaces.md` — the `AccessibilityProvider` Protocol, the CLI contract, the tree JSON.
- `system/architecture.md` — the `accessibility/` package and platform module selection.
- `product/features/skill.md` — the bundled skill has to teach `tree` before `screenshot`, and its
  `x-skill-version` marker bumps so installed copies report as outdated.
- `system/tech-stack.md` — the `tree` extra: `uiautomation >= 2.0` on Windows,
  `pyobjc-framework-ApplicationServices >= 10` on macOS, `PyGObject >= 3.46` on Linux, each behind
  a `sys_platform` marker, with the Linux system-package caveat recorded next to the pin.

## Agent Notes

- Boxes and centers are **actuation** units, always. An accessibility box must never be handed back
  as screenshot pixels — that is precisely the bug class `coordinate-spaces` exists to prevent, and
  it is easy to get wrong because on a 1:1 display the two agree.
- The node budget matters more than any single feature here. Report truncation; never hide it.
- Import the platform binding **inside the provider's constructor**, never at module import. Same
  rule as the backends, and the same consequence if broken: `use-computer --help` stops working on
  a machine without the extra.
- Linux: GTK applications expose AT-SPI only when the accessibility bus is running. When
  `org.a11y.Bus` is absent, say how to turn it on — an empty tree that means "you have it switched
  off" is the worst possible answer.
- macOS: this needs the same Accessibility permission the local backend already needs. Reuse
  `PermissionDeniedError` and name the permission.
- Tests get a **fake tree provider** alongside the fake backend, returning a canned tree. No CI
  runner has a session bus, a logged-in desktop or an Accessibility grant, so every platform
  provider is unreachable there by construction: the pruning, the budget, the id paths and the
  fallback are what the suite actually covers, and they are also where the bugs will be.
- A pruned tree still round-trips: the id of a pruned node must remain addressable through `--of`,
  which means ids are structural paths in the **full** tree, not indices into the pruned one.
