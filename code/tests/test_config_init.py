"""The guided setup: it writes a config, keeps secrets out of it, and proves the backend works."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from tests.conftest import strip_ansi
from tests.fake_backend import FakeBackend
from use_computer.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, app
from use_computer.config import (
    CONFIG_FILENAME,
    ENV_FILENAME,
    PROJECT_DIR,
    load,
    profile_env_var,
    render_config,
    write_initial_config,
)
from use_computer.errors import ConfigError


def invoke(*args: str, stdin_is_a_tty: bool = False) -> Result:
    return CliRunner().invoke(app, list(args), catch_exceptions=False)


# --- writing -----------------------------------------------------------------------------------


def test_the_written_config_resolves_back_through_the_loader(tmp_path: Path) -> None:
    """A setup that writes a file the loader cannot read is worse than no setup."""
    config_path, env_path = write_initial_config(
        tmp_path, "staging", "vnc", host="10.0.0.5", port=5901
    )
    assert config_path == tmp_path / PROJECT_DIR / CONFIG_FILENAME
    assert env_path is None

    resolved = load(profile="staging", start=tmp_path, environ={})
    assert resolved.profile.backend == "vnc"
    assert resolved.profile.host == "10.0.0.5"
    assert resolved.profile.port == 5901
    assert resolved.profile_name == "staging"
    assert resolved.warnings == ()  # nothing it writes is an unknown key


def test_a_local_config_carries_the_opt_in_it_was_given(tmp_path: Path) -> None:
    write_initial_config(tmp_path, "laptop", "local", allow_local=True)
    assert load(profile="laptop", start=tmp_path, environ={}).profile.allow_local is True


def test_a_password_goes_to_the_env_file_never_the_committed_toml(tmp_path: Path) -> None:
    config_path, env_path = write_initial_config(
        tmp_path, "staging", "vnc", host="h", password="hunter2"
    )
    assert env_path == tmp_path / PROJECT_DIR / ENV_FILENAME
    assert "hunter2" not in config_path.read_text(encoding="utf-8")
    assert profile_env_var("staging", "password") in env_path.read_text(encoding="utf-8")
    assert load(profile="staging", start=tmp_path, environ={}).profile.password == "hunter2"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_the_env_file_is_not_world_readable(tmp_path: Path) -> None:
    _, env_path = write_initial_config(tmp_path, "staging", "vnc", host="h", password="x")
    assert env_path is not None
    assert env_path.stat().st_mode & 0o077 == 0


def test_it_refuses_to_replace_an_existing_config(tmp_path: Path) -> None:
    write_initial_config(tmp_path, "staging", "vnc", host="h")
    with pytest.raises(ConfigError) as excinfo:
        write_initial_config(tmp_path, "other", "vnc", host="h")
    assert "--force" in str(excinfo.value)
    write_initial_config(tmp_path, "other", "vnc", host="h", force=True)
    assert load(start=tmp_path, environ={}).profile_name == "other"


def test_a_hostile_profile_name_cannot_break_out_of_the_string(tmp_path: Path) -> None:
    rendered = render_config('we"ird', "vnc", host='ho"st')
    assert '\\"' in rendered
    write_initial_config(tmp_path, 'we"ird', "vnc", host='ho"st')
    assert load(start=tmp_path, environ={}).profile.host == 'ho"st'


# --- the command -------------------------------------------------------------------------------


def test_init_emits_the_documented_payload(tmp_path: Path) -> None:
    result = invoke(
        "config", "init", "--backend", "vnc", "--host", "10.0.0.5",
        "--profile", "staging", "--dir", str(tmp_path), "--no-probe",
    )
    assert result.exit_code == EXIT_OK
    payload = json.loads(result.stdout)
    assert payload == {
        "action": "init",
        "config-file": str(tmp_path / PROJECT_DIR / CONFIG_FILENAME),
        "env-file": None,
        "profile": "staging",
        "backend": "vnc",
        "probe": None,
    }


def test_the_profile_defaults_to_the_backend_name(tmp_path: Path) -> None:
    result = invoke(
        "config", "init", "--backend", "vnc", "--host", "h",
        "--dir", str(tmp_path), "--no-probe",
    )
    assert json.loads(result.stdout)["profile"] == "vnc"


def test_vnc_without_a_host_is_a_usage_error(tmp_path: Path) -> None:
    result = invoke("config", "init", "--backend", "vnc", "--dir", str(tmp_path), "--no-probe")
    assert result.exit_code == EXIT_USAGE
    assert result.stdout.strip() == ""


def test_local_without_the_opt_in_is_a_usage_error(tmp_path: Path) -> None:
    # Never write an opt-in on the user's behalf.
    result = invoke("config", "init", "--backend", "local", "--dir", str(tmp_path), "--no-probe")
    assert result.exit_code == EXIT_USAGE
    assert not (tmp_path / PROJECT_DIR).exists()


def test_no_backend_on_a_pipe_is_a_usage_error_not_a_prompt(tmp_path: Path) -> None:
    result = invoke("config", "init", "--dir", str(tmp_path))
    assert result.exit_code == EXIT_USAGE
    assert "not a terminal" in strip_ansi(result.stderr)


# --- the probe ---------------------------------------------------------------------------------


def test_the_probe_reports_the_screen_it_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("use_computer.runner.create_backend", lambda profile: FakeBackend())
    result = invoke(
        "config", "init", "--backend", "vnc", "--host", "h", "--dir", str(tmp_path)
    )
    assert result.exit_code == EXIT_OK
    probe = json.loads(result.stdout)["probe"]
    assert probe["ok"] is True
    assert probe["screen"]["scale"] == 2.0
    assert probe["error"] is None


def test_an_underivable_scale_fails_the_setup_but_keeps_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The most expensive failure this tool has, surfaced at setup instead of the first click."""
    monkeypatch.setattr(
        "use_computer.runner.create_backend", lambda profile: FakeBackend(scale=None)
    )
    result = invoke(
        "config", "init", "--backend", "vnc", "--host", "h", "--dir", str(tmp_path)
    )
    assert result.exit_code == EXIT_FAILURE
    probe = json.loads(result.stdout)["probe"]
    assert probe["ok"] is False
    assert "scale" in probe["error"]
    assert (tmp_path / PROJECT_DIR / CONFIG_FILENAME).is_file()


