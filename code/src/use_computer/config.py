"""Configuration: project root discovery, named profiles, and layered resolution.

Adding a backend target is editing a file, not writing code -- so the config file is the
feature, and `config show` is what makes a misconfiguration debuggable in one command. Every
resolved value carries the layer it came from, tracked as data during resolution rather than
reconstructed for display.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from use_computer.compare import DEFAULT_THRESHOLD
from use_computer.coordinates import CoordinateSpace
from use_computer.errors import ConfigError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 only
    import tomli as tomllib

#: The directory that marks a project root, found by walking up the way git finds its own.
PROJECT_DIR = ".use-computer"
CONFIG_FILENAME = "config.toml"
ENV_FILENAME = ".env"

#: Environment prefix. Declared by :class:`Settings` and reused by the resolver, so the two
#: cannot drift apart.
ENV_PREFIX = "USE_COMPUTER_"

#: Layers, highest precedence first. The tuple *is* the precedence rule.
LAYERS = ("cli", "env", "dotenv", "profile", "config", "global-config", "default")
Layer = Literal["cli", "env", "dotenv", "profile", "config", "global-config", "default"]

#: Fields whose value is masked wherever configuration is printed.
SECRET_FIELDS = frozenset({"password"})


class BackendProfile(BaseModel):
    """A named backend target from the config file."""

    model_config = ConfigDict(extra="ignore")

    name: str
    backend: Literal["local", "vnc"]
    host: str | None = None
    port: int = 5900
    password: str | None = None
    allow_local: bool = False
    scale: float | None = Field(
        default=None,
        description="Explicit screenshot/actuation ratio. An explicit scale is trusted.",
    )


class Settings(BaseSettings):
    """The settings model. Declares the environment prefix the resolver scans with."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, extra="ignore")

    default_profile: str | None = None
    delay: float = 0.0
    typing_rate: float = 0.02
    verify: bool = False
    verify_threshold: float = DEFAULT_THRESHOLD
    space: CoordinateSpace = CoordinateSpace.SCREENSHOT
    screenshot_dir: Path | None = Field(
        default=None,
        description="Where screenshots go when no path was given. None means the XDG data dir.",
    )
    dry_run: bool = False
    allow_local: bool = False
    continue_on_error: bool = False
    tree_max_nodes: int = Field(
        default=400,
        ge=1,
        description="The node budget. Beyond it the tree is truncated and says so.",
    )
    tree_depth: int = Field(default=20, ge=0, description="Maximum depth from the scope root.")
    tree_max_text: int = Field(
        default=200,
        ge=0,
        description="Longest name or value a node reports. Identification, not content.",
    )
    tree_fallback: bool = Field(
        default=True, description="Capture a screenshot when the tree cannot answer."
    )


#: Scalar settings, usable at the top level of the config file and inside a profile.
SCALAR_FIELDS = tuple(Settings.model_fields)

#: Keys accepted at the top level of a config file.
TOP_LEVEL_KEYS = frozenset({*SCALAR_FIELDS, "profiles"})

#: Defaults for the fields a profile owns, which are not part of :class:`Settings`.
PROFILE_DEFAULTS: dict[str, Any] = {"port": 5900}

#: Keys accepted inside a profile. `default_profile` is meaningless there.
PROFILE_KEYS = frozenset(
    {*SCALAR_FIELDS, "backend", "host", "port", "password", "scale"} - {"default_profile"}
)


class ResolvedValue(BaseModel):
    """One setting, with the layer it came from."""

    model_config = ConfigDict(frozen=True)

    value: Any
    layer: Layer
    env: str = Field(description="The variable that would override this value.")
    source: str | None = Field(default=None, description="File the value was read from.")
    secret: bool = False

    def display(self) -> Any:
        return "***" if self.secret and self.value is not None else self.value


