"""What the tree says about the region the platform is not describing.

The case is GNOME Drawing: a panel 1920 px wide whose only child covers 163, with the canvas --
the one thing the task was about -- in no tree at all, under `--full` as well. Nothing fired,
because the provider worked and returned plenty.
"""

from __future__ import annotations

from collections.abc import Iterator

from tests.fake_provider import node
from use_computer.render import TREE_LEGEND
from use_computer.render import tree as render_tree
from use_computer.selectors import mark_unexposed, prune
from use_computer.tree import UINode


def drawing_window() -> UINode:
    """The measured shape: chrome that tiles, around a panel that does not."""
    return node(
        "0",
        "window",
        "Unsaved file",
        box=(0, 0, 1920, 1038),
        children=(
            node("0/22", "menubar", box=(0, 32, 1920, 28)),
            node(
                "0/0",
                "panel",
                box=(0, 60, 1920, 978),
                children=(
                    node("0/0/0", "toolbar", box=(0, 60, 1920, 44)),
                    node(
                        "0/0/2",
                        "panel",
                        box=(0, 106, 1920, 885),
                        children=(
                            node(
                                "0/0/2/0",
                                "scrollpane",
                                actions=("focus",),
                                box=(0, 106, 163, 885),
                            ),
                        ),
                    ),
                    node("0/0/3", "panel", box=(0, 991, 1920, 47)),
                ),
            ),
        ),
    )


def find(root: UINode, node_id: str) -> UINode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = find(child, node_id)
        if found is not None:
            return found
    return None


def test_the_canvas_is_named_as_a_region_the_platform_does_not_describe() -> None:
    marked = mark_unexposed(drawing_window())
    found = find(marked, "0/0/2")
    assert found is not None
    canvas = found.unexposed
    assert canvas is not None
    # Exactly the area to the right of the tool sidebar: where `screenshot --of` should point.
    assert (canvas.x, canvas.y, canvas.width, canvas.height) == (163, 106, 1757, 885)


def test_a_container_whose_children_tile_it_says_nothing() -> None:
    marked = mark_unexposed(drawing_window())
    container = find(marked, "0/0")
    assert container is not None and container.unexposed is None


def test_decoration_is_not_a_blind_spot() -> None:
    # A 1920x32 strip above the menubar is 3% of the window. Reporting it would make the marker
    # noise, and a marker that appears everywhere says nothing anywhere.
    assert mark_unexposed(drawing_window()).unexposed is None


def test_a_large_leaf_that_says_nothing_about_itself_is_a_canvas() -> None:
    # Measured: a drawing surface is one positioned rectangle, no name, no value, no actions, no
    # children. If a leaf could not be marked, the commonest shape of a canvas stayed invisible.
    assert mark_unexposed(node("0", "panel", box=(0, 0, 800, 600))).unexposed is not None


def test_a_leaf_the_platform_describes_is_not_a_hole() -> None:
    named = node("0", "image", "diagram.png", box=(0, 0, 800, 600))
    assert mark_unexposed(named).unexposed is None
    operable = node("0", "canvas", actions=("click",), box=(0, 0, 800, 600))
    assert mark_unexposed(operable).unexposed is None


def test_a_sliver_is_not_a_region() -> None:
    # The empty right-hand side of a toolbar is 1213x44 and the space beside a menubar 1561x28.
    # The platform describes nothing there because there is nothing there.
    toolbar = node(
        "0",
        "panel",
        box=(0, 60, 1920, 44),
        children=(node("0/0", "button", "New", actions=("click",), box=(0, 60, 707, 44)),),
    )
    assert mark_unexposed(toolbar).unexposed is None


def test_only_the_innermost_region_is_reported() -> None:
    # A canvas nested three panels deep would otherwise be reported three times, and the outermost
    # report is the least useful: an agent wants the smallest region to point a screenshot at.
    stack = node(
        "0",
        "panel",
        box=(0, 0, 900, 900),
        children=(
            node(
                "0/0",
                "tab",
                box=(-1, -1, 0, 0),
                children=(node("0/0/0", "panel", box=(10, 10, 880, 880)),),
            ),
        ),
    )
    marked = mark_unexposed(stack)
    assert marked.unexposed is None
    innermost = find(marked, "0/0/0")
    assert innermost is not None and innermost.unexposed is not None


def test_an_unpositioned_child_cannot_hide_a_blind_spot() -> None:
    # A closed menu's item has a box that is arithmetic, not a place. Letting it count as coverage
    # would let any application with a menu hide its canvas.
    root = node(
        "0",
        "panel",
        box=(0, 0, 1000, 1000),
        children=(
            node("0/0", "menuitem", "File", actions=("click",), box=(0, 0, 0, 0)),
            node("0/1", "button", "Go", actions=("click",), box=(0, 0, 100, 1000)),
        ),
    )
    blind = mark_unexposed(root).unexposed
    assert blind is not None
    assert (blind.x, blind.width) == (100, 900)


def test_pruning_cannot_collapse_away_the_only_sign_a_canvas_exists() -> None:
    # The canvas panel has a single child, which is exactly the shape pruning collapses.
    pruned = prune(mark_unexposed(drawing_window()))
    assert find(pruned, "0/0/2") is not None


def test_the_marker_is_rendered_and_the_legend_explains_it() -> None:
    text = render_tree(mark_unexposed(drawing_window()))
    assert "?unexposed" in TREE_LEGEND
    assert "?unexposed 163,106 1757x885" in text


def test_a_depth_limit_does_not_manufacture_a_blind_spot() -> None:
    # At the depth the snapshot stopped at every node looks childless. Marking there would report
    # the caller's own limit as a property of the application -- the same mistake as BUG-011.
    marked = mark_unexposed(drawing_window(), depth_limit=2)
    assert all(found.unexposed is None for found in _every(marked))


def _every(node: UINode) -> Iterator[UINode]:
    yield node
    for child in node.children:
        yield from _every(child)
