"""Everything the skill mentions must exist.

The obvious test is the opposite -- assert every command and flag appears in the skill -- and it
is the wrong direction: it would enforce a second `--help`, longer than the first, that still does
not say which of two ways to look or what an error means about which to try next.

Rot in the direction of *lying* is what needs catching. A skill that tells an agent to pass
`--human` after it was removed is actively harmful; one that does not mention `collapse` is merely
thin, and `--help` covers thin.
"""

from __future__ import annotations

import re

import pytest
import typer.main

from use_computer.cli import app
from use_computer.skill import bundled_text

#: Flags belonging to other tools the skill legitimately shows in shell examples.
FOREIGN = frozenset(
    {"--forms", "--add-entry", "--force-renderer-accessibility", "--system-site-packages"}
)

#: click adds this to every command and never declares it on one.
UNIVERSAL = frozenset({"--help"})


def skill() -> str:
    return bundled_text()


def _walk(group: object, found: set[str], names: set[str]) -> None:
    for name, command in getattr(group, "commands", {}).items():
        names.add(name)
        for parameter in getattr(command, "params", []):
            found.update(opt for opt in parameter.opts if opt.startswith("--"))
        _walk(command, found, names)


def _surface() -> tuple[set[str], set[str]]:
    """What the CLI actually declares, from the app itself rather than a hand-kept list.

    A list would drift in exactly the way this test exists to catch.
    """
    root = typer.main.get_command(app)
    options: set[str] = {opt for p in getattr(root, "params", []) for opt in p.opts
                         if opt.startswith("--")}
    names: set[str] = set()
    _walk(root, options, names)
    return options, names


def declared_options() -> set[str]:
    return _surface()[0]


def declared_commands() -> set[str]:
    return _surface()[1]


def test_every_flag_the_skill_mentions_is_real() -> None:
    mentioned = set(re.findall(r"--[a-z][a-z-]+", skill())) - FOREIGN - UNIVERSAL
    unknown = mentioned - declared_options()
    assert not unknown, f"the skill names flags that do not exist: {sorted(unknown)}"


def test_every_command_the_skill_shows_is_real() -> None:
    invoked = set(re.findall(r"^use-computer ([a-z-]+)", skill(), re.M))
    groups = {"config", "skill"}  # sub-apps, whose own names are checked by their commands
    unknown = invoked - declared_commands() - groups - {"-"}
    assert not unknown, f"the skill invokes commands that do not exist: {sorted(unknown)}"


@pytest.mark.parametrize("flag", ["--via", "--of", "--format", "--window", "--id"])
def test_the_flags_that_carry_a_judgement_are_taught(flag: str) -> None:
    """Not coverage for its own sake: these are the ones `--help` cannot explain.

    `--via` chooses which rung of the ladder an action takes -- the central idea of the tool --
    and went unmentioned through four revisions of this document.
    """
    assert flag in skill()


def test_it_teaches_the_two_ways_of_knowing() -> None:
    text = skill()
    assert "Structure" in text and "Pixels" in text
    assert "screenshot --of" in text  # the cheap way down to vision
