---
title: "Entities"
status: synced
author: ""
last-modified: "2026-09-17T00:00:00.000Z"
version: "3.3"
---

# Entities

Every data model is a pydantic 2 model. **Result models are frozen** — once an action has run, what
it did does not change.

### CoordinateSpace

An enum: `screenshot` | `actuation`. The space a coordinate is expressed in.

### Coordinate

`x: int`, `y: int`, `space: CoordinateSpace`. A bare pair of numbers is never a coordinate; the
space travels with it.

### ScreenInfo

Reported by a backend about itself:

- `width`, `height` — size in actuation units
- `screenshot_width`, `screenshot_height` — size in screenshot pixels
- `scale: float | None` — the ratio; `None` means unknown, and coordinate conversion refuses
  rather than guessing

### MouseButton

`left` | `right` | `middle`.

### ScrollDirection

`up` | `down` | `left` | `right`.

### KeyCombo

A parsed key combination: `modifiers: tuple[str, ...]`, `key: str`, both canonical names. Produced
by parsing the normalised key syntax; backends map it to their own vocabulary.

### Box

`x`, `y`, `width`, `height`, `space: CoordinateSpace`. The geometry of a UI element. The
accessibility API reports it in **actuation** units.

**Serialises as `[x, y, width, height]`**, and parses from either that array or the object form.
The space is not repeated on every node because it is always `actuation`: the keys cost more than
the values, and a tree carries thousands of them.

### UINode

One element of the accessibility tree:

- `id: str` — a structural path in the **full** tree, e.g. `0/2/1/3`
- `role: str` — canonical, normalised across platforms
- `name: str | None`, `value: str | None`
- `states: tuple[str, ...]` — canonical state names. On the way out only the **notable** ones
  survive: what almost every node reports (`showing`, `enabled`, `focusable`, `visible`,
  `sensitive`, `selectable`) says nothing and is dropped, while `checked`, `selected`, `expanded`,
  `modal` and the rest stay. **`disabled` is synthesised** when `enabled` is absent — the platforms
  report the positive and stay silent on the negative, which is the one case an agent must not miss
- `offscreen_children: int` — descendants not on screen, counted rather than expanded; `0` when
  there are none, or when they were expanded
- `actions: tuple[str, ...]` — the action names this node supports; empty means it can only be
  clicked by coordinate
- `box: Box`, `center: Coordinate`
- `unexposed: Box | None` — the region of this node's own box that its children do not account
  for: where the platform is describing nothing, which is where a canvas lives. Computed from
  positioned children only, set when the largest uncovered strip is at least 25% of the node and at
  least 10,000 square pixels, and `None` on a node with no positioned children — a leaf is not a
  container that failed to describe itself
- `children: tuple[UINode, ...]`

### WindowsResult *(frozen)*

What `windows` returns: `text: str | None` — the rendering — and `windows: tuple[WindowInfo, ...]`,
populated under `--format json`. Symmetrical with `TreeResult`, so the two reads look alike.

### WindowInfo *(frozen)*

One entry of what `windows` returns: `id`, `title: str | None`, `role`, `app: str | None`,
`pid: int | None`, `box: Box`, `active: bool`.

`active` is true for **at most one** window in a list: it answers which window `--window focused`
resolves to, so it is that decision, made once. A platform that reports `focused` per application
marks several at a time, which is not an answer — and where a window manager can be asked
(`ActiveWindow`), its answer settles it instead of the flags.

`app` is the application the window belongs to. Without it a candidate list is unreadable: two
windows both titled "ChatGPT" are told apart by what they belong to, not by the title that made
them ambiguous.

`pid` lives here and on nothing else. A window list is where it is worth its bytes; on every node
of a tree it is repetition.

### ActiveWindow *(frozen)*

What a window manager can say about the window in front: `pid: int | None`, `title: str | None`.
A hint, never a decision — the matching to a `WindowInfo` is policy and lives in `selectors.py`.

### TreeScope

What to snapshot: `kind: focused | all | title | pid` with an optional `value`. Parsed from
`--window`, where `@1234` means a pid and anything else a title.

### TreeReason

An enum: `unavailable` | `denied` | `empty`. Why a tree could not be returned — no provider for
this platform or backend, the OS refused the permission, or the application exposes nothing.

