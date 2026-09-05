"""The rendering: one line per node, and nothing that needs a parser."""

from __future__ import annotations

from tests.fake_provider import node
from use_computer import render
from use_computer.tree import Box, WindowInfo


def test_a_node_line_carries_every_field_and_no_syntax() -> None:
    tree = node(
        "0",
        "button",
        "Invia",
        actions=("click", "focus"),
        states=("disabled",),
        box=(412, 260, 88, 32),
    )
    line = render.tree(tree).split("\n")[1]
    assert line == '0 button "Invia" !disabled [click,focus] 412,260 88x32'


def test_depth_is_indentation_and_the_legend_comes_first() -> None:
    tree = node("0", "window", "App", children=(node("0/0", "button", "Ok"),))
    lines = render.tree(tree).split("\n")
    assert lines[0] == render.TREE_LEGEND
    assert lines[2].startswith("  0/0 ")


def test_a_counted_subtree_says_how_many() -> None:
    tree = node("0", "menu", "File", actions=("click",)).model_copy(
        update={"offscreen_children": 5}
    )
    assert render.tree(tree).split("\n")[1].endswith(" +5")


def test_a_name_never_breaks_the_line() -> None:
    # A format that needs a parser has lost the argument it was making.
    tree = node("0", "button", 'say "hi"\nnow')
    line = render.tree(tree).split("\n")[1]
    assert line.count("\n") == 0
    assert r'"say \"hi\" now"' in line


def test_windows_render_with_a_marker_on_the_active_one() -> None:
    box = Box(x=0, y=0, width=1920, height=1038)
    entries = [
        WindowInfo(id="0/1", title="Conferma", role="window", app="Posta", pid=4711, box=box,
                   active=True),
        WindowInfo(id="0/2", title=None, role="window", pid=None, box=box, active=False),
    ]
    lines = render.windows(entries).split("\n")
    assert lines[0] == render.WINDOWS_LEGEND
    assert lines[1] == '0/1 Posta window "Conferma" 4711 0,0 1920x1038 *'
    assert lines[2] == "0/2 - window - 0,0 1920x1038"  # no app, no title, no pid, not active


def test_a_crop_is_clipped_to_the_screen() -> None:
    # A node's box can extend past the edge. That must produce a smaller picture, never an error.
    from tests.fake_backend import png
    from use_computer.compare import Screenshot, crop

    shot = Screenshot(data=png(100, 50), width=100, height=50)
    cropped = crop(shot, (80, 40, 60, 40), "0/1")
    assert (cropped.width, cropped.height) == (20, 10)
    assert cropped.box == (80, 40, 20, 10)
    assert cropped.of == "0/1"