class ResolvedConfig(BaseModel):
    """Everything a run needs, plus where each value came from."""

    model_config = ConfigDict(frozen=True)

    project_root: Path | None
    config_file: Path | None
    global_config_file: Path | None
    profile_name: str | None
    values: dict[str, ResolvedValue]
    warnings: tuple[str, ...] = ()
    defined_profiles: tuple[str, ...] = Field(
        default=(),
        description="Every profile name any config file declares. What the refusal reports.",
    )

    def get(self, field: str) -> Any:
        entry = self.values.get(field)
        return entry.value if entry else None

    @property
    def settings(self) -> Settings:
        """The scalar settings, validated."""
        return Settings(**{f: self.get(f) for f in SCALAR_FIELDS if self.get(f) is not None})

    @property
    def profile(self) -> BackendProfile:
        """The selected profile, with every layer applied on top of it."""
        if self.profile_name is None:
            raise ConfigError(self._unselected())
        backend = self.get("backend")
        if backend is None:
            raise ConfigError(
                f"profile {self.profile_name!r} does not exist or declares no `backend`. "
                f"Define it in {PROJECT_DIR}/{CONFIG_FILENAME} under "
                f"[profiles.{self.profile_name}]."
            )
        return BackendProfile(
            name=self.profile_name,
            backend=backend,
            host=self.get("host"),
            port=self.get("port") or PROFILE_DEFAULTS["port"],
            password=self.get("password"),
            allow_local=bool(self.get("allow_local")),
            scale=self.get("scale"),
        )

    def _unselected(self) -> str:
        """Why no profile was selected, as **one** instruction.

        A menu of three alternatives is a question, and the caller here is usually an agent,
        which answers a question about a profile by inventing a name. So the message branches on
        what is actually true and names the single next move.
        """
        found: Path | None = self.config_file or self.global_config_file
        if not self.defined_profiles:
            if found is None:
                return "no configuration found; run `use-computer config init`"
            return (
                f"{found} defines no profiles; add a [profiles.<name>] section declaring a "
                "`backend`"
            )
        names = ", ".join(self.defined_profiles)
        where = found if found is not None else f"{PROJECT_DIR}/{CONFIG_FILENAME}"
        return (
            f"several profiles are defined ({names}) and none is the default; "
            f"set `default-profile` in {where}"
        )

    def show(self) -> dict[str, Any]:
        """The `config show` payload: every value, its layer, its variable, secrets masked."""
        return {
            "project-root": str(self.project_root) if self.project_root else None,
            "config-file": str(self.config_file) if self.config_file else None,
            "global-config-file": str(self.global_config_file) if self.global_config_file else None,
            "profile": self.profile_name,
            "layers": list(LAYERS),
            "values": {
                name: {
                    "value": entry.display(),
                    "layer": entry.layer,
                    "env": entry.env,
                    "source": entry.source,
                }
                for name, entry in sorted(self.values.items())
            },
        }


# --- Locations ---------------------------------------------------------------------------------


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from ``start`` looking for a ``.use-computer`` directory, the way git does."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / PROJECT_DIR).is_dir():
            return candidate
    return None


def xdg_config_dir() -> Path:
    """The XDG config directory. Configuration is not disposable, so never a cache directory."""
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "use-computer"


def xdg_data_dir() -> Path:
    """The XDG data directory, for anything stored."""
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "use-computer"


#: Files the tool writes into its own directory that must not be committed. It has always been
#: documented that `.env` is gitignored and nothing ever made it so.
GITIGNORE_LINES = ("# written by use-computer", ".env", "screens/")

SCREENS_DIR = "screens"


def default_screenshot_dir() -> Path:
    """Where screenshots land when nothing said otherwise.

    Beside the work that produced them when there is a project -- easy to open, easy to throw
    away, and separate from another project's. Under `.use-computer/` rather than a second hidden
    directory at the root, because the tool already owns that one.

    Without a project, the XDG *data* directory: a screenshot of somebody's desktop is not
    disposable like a cache.
    """
    root = find_project_root()
    if root is not None:
        return root / PROJECT_DIR / SCREENS_DIR
    return xdg_data_dir() / "screenshots"


def ensure_gitignore(project_dir: Path) -> None:
    """Keep the tool's own directory out of a commit.

    A screenshot here is the whole desktop -- open conversations, mail, whatever is on it -- and in
    a working tree one ``git add -A`` commits it. That objection is the reason the docs used to
    forbid this outright, so the answer travels with the change rather than being left as a note.

    Only ever this directory. Editing the project's own `.gitignore` is the user's business, not a
    side effect of taking a picture.
    """
    path = project_dir / ".gitignore"
    if path.exists():
        return
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(GITIGNORE_LINES) + "\n", encoding="utf-8")
    except OSError:
        # Not being able to write it must never stop a screenshot being taken.
        return