All three describe **the application or the platform**. A limit the caller asked for is never one of
them: a tree emptied by `--depth`, by pruning or by the node budget names that limit instead,
because `empty` is what tells an agent to stop reading trees and pay for vision.

### TreeResult *(frozen)*

- `root: UINode | None`
- `node_count: int`, `truncated: bool`, `truncated_ids: tuple[str, ...]`
- `text: str | None` — the rendering, with its legend line. Present unless `--format json`
- `reason: TreeReason | None` — set only when `root` is `None`
- `screenshot: Screenshot | None` — the fallback capture, when one was taken
- `path: Path | None` — where the tree was written, when `--out` asked for a file; `root` is then
  omitted, which is the point of asking

### NodeSelector

How an action names an element: `node_id: str | None`, `role: str | None`, `name: str | None`,
`exact: bool`, `nth: int | None`, `window: TreeScope`. At least one of `node_id`, `role` or `name`
must be set.

### Via

An enum: `auto` | `action` | `coordinate`. Which rung an element-addressed action should take;
`ActionResult.via` records which one it actually took, and is never `auto`.

### Action

A discriminated union on `action`, with one variant per member of the action set:

`MoveAction`, `ClickAction`, `DoubleClickAction`, `RightClickAction`, `DragAction`,
`ScrollAction`, `TypeAction`, `KeyAction`, `ScreenshotAction` (which also carries `of`, `pad` and `window` for cropping to an element),
`TreeAction`, `FocusAction`,
`ToggleAction`, `ExpandAction`, `CollapseAction`, `SelectAction`, `SetValueAction`,
`ShowMenuAction`, `WindowsAction`, `ActivateAction`.

Fields common to all: `delay: float | None`, `verify: bool`.
Positional variants carry `Coordinate`s; `TypeAction` carries `text` and an optional rate;
`KeyAction` carries a `KeyCombo`; `SetValueAction` carries `value`.

`TypeAction` and `SetValueAction` carry **either** their literal (`text` / `value`) **or**
`secret: str` naming an entry in the secret store, never both, and never neither — a validator
rejects both pairings the way the coordinate-or-selector one does.

**The action never holds the credential.** It holds the name; the store is read by the runner at
the moment of sending, and the value exists as a plain string only in that call. This is what makes
every rendering, serialisation and traceback safe by construction rather than by remembering, and
it is a stronger guarantee than masking a field would be: there is no field to mask.

`ActivateAction` carries a `TreeScope` and nothing else: its target is a window, not an element and
not a point. `MoveAction`, `ClickAction`, `DoubleClickAction`, `RightClickAction`, `DragAction` and
`ScrollAction` carry an optional `window: TreeScope | None` used when they are addressing a
coordinate — the window that coordinate belongs to, brought forward before it is sent.

The discriminator accepts the hyphenated CLI spelling as well as the underscored one, so
`set-value` and `set_value` name the same variant.

Element-addressable variants carry `selector: NodeSelector | None` and `via: Via`.
`ClickAction`, `DoubleClickAction`, `RightClickAction` and `ScrollAction` accept **either** a
coordinate or a selector, never both — a validator rejects the pair rather than deciding which
wins. `FocusAction`, `ToggleAction`, `ExpandAction`, `CollapseAction`, `SelectAction`,
`SetValueAction` and `ShowMenuAction` require a selector and take no coordinate at all.

### Screenshot

`path: Path`, `width`, `height`, `space`, `captured_at`, and — when it was cropped to an element —
`of: str | None` (the node id) and `box: tuple[int, int, int, int] | None` (the crop, in screenshot
pixels).

A screenshot that has been surfaced to the caller always has a path: it is a file. `data` is held
in memory only while a comparison needs it, is never serialised, and never crosses the JSON
boundary.

### ChangeReport

The outcome of change detection: `changed: bool`, `magnitude: float` (fraction of differing
pixels), `threshold: float`, `bbox: tuple[int, int, int, int] | None`.

`bbox` is present whenever `changed` is true, and it is what the text form reports: a box can be
compared against what the agent expected to happen, and a percentage cannot. It is computed before
the verdict, because it is what decides — `changed` is true when the box's **longest side** reaches
16 screenshot pixels, or the fraction clears the threshold. Extent rather than a pixel count keeps
a drawn stroke and a ticked checkbox from being reported as nothing, which is the error that costs
an agent a correct coordinate, while a 2x8 caret stays noise.