def test_a_backend_that_will_not_open_fails_the_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(profile: object) -> FakeBackend:
        raise ConnectionRefusedError("nothing is listening")

    monkeypatch.setattr("use_computer.runner.create_backend", refuse)
    result = invoke(
        "config", "init", "--backend", "vnc", "--host", "h", "--dir", str(tmp_path)
    )
    assert result.exit_code == EXIT_FAILURE
    assert "ConnectionRefusedError" in json.loads(result.stdout)["probe"]["error"]


# --- the guided half ---------------------------------------------------------------------------


def test_the_questions_produce_a_vnc_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter(["vnc", "10.0.0.5", "5901", "hunter2", "staging"])
    monkeypatch.setattr("use_computer.cli._stdin_is_a_tty", lambda: True)
    monkeypatch.setattr("typer.prompt", lambda *a, **k: next(answers))

    result = invoke("config", "init", "--dir", str(tmp_path), "--no-probe")
    assert result.exit_code == EXIT_OK
    payload = json.loads(result.stdout)
    assert payload["profile"] == "staging"
    assert payload["env-file"] is not None
    resolved = load(profile="staging", start=tmp_path, environ={})
    assert (resolved.profile.host, resolved.profile.port) == ("10.0.0.5", 5901)
    assert resolved.profile.password == "hunter2"


def test_declining_the_local_opt_in_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An opt-in nobody was asked for is not an opt-in -- and a refused one must leave no trace.
    monkeypatch.setattr("use_computer.cli._stdin_is_a_tty", lambda: True)
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "local")
    monkeypatch.setattr("typer.confirm", lambda *a, **k: False)

    result = invoke("config", "init", "--dir", str(tmp_path), "--no-probe")
    assert result.exit_code == EXIT_OK
    assert not (tmp_path / PROJECT_DIR).exists()
    assert result.stdout.strip() == ""


def test_an_unknown_backend_is_asked_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter(["telepathy", "local", "laptop"])
    monkeypatch.setattr("use_computer.cli._stdin_is_a_tty", lambda: True)
    monkeypatch.setattr("typer.prompt", lambda *a, **k: next(answers))
    monkeypatch.setattr("typer.confirm", lambda *a, **k: True)

    result = invoke("config", "init", "--dir", str(tmp_path), "--no-probe")
    assert result.exit_code == EXIT_OK
    assert json.loads(result.stdout)["backend"] == "local"
    assert "not a backend" in strip_ansi(result.stderr)
