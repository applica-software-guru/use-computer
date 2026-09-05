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
from use_computer.tree import NodeSelector, UINode, WindowInfo

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
    return is_on_screen(node) and (is_interactable(node) or carries_text(node))


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
        if child.box.positioned:
            shown.append(summarise_offscreen(child))
        else:
            hidden += count(child)
    return node.model_copy(
        update={"children": tuple(shown), "offscreen_children": hidden}
    )


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
