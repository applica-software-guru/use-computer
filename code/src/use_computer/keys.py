"""One key-name syntax, normalised per backend.

One spelling of a shortcut must work on both backends. This module owns the canonical
vocabulary and one mapping table per backend, both keyed by the same canonical names -- so a
missing entry is a visible hole rather than a divergence between backends.

This module is pure: the tables hold strings, never imported symbols, so it stays importable
with no extras installed.
"""

from __future__ import annotations

import difflib
from typing import Final

from pydantic import BaseModel, ConfigDict

from use_computer.errors import KeySyntaxError

#: Modifier aliases resolved to one canonical name.
MODIFIER_ALIASES: Final[dict[str, str]] = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "shift": "shift",
    "cmd": "cmd",
    "command": "cmd",
    "super": "cmd",
    "win": "cmd",
    "meta": "cmd",
}

#: Canonical modifiers, in the order they are pressed.
MODIFIER_ORDER: Final[tuple[str, ...]] = ("ctrl", "alt", "shift", "cmd")

#: Named-key aliases resolved to one canonical name.
KEY_ALIASES: Final[dict[str, str]] = {
    "return": "enter",
    "escape": "esc",
    "del": "delete",
    "ins": "insert",
    "pgup": "pageup",
    "page_up": "pageup",
    "pgdn": "pagedown",
    "pagedn": "pagedown",
    "page_down": "pagedown",
    "spacebar": "space",
    "capslock": "caps_lock",
    "printscreen": "print_screen",
}

_NAMED_KEYS: Final[tuple[str, ...]] = (
    "enter",
    "tab",
    "esc",
    "space",
    "backspace",
    "delete",
    "insert",
    "home",
    "end",
    "pageup",
    "pagedown",
    "up",
    "down",
    "left",
    "right",
    "caps_lock",
    "print_screen",
    *(f"f{n}" for n in range(1, 25)),
)

#: Every canonical named key. Single characters are keys too, but are not enumerated.
NAMED_KEYS: Final[frozenset[str]] = frozenset(_NAMED_KEYS)


class KeyCombo(BaseModel):
    """A parsed key combination, in canonical names."""

    model_config = ConfigDict(frozen=True)

    modifiers: tuple[str, ...] = ()
    key: str

    def __str__(self) -> str:
        return "+".join((*self.modifiers, self.key))


def _suggest(name: str) -> str:
    pool = [*MODIFIER_ALIASES, *NAMED_KEYS, *KEY_ALIASES]
    close = difflib.get_close_matches(name, pool, n=3, cutoff=0.5)
    if not close:
        return ""
    return " Did you mean: " + ", ".join(close) + "?"


def parse_combo(spec: str) -> KeyCombo:
    """Parse ``ctrl+shift+t`` into a :class:`KeyCombo` of canonical names.

    Raises:
        KeySyntaxError: on an empty spec, a repeated modifier, more than one non-modifier key,
            or an unknown key name. An unknown name is never passed through to the backend to
            fail obscurely there.
    """
    raw = spec.strip()
    if not raw:
        raise KeySyntaxError("empty key combination")
    if raw == "+":
        return KeyCombo(key="+")
    # "ctrl++" means ctrl plus the literal "+" key; the split leaves an empty tail behind.
    body = raw[:-1] if raw.endswith("+") else raw
    parts = [p.strip().lower() for p in body.split("+")]
    if raw.endswith("+"):
        if parts[-1] != "":
            # A trailing separator with nothing after it, e.g. "ctrl+".
            raise KeySyntaxError(f"malformed key combination: {spec!r}")
        parts[-1] = "+"
    if any(not p for p in parts):
        raise KeySyntaxError(f"malformed key combination: {spec!r}")

    modifiers: list[str] = []
    key: str | None = None
    for part in parts:
        if part in MODIFIER_ALIASES:
            modifier = MODIFIER_ALIASES[part]
            if modifier in modifiers:
                raise KeySyntaxError(f"repeated modifier {modifier!r} in {spec!r}")
            modifiers.append(modifier)
            continue
        if key is not None:
            raise KeySyntaxError(
                f"more than one non-modifier key in {spec!r}: {key!r} and {part!r}"
            )
        key = KEY_ALIASES.get(part, part)
        if len(key) != 1 and key not in NAMED_KEYS:
            raise KeySyntaxError(f"unknown key name {part!r} in {spec!r}.{_suggest(part)}")

    if key is None:
        # A lone modifier is a key in its own right: `use-computer key shift`.
        if len(modifiers) == 1:
            return KeyCombo(key=modifiers[0])
        raise KeySyntaxError(f"{spec!r} is only modifiers -- no key to press")

    ordered = tuple(m for m in MODIFIER_ORDER if m in modifiers)
    return KeyCombo(modifiers=ordered, key=key)


def canonical(spec: str) -> str:
    """Return the canonical spelling of ``spec``, so a log line is reproducible input."""
    return str(parse_combo(spec))


# --- Per-backend tables ----------------------------------------------------------------------
# Both keyed by the same canonical names. Values are the *names* the backend's library uses;
# resolving a name to a symbol happens in the backend, so this module imports nothing optional.

#: canonical name -> attribute of ``pynput.keyboard.Key``.
PYNPUT_KEYS: Final[dict[str, str]] = {
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "cmd": "cmd",
    "enter": "enter",
    "tab": "tab",
    "esc": "esc",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
    "insert": "insert",
    "home": "home",
    "end": "end",
    "pageup": "page_up",
    "pagedown": "page_down",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "caps_lock": "caps_lock",
    "print_screen": "print_screen",
    **{f"f{n}": f"f{n}" for n in range(1, 21)},
}

#: canonical name -> X11 keysym name understood by vncdotool.
VNC_KEYS: Final[dict[str, str]] = {
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "cmd": "super",
    "enter": "return",
    "tab": "tab",
    "esc": "esc",
    "space": "space",
    "backspace": "bsp",
    "delete": "delete",
    "insert": "insert",
    "home": "home",
    "end": "end",
    "pageup": "pgup",
    "pagedown": "pgdn",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "caps_lock": "caps_lock",
    "print_screen": "print",
    **{f"f{n}": f"f{n}" for n in range(1, 21)},
}
