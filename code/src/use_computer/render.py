"""One line per node, with a legend -- what the calling agent actually reads.

Bytes were the wrong unit. Measured on one window in *tokens*, which is what an agent pays:
the structured JSON of that tree cost 1,707, the same tree rendered here cost 555. JSON's cost is
not verbosity but that ``{``, ``"``, ``:``, ``,`` and every repeated key are each their own token,
so ``"role": "button"`` spends five of them to say one thing -- and a tree says it thousands of
times.

This module formats and decides nothing. Pruning, the node budget, the notable-state filter and
the off-screen summary have all run by the time it sees a tree, which is why it stays a page long
and tests against a literal string.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from use_computer.tree import UINode, WindowInfo

TREE_LEGEND = '# id role "name" !states [actions] x,y wxh +offscreen'
WINDOWS_LEGEND = '# id role "title" pid x,y wxh *active'


def _quote(text: str) -> str:
    """Keep a name on one line, and keep its quotes from ending it early.

    Minimal on purpose: a format that needs a parser has lost the argument it was making.
    """
    flattened = " ".join(text.split())
    return '"' + flattened.replace('"', '\\"') + '"'


def _node_line(node: UINode, depth: int) -> str:
    parts = ["  " * depth + node.id, node.role]
    if node.name:
        parts.append(_quote(node.name))
    if node.value:
        parts.append("=" + _quote(node.value))
    if node.states:
        parts.append("!" + ",".join(node.states))
    if node.actions:
        parts.append("[" + ",".join(node.actions) + "]")
    box = node.box
    parts.append(f"{box.x},{box.y} {box.width}x{box.height}")
    if node.offscreen_children:
        parts.append(f"+{node.offscreen_children}")
    return " ".join(parts)


def _walk(node: UINode, depth: int = 0) -> Iterable[tuple[UINode, int]]:
    yield node, depth
    for child in node.children:
        yield from _walk(child, depth + 1)


def tree(root: UINode) -> str:
    """Render a tree, legend first.

    Indentation duplicates what the id already encodes and measured *free* -- 555 tokens with or
    without it, because runs of spaces collapse into a token that would have been spent anyway.
    Free readability is not a trade-off worth agonising over.
    """
    lines = [TREE_LEGEND]
    lines.extend(_node_line(node, depth) for node, depth in _walk(root))
    return "\n".join(lines)


def windows(entries: Sequence[WindowInfo]) -> str:
    """Render a window list, in the same shape, so the two reads look alike."""
    lines = [WINDOWS_LEGEND]
    for entry in entries:
        parts = [entry.id, entry.role]
        if entry.title:
            parts.append(_quote(entry.title))
        parts.append(str(entry.pid) if entry.pid is not None else "-")
        box = entry.box
        parts.append(f"{box.x},{box.y} {box.width}x{box.height}")
        if entry.active:
            parts.append("*")
        lines.append(" ".join(parts))
    return "\n".join(lines)


__all__ = ["TREE_LEGEND", "WINDOWS_LEGEND", "tree", "windows"]
