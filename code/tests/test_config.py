"""Layered configuration, and the `config show` that makes it debuggable."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import WriteConfig
from use_computer.config import PROJECT_DIR, find_project_root, load, xdg_config_dir
from use_computer.errors import ConfigError

CONFIG = """
default-profile = "laptop"
delay = 0.5

[profiles.laptop]
backend = "local"
allow-local = true

[profiles.staging]
backend = "vnc"
host = "10.0.0.5"
port = 5900
scale = 1.0
"""


def test_the_project_root_is_found_by_walking_up(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nested = project / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert find_project_root() == project.resolve()


def test_no_project_root_above_the_checkout_is_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert find_project_root() is None


def test_the_selected_profile_supplies_the_backend(write_config: WriteConfig) -> None:
    write_config(CONFIG)
    resolved = load(profile="staging", environ={})
    assert resolved.profile.backend == "vnc"
    assert resolved.profile.host == "10.0.0.5"
    assert resolved.profile.scale == 1.0


def test_the_default_profile_is_used_when_none_is_given(write_config: WriteConfig) -> None:
    write_config(CONFIG)
    assert load(environ={}).profile_name == "laptop"


def test_precedence_runs_cli_over_env_over_dotenv_over_profile_over_config(
    write_config: WriteConfig, project: Path
) -> None:
    write_config(CONFIG)

    from_config = load(profile="staging", environ={})
    assert from_config.get("delay") == 0.5
    assert from_config.values["delay"].layer == "config"

    (project / PROJECT_DIR / ".env").write_text("USE_COMPUTER_DELAY=0.3\n", encoding="utf-8")
    from_dotenv = load(profile="staging", environ={})
    assert from_dotenv.get("delay") == 0.3
    assert from_dotenv.values["delay"].layer == "dotenv"

    from_env = load(profile="staging", environ={"USE_COMPUTER_DELAY": "0.2"})
    assert from_env.get("delay") == 0.2
    assert from_env.values["delay"].layer == "env"

    from_cli = load({"delay": 0.1}, profile="staging", environ={"USE_COMPUTER_DELAY": "0.2"})
    assert from_cli.get("delay") == 0.1
    assert from_cli.values["delay"].layer == "cli"


def test_a_profile_key_overrides_a_top_level_key(write_config: WriteConfig) -> None:
    write_config(CONFIG + "\n[profiles.slow]\nbackend = 'vnc'\nhost = 'h'\ndelay = 2.0\n")
    resolved = load(profile="slow", environ={})
    assert resolved.get("delay") == 2.0
    assert resolved.values["delay"].layer == "profile"


def test_a_profile_secret_can_come_from_the_environment(write_config: WriteConfig) -> None:
    write_config(CONFIG)
    resolved = load(
        profile="staging", environ={"USE_COMPUTER_PROFILES__STAGING__PASSWORD": "hunter2"}
    )
    assert resolved.profile.password == "hunter2"


def test_config_show_names_the_layer_and_the_variable(write_config: WriteConfig) -> None:
    write_config(CONFIG)
    payload = load(profile="staging", environ={}).show()
    assert payload["values"]["delay"]["layer"] == "config"
    assert payload["values"]["delay"]["env"] == "USE_COMPUTER_DELAY"
    assert payload["profile"] == "staging"


def test_config_show_masks_secrets(write_config: WriteConfig) -> None:
    write_config(CONFIG)
    payload = load(
        profile="staging", environ={"USE_COMPUTER_PROFILES__STAGING__PASSWORD": "hunter2"}
    ).show()
    assert payload["values"]["password"]["value"] == "***"


def test_unknown_keys_warn_including_inside_an_unselected_profile(
    write_config: WriteConfig,
) -> None:
    write_config(
        CONFIG + "\ntyop = 1\n\n[profiles.other]\nbackend = 'vnc'\nhsot = 'typo'\n"
    )
    warnings = load(profile="staging", environ={}).warnings
    joined = "\n".join(warnings)
    assert "typo" in joined or "hsot" in joined
    assert "'tyop'" in joined  # the top-level typo is reported too
    assert "'other'" in joined  # ... and it names the unselected profile


def test_a_missing_profile_is_a_clear_error(write_config: WriteConfig) -> None:
    write_config(CONFIG)
    resolved = load(profile="nope", environ={})
    with pytest.raises(ConfigError) as excinfo:
        _ = resolved.profile
    assert "nope" in str(excinfo.value)


def test_no_profile_at_all_says_what_to_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError) as excinfo:
        _ = load(environ={}).profile
    assert "--use" in str(excinfo.value)


def test_a_bad_boolean_in_the_environment_names_the_variable(write_config: WriteConfig) -> None:
    write_config(CONFIG)
    with pytest.raises(ConfigError) as excinfo:
        load(profile="laptop", environ={"USE_COMPUTER_ALLOW_LOCAL": "maybe"})
    assert "USE_COMPUTER_ALLOW_LOCAL" in str(excinfo.value)


def test_the_xdg_config_directory_is_used_never_a_cache_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "/somewhere/config")
    assert xdg_config_dir() == Path("/somewhere/config/use-computer")


def test_a_profile_field_default_is_reported_like_any_other(write_config: WriteConfig) -> None:
    write_config(CONFIG)
    payload = load(profile="staging", environ={}).show()
    assert payload["values"]["port"] == {
        "value": 5900,
        "layer": "profile",
        "env": "USE_COMPUTER_PORT",
        "source": payload["config-file"],
    }
