"""The Linux hint has to diagnose, not guess.

It has been wrong three times for one case -- first offering an extra that cannot build, then
naming packages the user already had -- because each fix rewrote the sentence instead of looking
at what is on disk. An agent that cannot read the screen is stuck, and this message is all it has.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from use_computer.accessibility import atspi


def install(tmp_path: Path, version: str) -> str:
    """A fake distro PyGObject, named the way the real one is."""
    directory = tmp_path / "dist-packages" / "gi"
    directory.mkdir(parents=True)
    major, minor = version.split(".")
    (directory / f"_gi.cpython-{major}{minor}-x86_64-linux-gnu.so").touch()
    return str(directory)


def test_it_reads_the_version_out_of_the_shared_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(atspi, "DISTRO_PATHS", (install(tmp_path, "3.10"),))
    assert atspi.distro_python() == "3.10"


def test_a_mismatched_interpreter_is_named_as_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = "3.10" if sys.version_info[:2] != (3, 10) else "3.12"
    monkeypatch.setattr(atspi, "DISTRO_PATHS", (install(tmp_path, other),))
    hint = atspi.system_hint()
    assert f"built for Python {other}" in hint
    assert f"python{other} -m venv --system-site-packages" in hint
    # The advice that would waste the reader's time must not be there.
    assert "sudo apt install" not in hint


def test_a_matching_interpreter_says_the_environment_cannot_see_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = f"{sys.version_info.major}.{sys.version_info.minor}"
    monkeypatch.setattr(atspi, "DISTRO_PATHS", (install(tmp_path, running),))
    hint = atspi.system_hint()
    assert "cannot see it" in hint
    assert "sudo apt install" not in hint


def test_with_nothing_installed_it_says_what_to_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(atspi, "DISTRO_PATHS", (str(tmp_path / "nowhere"),))
    assert atspi.system_hint() == atspi.INSTALL_HINT
    assert "sudo apt install" in atspi.INSTALL_HINT


def test_it_says_nothing_about_a_version_it_did_not_find(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A guess here is what produced three wrong messages already.
    (tmp_path / "gi").mkdir()
    monkeypatch.setattr(atspi, "DISTRO_PATHS", (str(tmp_path / "gi"),))
    assert atspi.distro_python() is None
