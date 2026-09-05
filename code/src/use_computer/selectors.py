"""Pruning, budgets and selector matching -- the policy over a tree, kept pure.

None of this touches a platform binding, which is deliberate: no CI runner has a session bus, a
logged-in desktop or an Accessibility grant, so the platform providers are unreachable there by
construction. Everything worth testing has to sit above them, and this is it.
"""

from __future__ import annotations

from collections.abc import Iterator

from use_computer.errors import AmbiguousNodeError, NodeNotFoundError
from use_computer.tree import NodeSelector, UINode

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
    "find",
    "is_interesting",
    "matches",
    "prune",
    "resolve_one",
    "subtree",
    "walk",
]
