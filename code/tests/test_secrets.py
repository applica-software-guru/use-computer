"""The secret store, and the one invariant it exists to hold.

*A secret leaves the store into the keyboard, and never into stdout.* Most of these tests are that
sentence: the value reaches the backend, and appears in no line, no envelope and no error anywhere
above it. The rest cover the store itself -- where it is written, with what mode, and what happens
when the name is not there.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.conftest import CliResult, strip_ansi
from tests.fake_backend import FakeBackend
from use_computer.actions import SetValueAction, TypeAction
from use_computer.cli import app
from use_computer.config import GITIGNORE_LINES, PROJECT_DIR, Settings
from use_computer.errors import SecretNotFoundError
from use_computer.runner import Session
from use_computer.secrets import STORE_FILENAME, Secrets, global_store, project_store
from use_computer.tree import NodeSelector

VALUE = "correct-horse-battery-staple"

runner = CliRunner()


def invoke(*args: str, stdin: str | None = None) -> CliResult:
    return runner.invoke(app, list(args), input=stdin)


def session(backend: FakeBackend, **settings: object) -> Session:
    return Session(
        backend,
        profile="fake",
        settings=Settings(**settings),  # type: ignore[arg-type]
        secrets=Secrets(),
    )


# --- the store ---------------------------------------------------------------------------------


def test_a_stored_secret_is_written_readable_only_by_its_owner() -> None:
    invoke("secret", "set", "gh-token", stdin=VALUE)
    path = global_store().path
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_setting_the_same_name_twice_rotates_it() -> None:
    invoke("secret", "set", "gh-token", stdin="first")
    invoke("secret", "set", "gh-token", stdin="second")
    found = global_store().get("gh-token")
    assert found is not None and found.get_secret_value() == "second"


def test_project_store_is_separate_and_wins_over_the_global_one(project: Path) -> None:
    invoke("secret", "set", "shared", stdin="global-value")
    invoke("secret", "set", "shared", "--project", stdin="project-value")

    store = project_store()
    assert store is not None
    assert store.path == project / PROJECT_DIR / STORE_FILENAME

    found = Secrets().require("shared")
    assert found.get_secret_value() == "project-value"


def test_the_project_store_is_gitignored() -> None:
    assert STORE_FILENAME in GITIGNORE_LINES


def test_project_outside_a_project_says_so_rather_than_writing_somewhere() -> None:
    result = invoke("secret", "set", "gh-token", "--project", stdin=VALUE)
    assert result.exit_code != 0
    assert "no project here" in strip_ansi(result.stderr)


def test_the_environment_supplies_one_for_a_machine_with_nobody_at_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoke("secret", "set", "gh-token", stdin="from-the-file")
    monkeypatch.setenv("USE_COMPUTER_SECRET_GH_TOKEN", "from-the-env")
    assert Secrets().require("gh-token").get_secret_value() == "from-the-env"


def test_an_empty_value_is_refused() -> None:
    result = invoke("secret", "set", "gh-token", stdin="\n")
    assert result.exit_code == 2
    assert "cannot be empty" in strip_ansi(result.stderr)


def test_a_name_that_would_not_survive_the_file_is_refused() -> None:
    result = invoke("secret", "set", 'oops"name', stdin=VALUE)
    assert result.exit_code != 0
    assert "usable secret name" in strip_ansi(result.stderr)


def test_removing_a_name_that_is_not_there_is_a_failure_not_a_silence() -> None:
    result = invoke("secret", "rm", "never-stored")
    assert result.exit_code == 1
    assert "no secret named" in strip_ansi(result.stderr)


# --- the invariant -----------------------------------------------------------------------------


def test_there_is_no_command_that_prints_a_secret() -> None:
    """`secret get` is absent by design, not by omission."""
    invoke("secret", "set", "gh-token", stdin=VALUE)
    assert invoke("secret", "get", "gh-token").exit_code != 0
    for args in (("secret", "list"), ("secret", "list", "--format", "json")):
        result = invoke(*args)
        assert result.exit_code == 0
        assert "gh-token" in result.stdout
        assert VALUE not in result.stdout


def test_list_names_the_store_but_never_the_value() -> None:
    invoke("secret", "set", "gh-token", stdin=VALUE)
    payload = json.loads(invoke("secret", "list", "--format", "json").stdout)
    assert payload["secrets"] == [
        {"name": "gh-token", "store": "global", "set-at": payload["secrets"][0]["set-at"]}
    ]
    assert VALUE not in json.dumps(payload)


def test_the_value_reaches_the_keyboard_and_nothing_else() -> None:
    invoke("secret", "set", "gh-token", stdin=VALUE)
    backend = FakeBackend()
    result = session(backend).run([TypeAction(secret="gh-token")])

    assert result.ok is True
    assert backend.calls == [("type_text", (VALUE, 0.02))]

    # Every rendering of what just happened, and the value is in none of them.
    assert VALUE not in json.dumps(result.model_dump(mode="json"))
    assert VALUE not in repr(result)
    assert VALUE not in str(result.results[0].action)


def test_set_value_sends_a_secret_through_the_platform_api() -> None:
    from tests.fake_provider import FakeProvider  # local: it builds a tree fixture

    invoke("secret", "set", "pw", stdin=VALUE)
    provider = FakeProvider()
    backend = FakeBackend()
    outcome = Session(
        backend,
        profile="fake",
        settings=Settings(),
        provider=provider,
        secrets=Secrets(),
    ).run([SetValueAction(selector=NodeSelector(role="text"), secret="pw")])

    assert outcome.ok is True, outcome.results[0].error
    assert provider.calls == [("0/0/0", "set_value", VALUE)]
    assert VALUE not in json.dumps(outcome.model_dump(mode="json"))


def test_the_result_line_carries_the_name_and_the_count_but_not_the_text() -> None:
    invoke("secret", "set", "gh-token", stdin=VALUE)
    backend = FakeBackend()
    result = session(backend).run([TypeAction(secret="gh-token")])

    from use_computer.cli import _text_lines

    line = _text_lines(result)
    assert f"{len(VALUE)} chars (secret gh-token)" in line
    assert VALUE not in line


def test_a_literal_type_still_prints_its_text() -> None:
    backend = FakeBackend()
    result = session(backend).run([TypeAction(text="hello")])

    from use_computer.cli import _text_lines

    assert "5 chars 'hello'" in _text_lines(result)


# --- refusals ----------------------------------------------------------------------------------


def test_a_missing_secret_names_the_command_and_forbids_the_obvious_repair() -> None:
    with pytest.raises(SecretNotFoundError) as caught:
        Secrets().require("gh-token")
    message = str(caught.value)
    assert "use-computer secret set gh-token" in message
    assert "Do not ask them for the value here" in message


def test_a_missing_secret_does_not_list_the_ones_that_exist() -> None:
    invoke("secret", "set", "other-token", stdin=VALUE)
    with pytest.raises(SecretNotFoundError) as caught:
        Secrets().require("gh-token")
    assert "other-token" not in str(caught.value)


def test_dry_run_resolves_existence_so_a_mistyped_name_fails_the_rehearsal() -> None:
    backend = FakeBackend()
    result = session(backend, dry_run=True).run([TypeAction(secret="never-stored")])

    assert result.ok is False
    assert backend.calls == []
    assert result.results[0].error is not None
    assert result.results[0].error.type == "SecretNotFoundError"


def test_dry_run_with_a_stored_secret_still_types_nothing() -> None:
    invoke("secret", "set", "gh-token", stdin=VALUE)
    backend = FakeBackend()
    result = session(backend, dry_run=True).run([TypeAction(secret="gh-token")])

    assert result.ok is True
    assert backend.calls == []
    assert VALUE not in json.dumps(result.model_dump(mode="json"))


# --- the model ---------------------------------------------------------------------------------


def test_an_action_needs_a_literal_or_a_secret() -> None:
    with pytest.raises(ValueError):
        TypeAction()


def test_an_action_refuses_a_literal_and_a_secret_together() -> None:
    with pytest.raises(ValueError):
        TypeAction(text="hello", secret="gh-token")


def test_the_cli_refuses_both_rather_than_choosing_one() -> None:
    result = invoke("type", "--text", "hello", "--secret", "gh-token")
    assert result.exit_code == 2
    assert "not both" in strip_ansi(result.stderr)


def test_a_batch_names_a_secret_instead_of_carrying_one(tmp_path: Path) -> None:
    from use_computer.actions import ActionListAdapter

    actions = ActionListAdapter.validate_python(
        [{"action": "type", "secret": "vpn-password"}]
    )
    assert isinstance(actions[0], TypeAction)
    assert actions[0].secret == "vpn-password"
    assert actions[0].text is None


def test_verification_never_photographs_a_screen_a_secret_went_into() -> None:
    invoke("secret", "set", "gh-token", stdin=VALUE)
    backend = FakeBackend(colours=[(0, 0, 0), (255, 255, 255)])
    result = session(backend, verify=True).run([TypeAction(secret="gh-token")])

    assert result.ok is True
    assert [name for name, _ in backend.calls] == ["type_text"]
    assert result.results[0].screenshot is None
    assert result.results[0].change is None
    assert result.results[0].verify_skipped is True


def test_a_skipped_verification_says_so_rather_than_reading_as_unchanged() -> None:
    invoke("secret", "set", "gh-token", stdin=VALUE)
    backend = FakeBackend(colours=[(0, 0, 0), (255, 255, 255)])
    result = session(backend, verify=True).run([TypeAction(secret="gh-token")])

    from use_computer.cli import _text_lines

    assert "not verified (secret)" in _text_lines(result)


def test_verification_still_works_for_an_ordinary_type() -> None:
    backend = FakeBackend(colours=[(0, 0, 0), (255, 255, 255)])
    result = session(backend, verify=True).run([TypeAction(text="hello")])

    assert result.results[0].change is not None
    assert result.results[0].verify_skipped is False
