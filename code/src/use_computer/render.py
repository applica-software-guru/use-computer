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
WINDOWS_LEGEND = '# id app role "title" pid x,y wxh *active'


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
        parts = [entry.id, entry.app or "-", entry.role]
        if entry.title:
            parts.append(_quote(entry.title))
        parts.append(str(entry.pid) if entry.pid is not None else "-")
        box = entry.box
        parts.append(f"{box.x},{box.y} {box.width}x{box.height}")
        if entry.active:
            parts.append("*")
        lines.append(" ".join(parts))
    return "\n".join(lines)




# --- the human views -----------------------------------------------------------------------------
# Aligned columns and nothing else. rich is available and is exactly the wrong instinct: this
# output is read in terminals, pipes and CI logs, and only alignment survives all three. The
# project has been bitten by rich twice -- a newline inside a JSON string, and `[tree]` eaten as
# markup -- and both times the lesson was to hand it less, not more.


def _columns(rows: list[list[str]], headers: list[str]) -> str:
    widths = [len(head) for head in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row, strict=True)]
    lines = ["  ".join(head.ljust(width) for head, width in zip(headers, widths, strict=True))]
    for row in rows:
        lines.append("  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)))
    return "\n".join(line.rstrip() for line in lines)


def _ellipsis(text: str, limit: int = 44) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


def windows_for_a_reader(entries: Sequence[WindowInfo]) -> str:
    """The window list, as columns."""
    if not entries:
        return "no windows"
    rows = [
        [
            entry.id,
            entry.app or "",
            entry.role,
            _ellipsis(entry.title or ""),
            str(entry.pid) if entry.pid is not None else "",
            f"{entry.box.x},{entry.box.y} {entry.box.width}x{entry.box.height}",
            "*" if entry.active else "",
        ]
        for entry in entries
    ]
    return _columns(rows, ["id", "app", "role", "title", "pid", "box", "active"])


__all__ = [
    "TREE_LEGEND",
    "WINDOWS_LEGEND",
    "tree",
    "windows",
    "windows_for_a_reader",
]