def env_var_for(field: str) -> str:
    return ENV_PREFIX + field.upper()


# --- Reading -----------------------------------------------------------------------------------


def _normalise(mapping: dict[str, Any]) -> dict[str, Any]:
    """Config files are written in kebab-case; fields are snake_case."""
    return {key.replace("-", "_"): value for key, value in mapping.items()}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            loaded: dict[str, Any] = tomllib.load(handle)
            return loaded
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc


def _check_unknown(raw: dict[str, Any], path: Path, warnings: list[str]) -> None:
    """Warn about unknown keys -- including keys inside profiles that are not selected.

    A typo in an unused profile is exactly the kind of thing discovered at the worst moment.
    """
    for key in raw:
        if key.replace("-", "_") not in TOP_LEVEL_KEYS:
            warnings.append(f"{path}: unknown key {key!r}")
    profiles = raw.get("profiles") or {}
    if not isinstance(profiles, dict):
        warnings.append(f"{path}: `profiles` must be a table")
        return
    for profile_name, profile in profiles.items():
        if not isinstance(profile, dict):
            warnings.append(f"{path}: profile {profile_name!r} must be a table")
            continue
        for key in profile:
            if key.replace("-", "_") not in PROFILE_KEYS:
                warnings.append(f"{path}: unknown key {key!r} in profile {profile_name!r}")


