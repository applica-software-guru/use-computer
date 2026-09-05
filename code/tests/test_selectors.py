"""Pruning, the node budget, and resolving a selector -- the pure half, tested without a desktop."""

from __future__ import annotations

import pytest

from tests.fake_provider import dialog, node
from use_computer.errors import (
    AmbiguousNodeError,
    AmbiguousWindowError,
    NodeNotFoundError,
    UITreeUnavailableError,
)
from use_computer.selectors import (
    budget,
    clamp_text,
    count,
    find,
    is_interesting,
    prune,
    resolve_one,
    resolve_window,
    subtree,
    walk,
)
from use_computer.tree import Box, NodeSelector, UINode, WindowInfo


def ids(root: UINode) -> list[str]:
    return [item.id for item in walk(root)]


def test_pruning_collapses_a_container_that_only_nests() -> None:
    pruned = prune(dialog())
    # The filler and the panel contribute nothing but nesting; the panel survives because it
    # carries two children, the filler does not because it carries one.
    assert "0/0" not in ids(pruned)
    assert "0/0/0" in ids(pruned)


def test_pruning_keeps_ids_from_the_full_tree() -> None:
    pruned = prune(dialog())
    # The collapsed child keeps its own path, so `--of` can still re-enter at it.
    assert "0/1/0" in ids(pruned)


def test_pruning_drops_what_is_off_screen_and_inert() -> None:
    tree = node(
        "0",
        "window",
        "App",
        children=(node("0/0", "label", "Hidden", box=(0, 0, 0, 0)),),
    )
    assert ids(prune(tree)) == ["0"]


def test_pruning_keeps_what_the_platform_can_operate_wherever_it_is() -> None:
    # The items of a closed menu have no position and are still the thing an agent came for:
    # reaching File > Preferences without opening the menu is the point of acting through the API.
    tree = node(
        "0",
        "window",
        "App",
        children=(node("0/0", "menuitem", "Preferences", box=(0, 0, 0, 0), actions=("click",)),),
    )
    assert ids(prune(tree)) == ["0", "0/0"]


def test_a_named_node_survives_even_without_actions() -> None:
    assert is_interesting(node("0", "label", "Totale")) is True
    assert is_interesting(node("0", "filler")) is False


def test_budget_truncates_and_names_what_it_cut() -> None:
    capped, total, truncated, cut = budget(dialog(), 3)
    assert truncated is True
    assert total == 3
    assert cut  # the ids to re-enter with --of
    assert count(capped) == 3


def test_budget_leaves_a_small_tree_alone() -> None:
    tree = dialog()
    capped, total, truncated, cut = budget(tree, 100)
    assert (truncated, cut) == (False, ())
    assert capped is tree
    assert total == count(tree)


def test_subtree_re_enters_at_a_node() -> None:
    found = subtree(dialog(), "0/1")
    assert found is not None
    assert [item.id for item in found.children] == ["0/1/0", "0/1/1"]
    assert subtree(dialog(), "9/9") is None


def test_find_matches_a_substring_case_insensitively() -> None:
    assert [item.id for item in find(dialog(), NodeSelector(name="invia"))] == ["0/1/0"]
    assert find(dialog(), NodeSelector(name="invia", exact=True)) == []


def test_resolve_one_returns_the_single_match() -> None:
    assert resolve_one(dialog(), NodeSelector(role="text")).name == "Destinatario"


def test_ambiguity_is_an_error_carrying_the_candidates() -> None:
    with pytest.raises(AmbiguousNodeError) as caught:
        resolve_one(dialog(), NodeSelector(role="button"))
    assert [item.id for item in caught.value.candidates] == ["0/1/0", "0/1/1"]
    assert "--nth" in str(caught.value)


def test_nth_picks_between_candidates() -> None:
    assert resolve_one(dialog(), NodeSelector(role="button", nth=1)).name == "Annulla"


def test_nth_past_the_end_is_not_found() -> None:
    with pytest.raises(NodeNotFoundError):
        resolve_one(dialog(), NodeSelector(role="button", nth=9))


def test_nothing_matched_says_so() -> None:
    with pytest.raises(NodeNotFoundError):
        resolve_one(dialog(), NodeSelector(role="slider"))


def test_an_id_whose_role_moved_says_the_tree_moved() -> None:
    with pytest.raises(NodeNotFoundError) as caught:
        resolve_one(dialog(), NodeSelector(node_id="0/1/0", role="checkbox"))
    assert "the tree moved" in str(caught.value)
    assert "button 'Invia'" in str(caught.value)


def test_clamp_text_bounds_what_a_node_carries_into_the_context() -> None:
    # The node budget counts nodes, which is the wrong unit: one terminal reports its whole
    # buffer as a single value, and 13 KB from one node defeats a budget of four hundred.
    tree = node(
        "0",
        "window",
        "App",
        children=(node("0/0", "terminal", "Terminal", value="x" * 5000, actions=("focus",)),),
    )
    clamped = clamp_text(tree, 200)
    child = clamped.children[0]
    assert child.value is not None
    assert len(child.value) == 201  # 200 plus the marker that says it was cut
    assert child.value.endswith("…")


def test_clamp_text_leaves_short_text_exactly_as_it_was() -> None:
    clamped = clamp_text(node("0", "button", "Invia"), 200)
    assert clamped.name == "Invia"


def test_matching_sees_the_full_name_not_the_clamped_one() -> None:
    # Clamping is applied on the way out. A selector must still be able to name a long label.
    long_name = "Conferma " + "molto " * 60 + "lungo"
    tree = node("0", "window", "App", children=(node("0/0", "button", long_name),))
    assert resolve_one(tree, NodeSelector(name="lungo")).id == "0/0"


# --- matching a window is policy, so it is tested here and not on three desktops ------------------


def window(node_id: str, title: str | None, app: str | None = None) -> WindowInfo:
    return WindowInfo(
        id=node_id, title=title, role="window", app=app, box=Box(x=0, y=0, width=10, height=10)
    )


def test_a_window_title_that_matches_once_resolves() -> None:
    entries = [window("0/1", "Ledger"), window("0/2", "Posta")]
    assert resolve_window(entries, "Ledger").id == "0/1"


def test_the_terminal_running_the_command_makes_a_title_ambiguous() -> None:
    # A terminal puts the running command in its own title, so it contains whatever was asked
    # for. Picking the first would return the window the user is looking at.
    entries = [
        window("0/1", "Report", app="Ledger"),
        window("0/9", 'use-computer --window "Report"', app="Terminal"),
    ]
    with pytest.raises(AmbiguousWindowError) as caught:
        resolve_window(entries, "Report")
    assert [w.app for w in caught.value.candidates] == ["Ledger", "Terminal"]


def test_an_id_is_exact_and_is_tried_before_any_title() -> None:
    entries = [window("0/1", "0/9 is a strange title"), window("0/9", "Posta")]
    assert resolve_window(entries, "0/9").title == "Posta"


def test_no_window_matching_says_so() -> None:
    with pytest.raises(UITreeUnavailableError):
        resolve_window([window("0/1", "Ledger")], "Posta")
