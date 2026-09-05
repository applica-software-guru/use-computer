"""Pruning, budgets and selector matching -- the policy over a tree, kept pure.

None of this touches a platform binding, which is deliberate: no CI runner has a session bus, a
logged-in desktop or an Accessibility grant, so the platform providers are unreachable there by
construction. Everything worth testing has to sit above them, and this is it.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from use_computer.errors import (
    AmbiguousNodeError,
    AmbiguousWindowError,
    NodeNotFoundError,
    UITreeUnavailableError,
)
from use_computer.tree import ActiveWindow, Box, NodeSelector, UINode, WindowInfo

#: Roles that are worth keeping even when the platform reports no actions and no name -- an
#: empty text field has nothing to say about itself and is still the thing an agent came for.
INTERACTIVE_ROLES = frozenset(
    {
        "button",
        "checkbox",
        "combobox",
        "link",
        "listitem",
        "menuitem",
        "radio",
        "scrollbar",
        "slider",
        "spinner",
        "tab",
        "text",
        "toggle",
        "treeitem",
    }
)

#: States that mean "the user cannot see this", whatever the geometry claims.
HIDDEN_STATES = frozenset({"offscreen", "hidden", "invisible"})

#: How many cut subtree roots to name. Truncation has to be reported, not re-enacted.
MAX_TRUNCATED_IDS = 50

#: How much of a node's own area its children must leave uncovered before it is worth saying so.
UNEXPOSED_FRACTION = 0.25

#: And how big that region must be on **both** sides.
#:
#: A blind spot is a region, not a sliver. Measured in GNOME Drawing: the canvas is 1754x883 and is
#: worth reporting; the 1213x44 of empty space to the right of the toolbar buttons, and the 1561x28
#: beside the menus, are decoration -- the platform describes nothing there because there is
#: nothing there. An area bound alone let both of those through, at 53,000 and 43,000 pixels.
UNEXPOSED_MIN_SIDE = 120

#: Appended to a name or value that was clamped, so a reader can tell.
ELLIPSIS = "\u2026"

#: States almost every node reports. A field that is nearly always the same says nothing, and a
#: tree carries thousands of them -- dropping these measured 26% of the payload.
UNREMARKABLE_STATES = frozenset(
    {"showing", "enabled", "focusable", "visible", "sensitive", "selectable"}
)


def walk(node: UINode) -> Iterator[UINode]:
    """Pre-order traversal, the order ids are assigned in."""
    yield node
    for child in node.children:
        yield from walk(child)


def count(node: UINode) -> int:
    return sum(1 for _ in walk(node))


def is_on_screen(node: UINode) -> bool:
    if HIDDEN_STATES & set(node.states):
        return False
    return node.box.positioned


def is_interactable(node: UINode) -> bool:
    if node.actions:
        return True
    if {"focusable", "editable"} & set(node.states):
        return True
    return node.role in INTERACTIVE_ROLES


def carries_text(node: UINode) -> bool:
    return bool(node.name) or bool(node.value)


def is_interesting(node: UINode) -> bool:
    """The default pruning rule.

    On-screen and either operable or saying something -- **or** operable through the platform
    wherever it is. The items of a closed menu have no position and are still the thing an agent
    came for: reaching "File > Preferences" without opening the menu first is the whole point of
    acting through the accessibility API.
    """
    if node.actions:
        return True
    if node.unexposed is not None:
        # The one thing on this node that no child can stand in for: where the platform is
        # describing nothing. Collapsing it away would delete the only sign a canvas exists.
        return True
    return is_on_screen(node) and (is_interactable(node) or carries_text(node))


def mark_active(
    entries: Sequence[WindowInfo], hint: ActiveWindow | None = None
) -> list[WindowInfo]:
    """Decide which single window is the active one, preferring what the window manager says.

    The flags cannot settle it. AT-SPI reports `active` per *application*, so on an ordinary
    desktop three windows claimed it at once. A window manager can settle it -- on X11
    `_NET_ACTIVE_WINDOW` names one window, by pid and title -- and where that answer exists it wins
    over the flags.

    The hint is a hint: absent on Wayland, absent without the binding, and wrong if an application
    renamed its window between the two reads. It never invents a mark, and when it matches nothing
    the flags decide exactly as before.
    """
    matched = _by_hint(entries, hint) if hint is not None else None
    if matched is None:
        return sole_active(entries)
    return [entry.model_copy(update={"active": entry.id == matched.id}) for entry in entries]


def _by_hint(entries: Sequence[WindowInfo], hint: ActiveWindow) -> WindowInfo | None:
    """The one window this hint names, or nothing -- never a first match."""
    candidates = [entry for entry in entries if hint.pid is not None and entry.pid == hint.pid]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return None
    named = [entry for entry in candidates if entry.title == hint.title]
    return named[0] if len(named) == 1 else None


def sole_active(entries: Sequence[WindowInfo]) -> list[WindowInfo]:
    """Leave the active mark on at most one window.

    The column answers exactly one question -- which window ``--window focused`` resolves to -- so
    it is that decision, made once. AT-SPI reports `active` per *application*, so on a desktop with
    several running programs three windows carried the mark at once, which answers nothing and is
    the first thing an agent is told to read.

    Measured on this desktop: neither `active` nor `focused` identifies the window on top, and
    neither does looking for a focused descendant. So when several claim it, **none** is marked.
    Saying nothing is worth more than a mark that is wrong two times in three.
    """
    claimed = [entry for entry in entries if entry.active]
    if len(claimed) == 1:
        return list(entries)
    return [entry.model_copy(update={"active": False}) for entry in entries]


def active_window(entries: Sequence[WindowInfo]) -> WindowInfo:
    """The window ``focused`` resolves to, or a refusal naming the candidates.

    Same refusal as an ambiguous title, for the same reason: picking the first match is how an
    agent ends up reading, clicking and verifying inside the wrong application, consistently.
    """
    claimed = [entry for entry in entries if entry.active]
    if len(claimed) == 1:
        return claimed[0]
    if not claimed:
        raise UITreeUnavailableError(
            "no window reports itself as active. Name one with --window TITLE, --window ID from "
            "`windows`, or --window @PID."
        )
    raise AmbiguousWindowError(
        "focused",
        claimed,
        "this platform reports `active` per application, so it cannot say which window is on "
        "top. Name one with --window ID from `windows`, --window TITLE, or --window @PID",
    )


def mark_unexposed(node: UINode) -> UINode:
    """Say where a node's children do not account for the node's own area.

    A tree can be rich, correct, and silent about the only region that matters. Measured in GNOME
    Drawing: a panel 1920 px wide whose single child covers 163, with the other 1757x885 -- the
    canvas -- in no tree at all, not pruned, not summarised, not truncated, and absent under
    ``--full`` as well. Nothing fired, because the provider worked and returned plenty.

    That is the ordinary shape of a drawing program, a map, a chart, a game or a PDF view: the one
    class of application for which "use the screenshot" is the right answer, and the one the tree
    served worst, because an agent could not tell it from a window that exposes everything.

    This runs on the **raw** snapshot, before pruning: a region hidden by our own pruning is not a
    region the platform failed to describe.
    """
    marked, _ = _mark(node)
    return marked


def _mark(node: UINode) -> tuple[UINode, bool]:
    """Mark this subtree, and say whether anything in it carries a mark.

    Only the **innermost** node is marked. A canvas nested three panels deep would otherwise be
    reported three times, and the outermost report is the least useful of them: the agent wants the
    smallest region it can point a screenshot at.
    """
    children = []
    deeper = False
    for child in node.children:
        marked, found = _mark(child)
        children.append(marked)
        deeper = deeper or found
    kids = tuple(children)
    region = None if deeper else _blind_spot(node, kids)
    return (
        node.model_copy(update={"children": kids, "unexposed": region}),
        deeper or region is not None,
    )


def _describes_itself(node: UINode) -> bool:
    """Whether the platform says anything about this node beyond that it is there."""
    return bool(node.name or node.value or node.actions)


def _blind_spot(node: UINode, children: Sequence[UINode]) -> Box | None:
    """The region of ``node`` that its positioned children leave undescribed."""
    if not node.box.positioned:
        return None

    # Positioned children only: an unpositioned child covers nothing, and must not be allowed to
    # hide a blind spot by contributing an arithmetic box.
    boxes = [child.box for child in children if child.box.positioned]

    left, top = node.box.x, node.box.y
    right, bottom = left + node.box.width, top + node.box.height
    if not boxes:
        # Nothing positioned underneath: the whole box is undescribed. That is the shape a drawing
        # surface actually has -- one positioned rectangle with no name, no value and no actions,
        # either childless or holding only the parts of a dialog that is not showing.
        if _describes_itself(node):
            return None  # a large named image is described; it is not a hole
        widest = node.box
    else:
        covered_left = max(left, min(box.x for box in boxes))
        covered_top = max(top, min(box.y for box in boxes))
        covered_right = min(right, max(box.x + box.width for box in boxes))
        covered_bottom = min(bottom, max(box.y + box.height for box in boxes))
        if covered_right <= covered_left or covered_bottom <= covered_top:
            return None
        strips = (
            Box(x=left, y=top, width=covered_left - left, height=node.box.height),
            Box(x=covered_right, y=top, width=right - covered_right, height=node.box.height),
            Box(x=left, y=top, width=node.box.width, height=covered_top - top),
            Box(x=left, y=covered_bottom, width=node.box.width, height=bottom - covered_bottom),
        )
        widest = max(strips, key=lambda box: box.width * box.height)

    if min(widest.width, widest.height) < UNEXPOSED_MIN_SIDE:
        return None
    own = node.box.width * node.box.height
    if not own or (widest.width * widest.height) / own < UNEXPOSED_FRACTION:
        return None
    return widest


def prune(root: UINode) -> UINode:
    """Drop what an agent cannot use, and collapse containers that only nest.

    An unpruned desktop tree is thousands of nodes; poured into an agent's context it is worse
    than the base64 screenshots this tool stopped returning, because it *looks* useful.

    The root survives regardless -- it is the thing that was asked for.
    """
    pruned = _prune_children(root)
    return pruned.model_copy(update={"children": pruned.children})


def _prune_children(node: UINode) -> UINode:
    kept: list[UINode] = []
    for child in node.children:
        kept.extend(_prune_node(child))
    return node.model_copy(update={"children": tuple(kept)})


def _prune_node(node: UINode) -> list[UINode]:
    """Return what this node contributes: itself, its children, or nothing."""
    reduced = _prune_children(node)
    if is_interesting(node):
        return [reduced]
    if len(reduced.children) == 1:
        # A container whose only contribution is nesting. Its child stands in for it, keeping
        # its own id -- ids are paths in the full tree, so they survive the collapse.
        return [reduced.children[0]]
    if reduced.children:
        # More than one surviving child: the container is now carrying structure, so it stays.
        return [reduced]
    return []


def budget(root: UINode, max_nodes: int) -> tuple[UINode, int, bool, tuple[str, ...]]:
    """Cap the tree at ``max_nodes``, reporting what was cut.

    Truncation is never silent: the ids of the subtrees that were dropped come back so
    ``--of ID`` can re-enter at any of them. A truncated tree is a starting point, not a dead end.
    """
    cut: list[str] = []
    remaining = max(max_nodes, 1)

    def take(node: UINode) -> UINode:
        nonlocal remaining
        remaining -= 1
        children: list[UINode] = []
        for child in node.children:
            if remaining <= 0:
                if len(cut) < MAX_TRUNCATED_IDS:
                    cut.append(child.id)
                continue
            children.append(take(child))
        return node.model_copy(update={"children": tuple(children)})

    total = count(root)
    if total <= max_nodes:
        return root, total, False, ()
    capped = take(root)
    return capped, count(capped), True, tuple(cut)


def notable_states(node: UINode) -> UINode:
    """Keep only the states that change a decision, and say when a control is disabled.

    The platforms report the *positive* -- ``enabled``, ``sensitive`` -- and simply stay silent
    when a control is not. An omitted field is therefore the one case an agent must not miss, so
    the absence is turned into a presence: ``disabled`` is synthesised rather than inferred.
    """
    states = set(node.states)
    kept = sorted(states - UNREMARKABLE_STATES)
    if states and not states & {"enabled", "sensitive"}:
        kept = sorted([*kept, "disabled"])
    return node.model_copy(
        update={
            "states": tuple(kept),
            "children": tuple(notable_states(child) for child in node.children),
        }
    )


def summarise_offscreen(node: UINode) -> UINode:
    """Count the descendants that are not on screen instead of expanding them.

    Of 73 nodes in one measured window, 55 were the items of closed menus: real, operable through
    the platform, and not visible. Expanding them costs three quarters of the payload before
    anybody asks for them.

    This decides what to *report*, never what exists -- a selector still resolves against the
    whole tree, so `click --name "Preferences"` keeps working with the menu closed. That is the
    thing this function could most easily break.
    """
    shown: list[UINode] = []
    hidden = 0
    for child in node.children:
        if child.box.positioned or _shows_something(child):
            shown.append(summarise_offscreen(child))
        else:
            hidden += count(child)
    return node.model_copy(
        update={"children": tuple(shown), "offscreen_children": hidden}
    )


def _shows_something(node: UINode) -> bool:
    """Whether anything in this subtree is on screen.

    An unpositioned node is not necessarily an unpositioned *subtree*. GTK reports the tab holding
    a drawing canvas at (-1, -1) with a 1x1 size while the canvas under it is 1754x883 and plainly
    visible -- counting that as an off-screen descendant hides the largest thing in the window.
    The closed-menu case is unaffected: its items have no positioned descendants either.
    """
    return any(descendant.box.positioned for descendant in walk(node))


def clamp_text(node: UINode, limit: int) -> UINode:
    """Bound the text a node carries into the caller's context.

    The node budget counts nodes, which is the wrong unit for this: a single terminal or editor
    reports its whole buffer as one value, and thirteen kilobytes from one node defeats a budget
    of four hundred. `name` and `value` identify an element; they are not a way to read its
    contents, and a tree that quietly became a document dump is the base64 mistake wearing a
    different hat.

    Applied on the way out, never before matching -- a selector must still see the full name.
    A limit of ``0`` means no clamping.
    """

    def clip(text: str | None) -> str | None:
        if text is None or limit <= 0 or len(text) <= limit:
            return text
        return text[:limit] + ELLIPSIS

    return node.model_copy(
        update={
            "name": clip(node.name),
            "value": clip(node.value),
            "children": tuple(clamp_text(child, limit) for child in node.children),
        }
    )


def subtree(root: UINode, node_id: str) -> UINode | None:
    """The node at ``node_id``, with everything under it. What ``--of`` re-enters at."""
    for node in walk(root):
        if node.id == node_id:
            return node
    return None


def matches(node: UINode, selector: NodeSelector) -> bool:
    if selector.node_id is not None and node.id != selector.node_id:
        return False
    if selector.role is not None and node.role != selector.role:
        return False
    if selector.name is not None:
        name = node.name or ""
        if selector.exact:
            if name != selector.name:
                return False
        elif selector.name.casefold() not in name.casefold():
            return False
    return True


def resolve_window(entries: Sequence[WindowInfo], wanted: str) -> WindowInfo:
    """Exactly one window, or an error carrying the ones that matched.

    An id is exact and a title is a substring, so a value that is one is never tested as the
    other. That ordering matters more than it looks: a terminal puts the running command in its
    own title, so the terminal executing ``--window "X"`` contains X and matches it. Picking the
    first would return the window the user is looking at rather than the one they named.

    This lives here rather than in a provider because it is policy. Three platforms would
    otherwise disagree about it, and two of them cannot be tested on this machine at all.

    Raises:
        UITreeUnavailableError: nothing matched.
        AmbiguousWindowError: several did, carrying them.
    """
    exact = [entry for entry in entries if entry.id == wanted]
    if exact:
        return exact[0]

    folded = wanted.casefold()
    matches = [entry for entry in entries if folded in (entry.title or "").casefold()]
    if not matches:
        raise UITreeUnavailableError(f"no window matches {wanted!r}.")
    if len(matches) > 1:
        raise AmbiguousWindowError(wanted, matches)
    return matches[0]


def find(root: UINode, selector: NodeSelector) -> list[UINode]:
    """Every node the selector matches, in tree order."""
    return [node for node in walk(root) if matches(node, selector)]


def resolve_one(root: UINode, selector: NodeSelector) -> UINode:
    """Exactly one node, or an error that says what to do next.

    Ambiguity is never resolved by picking the first match. Two buttons named "OK" in two
    dialogs is the ordinary case, and a silent choice fails a hundred runs later in a way nobody
    can reproduce.

    Raises:
        NodeNotFoundError: nothing matched -- the signal to drop to vision.
        AmbiguousNodeError: several matched, carrying the candidates to choose between.
    """
    candidates = find(root, selector)

    if not candidates and selector.node_id is not None:
        # An id that resolves to a node with a different role or name means the tree moved.
        # Say that, rather than "not found": the agent's next step is different.
        at_path = subtree(root, selector.node_id)
        if at_path is not None:
            raise NodeNotFoundError(
                f"{selector.describe()} -- the tree moved: {selector.node_id} is now "
                f"{at_path.describe()}. Re-read it with `tree`"
            )

    if not candidates:
        raise NodeNotFoundError(selector.describe())

    if selector.nth is not None:
        if selector.nth >= len(candidates):
            raise NodeNotFoundError(
                f"{selector.describe()} -- only {len(candidates)} candidate(s) matched"
            )
        return candidates[selector.nth]

    if len(candidates) > 1:
        raise AmbiguousNodeError(selector.describe(), candidates)

    return candidates[0]


__all__ = [
    "budget",
    "clamp_text",
    "find",
    "is_interesting",
    "matches",
    "notable_states",
    "prune",
    "resolve_one",
    "resolve_window",
    "subtree",
    "summarise_offscreen",
    "walk",
]
