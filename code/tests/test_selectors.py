"""Pruning, the node budget, and resolving a selector -- the pure half, tested without a desktop."""

from __future__ import annotations

import pytest

from tests.fake_provider import dialog, node
from use_computer.errors import AmbiguousNodeError, NodeNotFoundError
from use_computer.selectors import (
    budget,
    count,
    find,
    is_interesting,
    prune,
    resolve_one,
    subtree,
    walk,
)
from use_computer.tree import NodeSelector, UINode


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


def test_pruning_drops_what_is_off_screen() -> None:
    tree = node(
        "0",
        "window",
        "App",
        children=(node("0/0", "button", "Hidden", box=(0, 0, 0, 0), actions=("click",)),),
    )
    assert ids(prune(tree)) == ["0"]


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
