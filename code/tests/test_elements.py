"""The ladder: reading the tree, acting through the platform, and falling back to pixels."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from tests.fake_backend import FakeBackend
from tests.fake_provider import FakeProvider, denied, empty, unavailable
from use_computer.actions import (
    ClickAction,
    DoubleClickAction,
    FocusAction,
    SetValueAction,
    ToggleAction,
    TreeAction,
)
from use_computer.config import Settings
from use_computer.runner import Session
from use_computer.tree import NodeSelector, TreeReason, TreeScope, Via


def session(provider: FakeProvider | None = None, **settings: object) -> Session:
    return Session(
        FakeBackend(),
        profile="fake",
        settings=Settings(**settings),  # type: ignore[arg-type]
        provider=provider or FakeProvider(),
    )


def button() -> NodeSelector:
    return NodeSelector(role="button", name="Invia")


# --- reading -----------------------------------------------------------------------------------


def test_tree_returns_a_pruned_tree() -> None:
    result = session().run([TreeAction()]).results[0]
    assert result.ok
    assert result.tree is not None
    assert result.tree.root is not None
    assert result.tree.reason is None
    assert result.tree.screenshot is None


def test_tree_filters_to_a_flat_list_of_matches() -> None:
    result = session().run([TreeAction(role="button")]).results[0]
    root = result.tree.root  # type: ignore[union-attr]
    assert root is not None
    assert [child.name for child in root.children] == ["Invia", "Annulla"]
    assert all(child.children == () for child in root.children)


def test_tree_budget_reports_truncation_and_where_to_re_enter() -> None:
    result = session(tree_max_nodes=2).run([TreeAction()]).results[0]
    tree = result.tree
    assert tree is not None
    assert tree.truncated is True
    assert tree.truncated_ids


def test_of_re_enters_at_a_node() -> None:
    result = session().run([TreeAction(of="0/1", all=True)]).results[0]
    root = result.tree.root  # type: ignore[union-attr]
    assert root is not None and root.id == "0/1"


def test_no_provider_reports_why_and_hands_over_a_screenshot() -> None:
    result = session(unavailable()).run([TreeAction()]).results[0]
    tree = result.tree
    assert result.ok  # not a failure: it answered, and the answer is "there is none"
    assert tree is not None
    assert tree.reason is TreeReason.UNAVAILABLE
    assert tree.screenshot is not None
    assert tree.screenshot.path is not None
    assert tree.screenshot.path.exists()


def test_a_denied_permission_is_its_own_reason() -> None:
    tree = session(denied()).run([TreeAction()]).results[0].tree
    assert tree is not None and tree.reason is TreeReason.DENIED


def test_an_application_exposing_nothing_is_empty_not_absent() -> None:
    tree = session(empty()).run([TreeAction()]).results[0].tree
    assert tree is not None and tree.reason is TreeReason.EMPTY


def test_no_fallback_leaves_the_screenshot_untaken() -> None:
    tree = session(unavailable()).run([TreeAction(fallback=False)]).results[0].tree
    assert tree is not None and tree.screenshot is None


def test_out_writes_the_tree_and_returns_its_path(tmp_path: object) -> None:
    target = tmp_path / "tree.json"  # type: ignore[operator]
    tree = session().run([TreeAction(out=target)]).results[0].tree
    assert tree is not None
    assert tree.root is None  # the point of asking for a file
    assert tree.path == target
    assert json.loads(target.read_text())["role"] == "dialog"


# --- acting ------------------------------------------------------------------------------------


def test_click_on_an_element_goes_through_the_platform() -> None:
    provider = FakeProvider()
    backend = FakeBackend()
    result = Session(backend, profile="fake", provider=provider).run(
        [ClickAction(selector=button())]
    )
    assert result.ok
    assert provider.calls == [("0/1/0", "click", None)]
    assert backend.calls == []  # no pointer moved at all
    assert result.results[0].via is Via.ACTION
    assert result.results[0].matched is not None


def test_a_node_the_platform_will_not_operate_falls_back_to_its_centre() -> None:
    provider = FakeProvider()
    backend = FakeBackend()
    result = Session(backend, profile="fake", provider=provider).run(
        [ClickAction(selector=NodeSelector(role="button", name="Annulla"))]
    )
    assert result.ok
    assert provider.calls == []  # it advertises no actions, so nothing was even attempted
    assert backend.calls == [("click", (564, 276, "left", 1))]
    assert result.results[0].via is Via.COORDINATE
    assert result.results[0].resolved is not None


def test_a_platform_refusal_falls_back_too() -> None:
    provider = FakeProvider(refuse=frozenset({"click"}))
    backend = FakeBackend()
    result = Session(backend, profile="fake", provider=provider).run(
        [ClickAction(selector=button())]
    )
    assert provider.calls == [("0/1/0", "click", None)]
    assert backend.calls  # false from the platform is a real refusal, not silence
    assert result.results[0].via is Via.COORDINATE


def test_via_action_refuses_to_fall_back() -> None:
    result = session(FakeProvider(refuse=frozenset({"click"}))).run(
        [ClickAction(selector=button(), via=Via.ACTION)]
    )
    assert not result.ok
    assert result.results[0].error is not None
    assert result.results[0].error.type == "ActionFailedError"


def test_via_coordinate_never_asks_the_platform() -> None:
    provider = FakeProvider()
    backend = FakeBackend()
    Session(backend, profile="fake", provider=provider).run(
        [ClickAction(selector=button(), via=Via.COORDINATE)]
    )
    assert provider.calls == []
    assert backend.calls


def test_double_click_has_no_platform_form_and_says_so() -> None:
    result = session().run([DoubleClickAction(selector=button(), via=Via.ACTION)])
    assert not result.ok
    assert result.results[0].error is not None
    assert result.results[0].error.type == "ActionNotSupportedError"


def test_double_click_by_element_still_uses_the_pointer() -> None:
    backend = FakeBackend()
    result = Session(backend, profile="fake", provider=FakeProvider()).run(
        [DoubleClickAction(selector=button())]
    )
    assert result.ok
    assert backend.calls == [("click", (456, 276, "left", 2))]
    assert result.results[0].via is Via.COORDINATE


def test_an_element_only_action_the_node_does_not_support_is_an_error() -> None:
    result = session().run([ToggleAction(selector=button())])
    assert not result.ok
    error = result.results[0].error
    assert error is not None and error.type == "ActionNotSupportedError"
    assert "click" in error.message  # names what the node does support


def test_set_value_carries_its_value_to_the_platform() -> None:
    provider = FakeProvider()
    Session(FakeBackend(), profile="fake", provider=provider).run(
        [SetValueAction(selector=NodeSelector(role="text"), value="mario@example.com")]
    )
    assert provider.calls == [("0/0/0", "set_value", "mario@example.com")]


def test_focus_goes_through_the_platform() -> None:
    provider = FakeProvider()
    Session(FakeBackend(), profile="fake", provider=provider).run(
        [FocusAction(selector=NodeSelector(role="text"))]
    )
    assert provider.calls == [("0/0/0", "focus", None)]


# --- resolution failures -------------------------------------------------------------------------


def test_ambiguity_comes_back_with_the_candidates() -> None:
    result = session().run([ClickAction(selector=NodeSelector(role="button"))])
    error = result.results[0].error
    assert error is not None and error.type == "AmbiguousNodeError"
    assert error.candidates is not None
    assert [item.name for item in error.candidates] == ["Invia", "Annulla"]


def test_nothing_matched_hands_over_a_screenshot() -> None:
    result = session().run([ClickAction(selector=NodeSelector(role="slider"))])
    error = result.results[0].error
    assert error is not None and error.type == "NodeNotFoundError"
    assert error.screenshot is not None
    assert error.screenshot.path is not None
    assert error.screenshot.path.exists()


# --- guards --------------------------------------------------------------------------------------


def test_a_coordinate_and_a_selector_together_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClickAction(x=1, y=2, selector=button())


def test_an_element_only_action_has_no_coordinate_form() -> None:
    with pytest.raises(ValidationError):
        FocusAction(selector=button(), via=Via.COORDINATE)


def test_an_element_action_needs_a_selector() -> None:
    with pytest.raises(ValidationError):
        FocusAction()


def test_flat_selector_keys_in_a_batch_become_a_selector() -> None:
    action = ClickAction.model_validate({"role": "button", "name": "Invia", "window": "@42"})
    assert action.selector is not None
    assert action.selector.role == "button"
    assert action.selector.window == TreeScope.parse("@42")


# --- safety --------------------------------------------------------------------------------


def test_dry_run_still_resolves_and_reports_the_rung() -> None:
    provider = FakeProvider()
    backend = FakeBackend()
    result = Session(
        backend,
        profile="fake",
        settings=Settings(dry_run=True),
        provider=provider,
    ).run([ClickAction(selector=button())])
    item = result.results[0]
    assert item.performed is False
    assert item.matched is not None and item.matched.id == "0/1/0"
    assert item.via is Via.ACTION
    assert provider.calls == [] and backend.calls == []


def test_a_run_of_coordinate_actions_never_builds_a_provider() -> None:
    # The provider is lazy on purpose: a coordinate-only run must not pay for an accessibility
    # API, nor fail on a machine where none is installed.
    live = Session(FakeBackend(), profile="fake")
    result = live.run([ClickAction(x=120, y=340)])
    assert result.ok
    live.close()


def test_closing_a_session_closes_the_provider() -> None:
    provider = FakeProvider()
    live = Session(FakeBackend(), profile="fake", provider=provider)
    live.close()
    assert provider.closed is True
