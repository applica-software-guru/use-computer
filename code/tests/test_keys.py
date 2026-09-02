"""One key syntax, normalised for every backend."""

from __future__ import annotations

import pytest

from use_computer.errors import KeySyntaxError
from use_computer.keys import NAMED_KEYS, PYNPUT_KEYS, VNC_KEYS, canonical, parse_combo


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("ctrl+shift+t", "ctrl+shift+t"),
        ("CTRL+SHIFT+T", "ctrl+shift+t"),
        ("control+t", "ctrl+t"),
        ("cmd+space", "cmd+space"),
        ("super+space", "cmd+space"),
        ("option+f4", "alt+f4"),
        ("shift+ctrl+a", "ctrl+shift+a"),
        ("return", "enter"),
        ("escape", "esc"),
        ("shift", "shift"),
        ("ctrl++", "ctrl++"),
    ],
)
def test_aliases_resolve_to_one_canonical_spelling(spec: str, expected: str) -> None:
    assert canonical(spec) == expected


def test_modifiers_come_back_in_a_stable_order() -> None:
    assert parse_combo("shift+cmd+ctrl+alt+a").modifiers == ("ctrl", "alt", "shift", "cmd")


@pytest.mark.parametrize("spec", ["", "   ", "ctrl+", "ctrl+ctrl+a", "a+b", "ctrl+alt"])
def test_malformed_combinations_are_rejected(spec: str) -> None:
    with pytest.raises(KeySyntaxError):
        parse_combo(spec)


def test_an_unknown_key_names_the_closest_matches() -> None:
    with pytest.raises(KeySyntaxError) as excinfo:
        parse_combo("ctrl+entr")
    message = str(excinfo.value)
    assert "entr" in message
    assert "enter" in message


def test_both_backend_tables_are_keyed_by_the_same_canonical_names() -> None:
    # A missing entry must be a visible hole, not a divergence between backends.
    assert set(PYNPUT_KEYS) == set(VNC_KEYS)


def test_every_named_key_that_backends_map_is_canonical() -> None:
    modifiers = {"ctrl", "alt", "shift", "cmd"}
    assert set(PYNPUT_KEYS) - modifiers <= NAMED_KEYS
