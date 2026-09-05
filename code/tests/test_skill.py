"""The bundled skill: it ships in the wheel, and it never touches someone else's directory."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from use_computer.cli import EXIT_FAILURE, EXIT_OK, app
from use_computer.errors import ConfigError
from use_computer.skill import (
    CLAUDE_DIR,
    MARKER_KEY,
    MARKER_VALUE,
    NEUTRAL_DIR,
    SKILL_FILE,
    SKILL_NAME,
    Scope,
    SkillState,
    bundled_text,
    install,
    remove,
    skills_dir,
    status,
    update,
)


def test_the_skill_is_package_data_not_a_file_at_the_repository_root() -> None:
    # A copy at the repository root would not ship in the wheel, and a skill that is not in
    # the wheel does not exist for anyone who installed from PyPI.
    text = bundled_text()
    assert text.startswith("---")
    assert f"{MARKER_KEY}: {MARKER_VALUE}" in text


def test_project_scope_follows_a_claude_layout(tmp_path: Path) -> None:
    (tmp_path / CLAUDE_DIR).mkdir(parents=True)
    assert skills_dir(Scope.PROJECT, root=tmp_path) == tmp_path / CLAUDE_DIR


def test_project_scope_follows_an_agents_layout(tmp_path: Path) -> None:
    (tmp_path / NEUTRAL_DIR).mkdir(parents=True)
    assert skills_dir(Scope.PROJECT, root=tmp_path) == tmp_path / NEUTRAL_DIR


def test_project_scope_defaults_to_the_neutral_layout(tmp_path: Path) -> None:
    assert skills_dir(Scope.PROJECT, root=tmp_path) == tmp_path / NEUTRAL_DIR


def test_install_writes_the_bundled_copy(tmp_path: Path) -> None:
    state = install(Scope.PROJECT, root=tmp_path)
    assert state.path == tmp_path / NEUTRAL_DIR / SKILL_NAME / SKILL_FILE
    assert state.path.read_text(encoding="utf-8") == bundled_text()
    assert state.status == "up-to-date"


def test_install_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    install(Scope.PROJECT, root=tmp_path)
    with pytest.raises(ConfigError) as excinfo:
        install(Scope.PROJECT, root=tmp_path)
    assert "--force" in str(excinfo.value)
    install(Scope.PROJECT, root=tmp_path, force=True)


def test_install_never_touches_a_directory_that_is_not_ours(tmp_path: Path) -> None:
    foreign = tmp_path / NEUTRAL_DIR / SKILL_NAME / SKILL_FILE
    foreign.parent.mkdir(parents=True)
    foreign.write_text("---\nname: someone-else\n---\n", encoding="utf-8")
    attempts: tuple[Callable[[], SkillState], ...] = (
        lambda: install(Scope.PROJECT, root=tmp_path, force=True),
        lambda: update(Scope.PROJECT, root=tmp_path),
        lambda: remove(Scope.PROJECT, root=tmp_path),
    )
    for attempt in attempts:
        with pytest.raises(ConfigError):
            attempt()
    assert "someone-else" in foreign.read_text(encoding="utf-8")


def test_remove_deletes_only_our_own_copy(tmp_path: Path) -> None:
    state = install(Scope.PROJECT, root=tmp_path)
    removed = remove(Scope.PROJECT, root=tmp_path)
    assert not state.path.exists()
    assert removed.status == "missing"


def test_remove_is_a_no_op_when_nothing_is_installed(tmp_path: Path) -> None:
    assert remove(Scope.PROJECT, root=tmp_path).status == "missing"


def test_status_reports_outdated_and_update_fixes_it(tmp_path: Path) -> None:
    state = install(Scope.PROJECT, root=tmp_path)
    state.path.write_text(
        f"---\n{MARKER_KEY}: {MARKER_VALUE}\n---\nstale\n", encoding="utf-8"
    )
    assert status(Scope.PROJECT, root=tmp_path).status == "outdated"
    assert update(Scope.PROJECT, root=tmp_path).status == "up-to-date"


def test_dir_overrides_the_scope(tmp_path: Path) -> None:
    target = tmp_path / "custom"
    state = install(Scope.PROJECT, override=target)
    assert state.path == target / SKILL_NAME / SKILL_FILE


def test_the_scope_flag_accepts_every_documented_value() -> None:
    assert {scope.value for scope in Scope} == {"user", "project", "agents", "claude"}


def test_the_cli_reports_what_it_did(project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["skill", "install"], catch_exceptions=False)
    assert result.exit_code == EXIT_OK
    assert result.stdout.split()[:3] == ["install", "project", "up-to-date"]

    again = runner.invoke(app, ["skill", "install"], catch_exceptions=False)
    assert again.exit_code == EXIT_FAILURE

    status_result = runner.invoke(
        app, ["skill", "status", "--format", "json"], catch_exceptions=False
    )
    assert json.loads(status_result.stdout)["installed"] is True

    removed = runner.invoke(app, ["skill", "remove"], catch_exceptions=False)
    assert removed.stdout.split()[:3] == ["remove", "project", "missing"]