### ActionResult *(frozen)*

- `action` — the action as requested
- `resolved` — coordinates converted into actuation units
- `performed: bool` — false under dry-run
- `duration_ms: float`
- `change: ChangeReport | None`
- `screenshot: Screenshot | None`
- `tree: TreeResult | None` — for `tree`
- `windows: WindowsResult | None` — for `windows`
- `matched: UINode | None` — the node a selector resolved to
- `via: Via | None` — the rung actually taken; `action` or `coordinate`, never `auto`
- `typed: int | None` — characters sent; the only report a secret leaves behind
- `verify_skipped: bool` — verification was in force and was refused, because the
  after-screenshot of an action carrying a secret is a photograph of the credential
- `error: ErrorInfo | None`

### RunResult *(frozen)*

One per invocation, and what the CLI serialises to stdout:

- `profile: str`
- `backend: str`
- `screen: ScreenInfo`
- `results: list[ActionResult]`
- `ok: bool`
- `failed_index: int | None`

### BackendProfile

A named entry in `config.toml`: `name`, `backend` (`local` | `vnc`), plus backend-specific
fields (`host`, `port`, `password` for vnc; `allow_local` for local) and an optional explicit
`scale`.

### Settings

The pydantic-settings model, env prefix `USE_COMPUTER`. Holds the resolved configuration plus, for
each field, the **layer** it came from — which is what `config show` prints.

### StoredSecret

One entry in the secret store: `name: str`, `value: SecretStr`, `set_at: datetime`, and `store`
(`global` | `project`) — which of the two files it was found in, filled by the reader rather than
written to disk.

`value` is a `SecretStr` from the moment it is decrypted, so it masks itself in `repr`, in a log
line and in a traceback. `FileStore` is the `0600` TOML implementation, and `Secrets` is the
resolver over the two of them plus the environment — `get`, `require`, `entries`. An OS keychain is
a second `FileStore`-shaped implementation, which is why the CLI never names a file.

**The cipher lives inside `FileStore`.** `Secrets`, the runner and the CLI never hold a key and
never see a ciphertext, so the store's interface is the same one a keychain would satisfy. The key
itself is resolved by `key_path()` against the XDG *data* directory, minted lazily on a write, and
`SecretUnreadableError` is what a failed decrypt raises — never `InvalidToken`, which names a
library to a caller who is mid-task and cannot see the code.

There is deliberately **no** method that returns every value at once: the store is read one name at
a time, by the action that is about to type it. `entries()` returns `SecretEntry` objects, which
have no `value` field to omit.

### Errors

`UseComputerError` (base) → `BackendNotAvailableError` (names the extra to install),
`PermissionDeniedError` (names the OS permission), `CoordinateSpaceError` (unknown or inconsistent
scale), `KeySyntaxError`, `ConfigError`, `ActionFailedError`,
`UITreeUnavailableError` (no provider — names both the extra and, on Linux, the system package),
`NodeNotFoundError` (nothing matched), `AmbiguousNodeError` (carries the candidates),
`AmbiguousWindowError` (carries the matching `WindowInfo`s),
`ActionNotSupportedError` (names the actions the matched node does support),
`SecretNotFoundError` (names the missing secret and the command that stores it — and never the
names that do exist, which would read as a list to try),
`SecretUnreadableError` (a stored value did not decrypt: written before encryption, or the key is
gone — one message, because the remedy is the same and the two are indistinguishable),
`SecretNameError` (a name that would not survive being a TOML key or an environment variable).

## Agent Notes

- Frozen means `model_config = ConfigDict(frozen=True)` on every result model.
- The `Action` union is discriminated on the literal `action` field so a batch JSON file parses
  into typed variants in one `TypeAdapter` call.
- `AmbiguousNodeError` carries the candidate `UINode`s, not a formatted string. The CLI renders
  them; the Python API hands them over as objects.
- `UINode.children` is a tuple and every result model is frozen, so a tree can be shared between an
  action's resolution step and the result it reports without anyone mutating it in between.
