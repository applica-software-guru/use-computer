"""The CLI contract: JSON on stdout, diagnostics on stderr, and the documented exit codes."""

from __future__ import annotations

import json
import sys
from importlib import metadata
from pathlib import Path

import pytest
from typer.testing import CliRunner

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import use_computer
from tests.conftest import CliResult, WriteConfig, strip_ansi
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


def invoke(runner: CliRunner, *args: str, input: str | None = None) -> CliResult:
    return runner.invoke(app, list(args), catch_exceptions=False, input=input)


def test_the_envelope_is_json_and_nothing_else(
    runner: CliRunner,
    write_config: WriteConfig,
    backend: FakeBackend,
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "click", "--x", "120", "--y", "340", "--format", "json")
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
    result = invoke(runner, "click", "--x", "1", "--y", "1", "--format", "json")
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
    result = invoke(runner, "batch", str(actions), "--format", "json")
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
    result = invoke(runner, "click", "--x", "1", "--y", "1", "--dry-run", "--format", "json")
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
    result = invoke(runner, "config", "show", "--format", "json")
    assert result.exit_code == EXIT_OK
    payload = json.loads(result.stdout)
    assert payload["profile"] == "fake"
    assert payload["values"]["delay"]["env"] == "USE_COMPUTER_DELAY"


def test_config_show_reads_as_lines_by_default(
    runner: CliRunner,
    write_config: WriteConfig,
) -> None:
    # The command named first when a profile misbehaves. Two kilobytes on one line is the worst
    # possible answer to "why is this profile behaving like that".
    write_config(CONFIG)
    result = invoke(runner, "config", "show")
    assert result.exit_code == EXIT_OK
    assert not result.stdout.lstrip().startswith("{")
    lines = result.stdout.splitlines()
    assert lines[0].split() == ["key", "value", "layer", "env"]
    assert any(
        line.startswith("delay") and "USE_COMPUTER_DELAY" in line for line in lines
    )
    assert "profile: fake" in result.stdout


def test_config_show_prints_a_setting_the_way_it_is_typed(
    runner: CliRunner, write_config: WriteConfig
) -> None:
    # `CoordinateSpace.SCREENSHOT` is a repr, not a value anybody could put in a config file.
    write_config(CONFIG)
    result = invoke(runner, "config", "show")
    assert any(
        line.startswith("space") and "screenshot" in line
        for line in result.stdout.splitlines()
    )


def test_version_is_text_like_everything_else(runner: CliRunner) -> None:
    # A contract is worth what its least consistent command is worth.
    result = invoke(runner, "--version")
    assert result.exit_code == EXIT_OK
    assert result.stdout.startswith("use-computer ")
    assert not result.stdout.lstrip().startswith("{")


def test_json_output_survives_a_long_string(
    runner: CliRunner, write_config: WriteConfig, backend: FakeBackend
) -> None:
    """rich soft-wraps long strings and can put a newline inside a JSON string.

    Emitting with plain json.dumps is what keeps this parseable, so assert it stays that way.
    """
    write_config(CONFIG)
    text = "x" * 5000
    result = invoke(runner, "type", "--text", text, "--format", "json")
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


def test_the_version_is_read_from_the_distribution_that_is_actually_published() -> None:
    """importlib.metadata is keyed by the distribution name, not the import package.

    They differ here, so a rename that misses one of them silently reports 0.0.0.
    """
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["name"]
    assert declared == use_computer.DISTRIBUTION
    assert use_computer.__version__ == metadata.version(declared)
    assert use_computer.__version__ != "0.0.0"


# --- element addressing --------------------------------------------------------------------------


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> object:
    """Every element command in these tests reads the canned tree, never a real desktop."""
    from tests.fake_provider import FakeProvider

    instance = FakeProvider()
    monkeypatch.setattr("use_computer.runner.create_provider", lambda backend: instance)
    return instance