def _env_layer(environ: dict[str, str]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Split ``USE_COMPUTER_*`` into scalar overrides and per-profile overrides.

    ``USE_COMPUTER_PROFILES__STAGING__PASSWORD`` targets one profile; everything else is a
    scalar override.
    """
    scalars: dict[str, Any] = {}
    profiles: dict[str, dict[str, Any]] = {}
    for raw_key, raw_value in environ.items():
        if not raw_key.startswith(ENV_PREFIX):
            continue
        name = raw_key[len(ENV_PREFIX) :].lower()
        if name.startswith("profiles__"):
            parts = name.split("__")
            if len(parts) == 3:
                profiles.setdefault(parts[1], {})[parts[2]] = raw_value
            continue
        scalars[name] = raw_value
    return scalars, profiles


def _declared_profiles(
    layers: tuple[tuple[dict[str, Any], Layer, Path | None], ...],
) -> dict[str, tuple[Layer, Path | None]]:
    """Every profile name a config file declares, with the layer that declared it.

    Lowest precedence first, so a name the project file also declares overwrites the global
    one -- the same order the values themselves follow. A profile mentioned only by an
    environment override is not declared: it has no `backend` and could not be opened.
    """
    declared: dict[str, tuple[Layer, Path | None]] = {}
    for raw, layer, source in layers:
        for name, entry in (raw.get("profiles") or {}).items():
            if isinstance(entry, dict):
                declared[name] = (layer, source)
    return declared


# --- Resolution --------------------------------------------------------------------------------


def load(
    cli: dict[str, Any] | None = None,
    *,
    profile: str | None = None,
    start: Path | None = None,
    environ: dict[str, str] | None = None,
) -> ResolvedConfig:
    """Resolve configuration across every layer.

    Precedence, highest to lowest: CLI flags, environment variables, .env files, the selected
    profile, top-level config keys, the global config, field defaults.
    """
    cli_values = {key: value for key, value in (cli or {}).items() if value is not None}
    environ = dict(os.environ if environ is None else environ)
    warnings: list[str] = []

    root = find_project_root(start)
    config_file = root / PROJECT_DIR / CONFIG_FILENAME if root else None
    if config_file is not None and not config_file.is_file():
        config_file = None
    global_file: Path | None = xdg_config_dir() / CONFIG_FILENAME
    if global_file is not None and not global_file.is_file():
        global_file = None

    project_raw = _read_toml(config_file) if config_file else {}
    global_raw = _read_toml(global_file) if global_file else {}
    if config_file:
        _check_unknown(project_raw, config_file, warnings)
    if global_file:
        _check_unknown(global_raw, global_file, warnings)

    dotenv_raw: dict[str, Any] = {}
    dotenv_profiles: dict[str, dict[str, Any]] = {}
    dotenv_file = root / PROJECT_DIR / ENV_FILENAME if root else None
    if dotenv_file is not None and dotenv_file.is_file():
        present = {k: v for k, v in dotenv_values(dotenv_file).items() if v is not None}
        dotenv_raw, dotenv_profiles = _env_layer(present)
    else:
        dotenv_file = None

    env_raw, env_profiles = _env_layer(environ)

    declared = _declared_profiles(
        ((global_raw, "global-config", global_file), (project_raw, "config", config_file))
    )

    # Pass one: the profile name itself, resolved without a profile layer. Where it came from
    # is tracked here rather than reconstructed later, so `config show` reports what actually
    # chose it.
    selected: str | None = None
    selected_layer: Layer = "cli"
    selected_source: Path | None = None

    explicit = profile or cli_values.get("profile")
    if explicit:
        selected = str(explicit)
    else:
        candidates: tuple[tuple[Any, Layer, Path | None], ...] = (
            (env_raw.get("default_profile"), "env", None),
            (dotenv_raw.get("default_profile"), "dotenv", dotenv_file),
            (_normalise(project_raw).get("default_profile"), "config", config_file),
            (_normalise(global_raw).get("default_profile"), "global-config", global_file),
        )
        for candidate, layer, source in candidates:
            if candidate:
                selected, selected_layer, selected_source = str(candidate), layer, source
                break

    # A single declared profile is the profile. Nothing distinguishes one profile from another
    # in any result the caller can read, so a choice with one option is not a choice -- and the
    # caller most likely to be stopped by it is an agent, which cannot make it at all.
    if selected is None and len(declared) == 1:
        selected, (selected_layer, selected_source) = next(iter(declared.items()))

    # Pass two: every field, over the full stack.
    profile_raw: dict[str, Any] = {}
    profile_source: Path | None = None
    if selected:
        for raw, source in ((project_raw, config_file), (global_raw, global_file)):
            entry = (raw.get("profiles") or {}).get(selected)
            if isinstance(entry, dict):
                profile_raw = _normalise(entry)
                profile_source = source
                break
        else:
            warnings.append(f"profile {selected!r} is not defined in any config file")
        for overrides in (dotenv_profiles.get(selected), env_profiles.get(selected)):
            if overrides:
                profile_raw = {**profile_raw, **overrides}

    stack: list[tuple[Layer, dict[str, Any], Path | None]] = [
        ("cli", {k: v for k, v in cli_values.items() if k != "profile"}, None),
        ("env", env_raw, None),
        ("dotenv", dotenv_raw, dotenv_file),
        ("profile", profile_raw, profile_source),
        (
            "config",
            _normalise({k: v for k, v in project_raw.items() if k != "profiles"}),
            config_file,
        ),
        (
            "global-config",
            _normalise({k: v for k, v in global_raw.items() if k != "profiles"}),
            global_file,
        ),
    ]

    fields = (*SCALAR_FIELDS, "backend", "host", "port", "scale", "password")
    defaults = Settings()
    values: dict[str, ResolvedValue] = {}
    for field in fields:
        for layer, mapping, source in stack:
            if field in mapping:
                values[field] = ResolvedValue(
                    value=_coerce(field, mapping[field]),
                    layer=layer,
                    env=env_var_for(field),
                    source=str(source) if source else None,
                    secret=field in SECRET_FIELDS,
                )
                break
        else:
            values[field] = ResolvedValue(
                value=getattr(defaults, field, PROFILE_DEFAULTS.get(field)),
                layer="default",
                env=env_var_for(field),
                secret=field in SECRET_FIELDS,
            )
    if selected:
        values["default_profile"] = values["default_profile"].model_copy(
            update={
                "value": selected,
                "layer": selected_layer,
                "source": str(selected_source) if selected_source else None,
            }
        )

    return ResolvedConfig(
        project_root=root,
        config_file=config_file,
        global_config_file=global_file,
        profile_name=selected,
        values=values,
        warnings=tuple(warnings),
        defined_profiles=tuple(sorted(declared)),
    )


# --- Writing ---------------------------------------------------------------------------------


def _toml_string(value: str) -> str:
    """TOML basic string. Values here are hosts and profile names, but never assume."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def _toml_key(value: str) -> str:
    """A TOML key. Bare when it can be, quoted when it must be.

    The table header is a key, not a value: interpolating a name with a quote or a dot into
    `[profiles.<name>]` produces a file the loader then refuses to read.
    """
    return value if _BARE_KEY.match(value) else _toml_string(value)


def render_config(
    profile: str,
    backend: str,
    *,
    host: str | None = None,
    port: int = 5900,
    allow_local: bool = False,
) -> str:
    """The config file a guided setup writes.

    Commented, because the file is the thing the user edits next.
    """
    lines = [
        "# Written by `use-computer config init`. Edit it freely.",
        "#",
        "# This file is discovered by walking up from the current directory, the way git finds",
        "# its own, and is meant to be committed. Secrets belong in .use-computer/.env, which",
        "# is not. `use-computer config show` prints every resolved value and where it came from.",
        "",
        f"default-profile = {_toml_string(profile)}",
        "",
        "# Seconds to wait after each action, so the application can react.",
        "delay = 0.1",
        "",
        f"[profiles.{_toml_key(profile)}]",
        f"backend = {_toml_string(backend)}",
    ]
    if backend == "vnc":
        lines += [
            f"host = {_toml_string(host or '')}",
            f"port = {port}",
            "# The password belongs in .use-computer/.env, not here:",
            f"#   {profile_env_var(profile, 'password')}=...",
        ]
    if backend == "local":
        lines += [
            "# The local backend moves THIS machine's pointer and types on THIS machine's",
            "# keyboard. That is why it is off by default; this line is the explicit opt-in.",
            f"allow-local = {str(bool(allow_local)).lower()}",
        ]
    return "\n".join(lines) + "\n"


def profile_env_var(profile: str, field: str) -> str:
    """The variable that overrides one field of one profile."""
    return f"{ENV_PREFIX}PROFILES__{profile.upper()}__{field.upper()}"


def write_initial_config(
    root: Path,
    profile: str,
    backend: str,
    *,
    host: str | None = None,
    port: int = 5900,
    allow_local: bool = False,
    password: str | None = None,
    force: bool = False,
) -> tuple[Path, Path | None]:
    """Create ``.use-computer/config.toml`` under ``root``, and a ``.env`` if given a password.

    Returns the config path and the .env path, the latter ``None`` when no password was given.

    Raises:
        ConfigError: when a config is already there and ``force`` was not given.
    """
    directory = root / PROJECT_DIR
    config_path = directory / CONFIG_FILENAME
    if config_path.exists() and not force:
        raise ConfigError(
            f"{config_path} already exists. Edit it, or pass --force to replace it. "
            "`config init` creates a config; it does not merge into one."
        )
    directory.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        render_config(profile, backend, host=host, port=port, allow_local=allow_local),
        encoding="utf-8",
    )

    env_path: Path | None = None
    if password:
        env_path = directory / ENV_FILENAME
        line = f"{profile_env_var(profile, 'password')}={password}\n"
        existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
        if existing and not existing.endswith("\n"):
            existing += "\n"
        env_path.write_text(existing + line, encoding="utf-8")
        # The file holds a secret from the moment it is written.
        env_path.chmod(0o600)
    return config_path, env_path


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
_BOOL_FIELDS = frozenset({"verify", "dry_run", "allow_local", "continue_on_error"})
_PATH_FIELDS = frozenset({"screenshot_dir"})
_FLOAT_FIELDS = frozenset({"delay", "typing_rate", "verify_threshold", "scale"})


def _coerce(field: str, value: Any) -> Any:
    """Environment variables and .env files arrive as strings; TOML arrives already typed."""
    if not isinstance(value, str):
        return value
    lowered = value.strip().lower()
    if field in _BOOL_FIELDS:
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ConfigError(f"{env_var_for(field)}={value!r} is not a boolean")
    if field in _FLOAT_FIELDS:
        try:
            return float(value)
        except ValueError as exc:
            raise ConfigError(f"{env_var_for(field)}={value!r} is not a number") from exc
    if field in _PATH_FIELDS:
        return Path(value).expanduser()
    if field == "port":
        try:
            return int(value)
        except ValueError as exc:
            raise ConfigError(f"{env_var_for(field)}={value!r} is not an integer") from exc
    return value
