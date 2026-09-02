"""Test environment isolation.

Two things bite in CI and not locally, and both are handled here:

* Ambient ``USE_COMPUTER_*``, ``CLAUDE*`` and ``XDG_*`` variables, and any project root above
  the checkout, leak into resolution and change what a test resolves.
* rich enables colour inside GitHub Actions, and its highlighter splits an option token across
  styled spans -- so substring assertions pass locally and fail on CI. ``TERM`` and ``COLUMNS``
  are pinned, and :func:`strip_ansi` removes what still gets through.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest

from use_computer.config import CONFIG_FILENAME, PROJECT_DIR

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escapes, so an assertion means the same thing everywhere."""
    return _ANSI.sub("", text)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    for name in list(os.environ):
        if name.startswith(("USE_COMPUTER", "CLAUDE", "XDG_")):
            monkeypatch.delenv(name, raising=False)
    # Colour and width are what make CLI assertions environment-dependent.
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("NO_COLOR", "1")
    # An XDG config above the checkout is a configuration layer; point it somewhere empty.
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True, exist_ok=True)
    (home / ".local" / "share").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    yield


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project root with a ``.use-computer`` directory, and the cwd inside it.

    Working inside it also guarantees no project root above the checkout is found.
    """
    root = tmp_path / "project"
    (root / PROJECT_DIR).mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


class WriteConfig(Protocol):
    """Writes a config.toml into the project fixture's root."""

    def __call__(self, text: str) -> Path: ...


@pytest.fixture
def write_config(project: Path) -> WriteConfig:
    def _write(text: str) -> Path:
        path = project / PROJECT_DIR / CONFIG_FILENAME
        path.write_text(text, encoding="utf-8")
        return path

    return _write
