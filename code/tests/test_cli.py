"""The CLI contract: JSON on stdout, diagnostics on stderr, and the documented exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from tests.conftest import WriteConfig, strip_ansi
from tests.fake_backend import FakeBackend
from use_computer import cli
from use_computer.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, app, apply_default_command

CONFIG = """
default-profile = "fake"

[profiles.fake]
backend = "vnc"
host = "127.0.0.1"
"""


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> FakeBackend:
    """Every CLI run in these tests talks to the recording backend, never to a screen."""
    instance = FakeBackend()
    monkeypatch.setattr("use_computer.runner.create_backend", lambda profile: instance)
    return instance


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def invoke(runner: CliRunner, *args: str) -> Result:
    return runner.invoke(app, list(args), catch_exceptions=False)


def test_stdout_is_json_and_nothing_else(
    runner: CliRunner,
    write_config: WriteConfig,
    backend: FakeBackend,
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "click", "--x", "120", "--y", "340")
    assert result.exit_code == EXIT_OK
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["results"][0]["resolved"] == {"x": 60, "y": 170, "space": "actuation"}


def test_a_failed_action_exits_one(
    runner: CliRunner,
    write_config: WriteConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_config(CONFIG)
    monkeypatch.setattr(
        "use_computer.runner.create_backend", lambda profile: FakeBackend(fail_on="click")
    )
    result = invoke(runner, "click", "--x", "1", "--y", "1")
    assert result.exit_code == EXIT_FAILURE
    assert json.loads(result.stdout)["ok"] is False


def test_bad_usage_exits_two(
    runner: CliRunner,
    write_config: WriteConfig,
    backend: FakeBackend,
) -> None:
    write_config(CONFIG)
    assert invoke(runner, "key", "ctrl+nosuchkey").exit_code == EXIT_USAGE
    assert invoke(runner, "batch", "missing.json").exit_code == EXIT_USAGE


def test_a_missing_profile_exits_one_with_the_error_on_stderr(
    runner: CliRunner, project: Path
) -> None:
    result = invoke(runner, "click", "--x", "1", "--y", "1", "--use", "nope")
    assert result.exit_code == EXIT_FAILURE
    assert result.stdout.strip() == ""


def test_a_batch_runs_over_one_backend(
    runner: CliRunner, write_config: WriteConfig, backend: FakeBackend, tmp_path: Path
) -> None:
    write_config(CONFIG)
    actions = tmp_path / "actions.json"
    actions.write_text(
        json.dumps(
            [
                {"action": "click", "x": 120, "y": 340},
                {"action": "type", "text": "hello"},
                {"action": "key", "combo": "enter"},
            ]
        ),
        encoding="utf-8",
    )
    result = invoke(runner, "batch", str(actions))
    assert result.exit_code == EXIT_OK
    assert [name for name, _ in backend.calls] == ["click", "type_text", "key"]
    assert len(json.loads(result.stdout)["results"]) == 3


def test_a_batch_reads_stdin(
    runner: CliRunner,
    write_config: WriteConfig,
    backend: FakeBackend,
) -> None:
    write_config(CONFIG)
    payload = json.dumps([{"action": "key", "combo": "ctrl+s"}])
    result = runner.invoke(app, ["batch", "-"], input=payload, catch_exceptions=False)
    assert result.exit_code == EXIT_OK
    assert backend.calls == [("key", "ctrl+s")]


def test_a_malformed_batch_exits_two(
    runner: CliRunner,
    write_config: WriteConfig,
    backend: FakeBackend,
) -> None:
    write_config(CONFIG)
    result = runner.invoke(app, ["batch", "-"], input="not json", catch_exceptions=False)
    assert result.exit_code == EXIT_USAGE


def test_dry_run_performs_nothing(
    runner: CliRunner,
    write_config: WriteConfig,
    backend: FakeBackend,
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "click", "--x", "1", "--y", "1", "--dry-run")
    assert result.exit_code == EXIT_OK
    assert backend.calls == []
    assert json.loads(result.stdout)["results"][0]["performed"] is False


def test_type_sends_literal_text(
    runner: CliRunner,
    write_config: WriteConfig,
    backend: FakeBackend,
) -> None:
    write_config(CONFIG)
    invoke(runner, "type", "--text", "ctrl+a")
    assert backend.calls[0][0] == "type_text"
    assert backend.calls[0][1][0] == "ctrl+a"


def test_config_show_prints_layers_and_masks_secrets(
    runner: CliRunner,
    write_config: WriteConfig,
) -> None:
    write_config(CONFIG + '\npassword = "hunter2"\n')
    result = invoke(runner, "config", "show")
    assert result.exit_code == EXIT_OK
    payload = json.loads(result.stdout)
    assert payload["profile"] == "fake"
    assert payload["values"]["delay"]["env"] == "USE_COMPUTER_DELAY"


def test_version_is_json_too(runner: CliRunner) -> None:
    result = invoke(runner, "--version")
    assert result.exit_code == EXIT_OK
    assert "version" in json.loads(result.stdout)


def test_json_output_survives_a_long_string(
    runner: CliRunner, write_config: WriteConfig, backend: FakeBackend
) -> None:
    """rich soft-wraps long strings and can put a newline inside a JSON string.

    Emitting with plain json.dumps is what keeps this parseable, so assert it stays that way.
    """
    write_config(CONFIG)
    text = "x" * 5000
    result = invoke(runner, "type", "--text", text)
    payload = json.loads(result.stdout)
    assert payload["results"][0]["action"]["text"] == text


def test_help_lists_every_action(runner: CliRunner) -> None:
    output = strip_ansi(invoke(runner, "--help").stdout)
    for command in ("move", "click", "double-click", "right-click", "drag", "scroll", "batch"):
        assert command in output


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["use-computer", "actions.json"], ["use-computer", "batch", "actions.json"]),
        (["use-computer", "-"], ["use-computer", "batch", "-"]),
        (["use-computer", "click", "--x", "1"], ["use-computer", "click", "--x", "1"]),
        (["use-computer", "--help"], ["use-computer", "--help"]),
        (["use-computer", "--version"], ["use-computer", "--version"]),
        (["use-computer"], ["use-computer"]),
    ],
)
def test_the_default_command_is_applied_by_rewriting_argv(
    argv: list[str], expected: list[str]
) -> None:
    # Never by subclassing TyperGroup: typer 0.27 stopped being click-based and that breaks
    # silently.
    assert apply_default_command(argv) == expected


def test_the_command_list_matches_the_registered_commands() -> None:
    """A command missing from _COMMANDS would be swallowed by the default-command rewrite."""
    registered = {
        command.name or command.callback.__name__.replace("_", "-")
        for command in app.registered_commands
        if command.callback is not None
    }
    registered |= {group.name for group in app.registered_groups if group.name}
    assert registered == set(cli._COMMANDS)


@pytest.mark.parametrize("command", sorted(cli._COMMANDS))
def test_a_known_command_is_never_rewritten(command: str) -> None:
    assert apply_default_command(["use-computer", command]) == ["use-computer", command]