def test_the_envelope_carries_objects_not_a_rendering(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    # Asking for the envelope is asking to parse, so it carries the structure and not the prose.
    write_config(CONFIG)
    result = invoke(runner, "tree", "--format", "json")
    assert result.exit_code == EXIT_OK
    tree = json.loads(result.stdout)["results"][0]["tree"]
    assert tree["text"] is None
    assert tree["root"]["role"] == "dialog"
    assert tree["reason"] is None


def test_tree_returns_objects_when_asked(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "tree", "--format", "json")
    assert result.exit_code == EXIT_OK
    tree = json.loads(result.stdout)["results"][0]["tree"]
    assert tree["text"] is None
    assert tree["root"]["role"] == "dialog"


def test_windows_renders_too(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "windows", "--format", "json")
    assert result.exit_code == EXIT_OK
    payload = json.loads(result.stdout)["results"][0]["windows"]
    assert payload["text"] is None
    assert [w["title"] for w in payload["windows"]] == ["Conferma"]


def test_clicking_by_name_reports_the_rung_it_took(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "click", "--role", "button", "--name", "Invia", "--format", "json")
    assert result.exit_code == EXIT_OK
    item = json.loads(result.stdout)["results"][0]
    assert item["via"] == "action"
    assert item["matched"]["id"] == "0/1/0"
    assert provider.calls == [("0/1/0", "click", None)]  # type: ignore[attr-defined]


def test_an_ambiguous_selector_lists_the_candidates_on_stderr(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "click", "--role", "button")
    assert result.exit_code == EXIT_FAILURE
    err = strip_ansi(result.stderr)
    assert "AmbiguousNodeError" in err
    assert "0/1/0" in err and "'Invia'" in err
    assert "0/1/1" in err and "'Annulla'" in err


def test_an_element_command_without_a_selector_is_a_usage_error(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "focus")
    assert result.exit_code == EXIT_USAGE
    assert "--id" in strip_ansi(result.stderr)


def test_a_coordinate_and_a_selector_together_is_rejected_by_the_cli(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "click", "--x", "1", "--y", "2", "--role", "button")
    assert result.exit_code == EXIT_USAGE
    assert "not both" in strip_ansi(result.stderr)


def test_set_value_requires_its_value(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "set-value", "--role", "text")
    assert result.exit_code == EXIT_USAGE


def test_every_element_command_is_a_known_command_for_the_default_dispatch() -> None:
    for name in ("tree", "focus", "toggle", "expand", "collapse", "select", "set-value"):
        assert apply_default_command(["use-computer", name]) == ["use-computer", name]


# --- a missing required option is bad usage, on every supported typer ----------------------------


@pytest.mark.parametrize(
    ("argv", "flag"),
    [
        (["type"], "--text"),
        (["drag"], "--from-x"),
        (["scroll"], "--amount"),
        (["set-value", "--role", "text"], "--value"),
    ],
)
def test_a_missing_required_option_exits_2_and_names_the_flag(
    runner: CliRunner, write_config: WriteConfig, argv: list[str], flag: str
) -> None:
    # typer does not enforce a required option the same way across the supported range: at the
    # 0.16 floor it hands the command None, and the model then reports *failure* where the
    # contract promises *bad usage*. An agent branching on the exit code would retry a call that
    # was simply wrong. These run in the matrix, because the floor is the only place it shows.
    write_config(CONFIG)
    result = invoke(runner, *argv)
    assert result.exit_code == EXIT_USAGE
    assert flag in strip_ansi(result.stderr)


def test_an_error_message_keeps_its_brackets(
    runner: CliRunner, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    # rich parses [...] as markup, so an error naming `use-computer-cli[tree]` silently lost the
    # extra it exists to name. Assert on a message that contains brackets: one that does not
    # proves nothing.
    from use_computer.errors import UITreeUnavailableError

    def refuse(profile: object) -> object:
        raise UITreeUnavailableError("needs 'gi'.", extra="tree")

    write_config(CONFIG)
    monkeypatch.setattr("use_computer.runner.create_backend", refuse)
    result = invoke(runner, "windows")
    assert result.exit_code == EXIT_FAILURE
    assert 'use-computer-cli[tree]' in strip_ansi(result.stderr)


def test_a_candidate_name_keeps_its_brackets(
    runner: CliRunner, backend: FakeBackend, write_config: WriteConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.fake_provider import FakeProvider, node

    root = node(
        "0",
        "window",
        "App",
        children=(
            node("0/0", "button", "[draft] Send", box=(0, 0, 10, 10)),
            node("0/1", "button", "[draft] Save", box=(0, 20, 10, 10)),
        ),
    )
    monkeypatch.setattr(
        "use_computer.runner.create_provider", lambda backend: FakeProvider(root=root)
    )
    write_config(CONFIG)
    result = invoke(runner, "click", "--role", "button")
    assert result.exit_code == EXIT_FAILURE
    assert "[draft] Send" in strip_ansi(result.stderr)


# --- text is the output, JSON is the thing you ask for --------------------------------------------


def test_windows_prints_columns_and_no_json(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "windows")
    assert result.exit_code == EXIT_OK
    out = strip_ansi(result.stdout)
    assert out.startswith("id")  # the header, not a brace
    assert "Conferma" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_tree_prints_bare(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "tree")
    assert result.exit_code == EXIT_OK
    out = strip_ansi(result.stdout)
    assert out.startswith('# id role "name"')
    assert '"Invia"' in out


def test_an_action_is_one_line(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    result = invoke(runner, "click", "--role", "button", "--name", "Invia")
    assert result.exit_code == EXIT_OK
    lines = strip_ansi(result.stdout).strip().split("\n")
    assert len(lines) == 2  # the action, then the closing line
    assert "click button 'Invia' at 0/1/0" in lines[0]
    assert "via the platform API" in lines[0]


def test_a_failure_splits_what_happened_from_why(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    # stdout says what happened, stderr says why. Neither repeats the other, so a reader
    # scrolling back never has to work out which stream is which.
    write_config(CONFIG)
    result = invoke(runner, "click", "--role", "button")
    assert result.exit_code == EXIT_FAILURE
    out = strip_ansi(result.stdout).strip()
    assert out.startswith("failed at action 1")
    assert "AmbiguousNodeError" not in out
    assert "AmbiguousNodeError" in strip_ansi(result.stderr)


def test_the_envelope_is_one_flag_away(
    runner: CliRunner, backend: FakeBackend, provider: object, write_config: WriteConfig
) -> None:
    # The contract holds for every invocation that does not ask for prose, and --human is never
    # inferred from isatty(): agents run under a pty too.
    write_config(CONFIG)
    result = invoke(runner, "windows", "--format", "json")
    assert json.loads(result.stdout)["ok"] is True


def test_verify_reports_its_answer_and_where_it_looked(
    runner: CliRunner, backend: FakeBackend, write_config: WriteConfig
) -> None:
    # --verify exists to give feedback. A flag whose whole purpose is feedback must not be silent
    # in the format everyone gets by default.
    backend.colours = [(0, 0, 0), (255, 255, 255)]
    write_config(CONFIG)
    result = invoke(runner, "click", "--x", "10", "--y", "10", "--verify")
    assert result.exit_code == EXIT_OK
    out = strip_ansi(result.stdout)
    assert "changed" in out
    assert ".png" in out  # the picture it already paid for, so nobody asks for it twice


def test_an_unchanged_screen_says_so_in_a_word(
    runner: CliRunner, backend: FakeBackend, write_config: WriteConfig
) -> None:
    # `unchanged` is the one an agent has to notice: it means the coordinate was stale.
    backend.colours = [(0, 0, 0), (0, 0, 0)]
    write_config(CONFIG)
    result = invoke(runner, "click", "--x", "10", "--y", "10", "--verify")
    assert "unchanged" in strip_ansi(result.stdout)


def test_every_run_ends_with_what_the_envelope_carried(
    runner: CliRunner, backend: FakeBackend, write_config: WriteConfig
) -> None:
    # Cheap must not mean lossy. The envelope was dropped for costing 177 tokens, not because the
    # facts in it were worthless -- the scale especially, which is what an agent needs the moment
    # a coordinate lands somewhere surprising.
    write_config(CONFIG)
    result = invoke(runner, "click", "--x", "10", "--y", "10")
    last = strip_ansi(result.stdout).strip().split("\n")[-1]
    assert last.startswith("ok — ")
    assert "profile fake" in last
    assert "backend fake" in last
    assert "screen 1280x800" in last
    assert "scale 2" in last


def test_a_failure_says_which_action_it_was(
    runner: CliRunner, backend: FakeBackend, write_config: WriteConfig
) -> None:
    write_config(CONFIG)
    backend.fail_on = "click"
    result = invoke(runner, "click", "--x", "10", "--y", "10")
    assert result.exit_code == EXIT_FAILURE
    assert "failed at action 1" in strip_ansi(result.stdout)


def test_an_unknown_scale_is_named_not_omitted(
    runner: CliRunner, backend: FakeBackend, write_config: WriteConfig
) -> None:
    # Refusing to guess a scale is only useful if the caller can see that it is unknown.
    backend.scale = None
    write_config(CONFIG)
    result = invoke(runner, "screenshot")
    assert "scale unknown" in strip_ansi(result.stdout)


def test_a_batch_names_the_screenshot_directory_once(
    runner: CliRunner, backend: FakeBackend, write_config: WriteConfig, tmp_path: Path
) -> None:
    # A path is 23 tokens, and a batch of five verified actions repeats the same directory in
    # every one of them -- 70 tokens of it, five times what the whole closing line costs.
    backend.colours = [(0, 0, 0), (255, 255, 255)]
    write_config(CONFIG)
    plan = '[{"action":"click","x":1,"y":1},{"action":"click","x":2,"y":2}]'
    result = invoke(runner, "batch", "-", "--verify", input=plan)
    out = strip_ansi(result.stdout)
    assert "screenshots in " in out.split("\n")[-2]
    for line in out.split("\n"):
        if line.startswith("  ") and line.strip().endswith(".png"):
            assert "/" not in line  # a filename, because the directory was already named


def test_a_single_screenshot_keeps_its_whole_path(
    runner: CliRunner, backend: FakeBackend, write_config: WriteConfig
) -> None:
    # Nothing to save with one file, and an indirection to read would cost more than it returns.
    write_config(CONFIG)
    result = invoke(runner, "screenshot")
    assert strip_ansi(result.stdout).split("\n")[0].startswith("/")
    assert "screenshots in " not in strip_ansi(result.stdout)


def test_the_skill_command_answers_in_text(runner: CliRunner) -> None:
    # The command an agent runs to find out whether its own instructions are current, and the last
    # one still replying with a JSON object after the contract was inverted.
    result = invoke(runner, "skill", "status")
    assert result.exit_code == EXIT_OK
    assert not result.stdout.lstrip().startswith("{")
    assert result.stdout.split()[0] == "status"


def test_the_skill_command_still_has_a_json_form(runner: CliRunner) -> None:
    result = invoke(runner, "skill", "status", "--format", "json")
    assert result.exit_code == EXIT_OK
    assert json.loads(result.stdout)["action"] == "status"
