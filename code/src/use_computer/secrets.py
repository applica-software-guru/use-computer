"""The secret store: a value the agent types and never reads.

One invariant holds this module together -- *a secret leaves the store into the keyboard, and never
into stdout*. So there is no function here that returns every value at once, nothing renders a
value, and the only way out is :func:`resolve`, called by the action that is about to send it.

The value is a ``SecretStr`` from the moment it is parsed, which masks it in a ``repr``, a log line
and a traceback. That is defence in depth rather than the mechanism: the mechanism is that actions
carry the *name*, so nothing that serialises an action can leak anything.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, SecretStr

from use_computer.config import PROJECT_DIR, find_project_root, xdg_config_dir
from use_computer.errors import SecretNotFoundError, UseComputerError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 only
    import tomli as tomllib

STORE_FILENAME = "secrets.toml"

#: Supplies one secret from the environment, for a machine with nobody sitting at it to answer a
#: prompt. Dashes in the name become underscores.
ENV_SECRET_PREFIX = "USE_COMPUTER_SECRET_"

Store = Literal["global", "project", "env"]

#: A name goes into a TOML key and into an environment variable, so it is constrained to what is
#: unambiguous in both. This is a boundary, not a style rule: a name carrying a quote or a newline
#: would write a store file that the reader then refuses.
_VALID_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class SecretNameError(UseComputerError):
    """A secret name is not usable as a key."""


class SecretEntry(BaseModel):
    """One secret, without its value. What ``secret list`` is allowed to know."""

    model_config = ConfigDict(frozen=True)

    name: str
    store: Store
    set_at: datetime | None = None


def check_name(name: str) -> str:
    if not _VALID_NAME.match(name):
        raise SecretNameError(
            f"{name!r} is not a usable secret name; use letters, digits, dashes and "
            "underscores, starting with a letter or a digit"
        )
    return name


def env_var_for(name: str) -> str:
    return ENV_SECRET_PREFIX + name.replace("-", "_").upper()


# --- the file ----------------------------------------------------------------------------------


class FileStore:
    """A ``secrets.toml``, read one name at a time."""

    def __init__(self, path: Path, kind: Literal["global", "project"]) -> None:
        self.path = path
        self.kind = kind

    def _read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            with self.path.open("rb") as handle:
                loaded: dict[str, Any] = tomllib.load(handle)
        except OSError as exc:
            raise UseComputerError(f"cannot read {self.path}: {exc}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise UseComputerError(f"{self.path} is not valid TOML: {exc}") from exc
        section = loaded.get("secrets")
        return section if isinstance(section, dict) else {}

    def get(self, name: str) -> SecretStr | None:
        entry = self._read().get(name)
        if not isinstance(entry, dict):
            return None
        value = entry.get("value")
        return SecretStr(value) if isinstance(value, str) else None

    def entries(self) -> list[SecretEntry]:
        found = []
        for name, entry in sorted(self._read().items()):
            if not isinstance(entry, dict):
                continue
            raw = entry.get("set-at")
            found.append(
                SecretEntry(name=name, store=self.kind, set_at=_parse_time(raw))
            )
        return found

    def put(self, name: str, value: str) -> None:
        """Store a value, replacing one of the same name.

        Rotating a credential must not require a second command, or it gets done by editing the
        file -- which is how a secret ends up in an editor's undo history.
        """
        check_name(name)
        secrets = self._read()
        secrets[name] = {
            "value": value,
            "set-at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._write(secrets)

    def remove(self, name: str) -> bool:
        secrets = self._read()
        if name not in secrets:
            return False
        del secrets[name]
        self._write(secrets)
        return True

    def _write(self, secrets: dict[str, Any]) -> None:
        lines = [
            "# Written by `use-computer secret set`. Values here are not encrypted;",
            "# the file is mode 0600 and must not be committed.",
        ]
        for name, entry in sorted(secrets.items()):
            lines += [
                "",
                f"[secrets.{_toml_key(name)}]",
                f"value = {_toml_string(str(entry.get('value', '')))}",
                f"set-at = {_toml_string(str(entry.get('set-at', '')))}",
            ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 0600 **at creation**: chmod afterwards leaves a window in which the file is readable,
        # and the thing readable in that window is the credential.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        # An existing file keeps whatever mode it had, so narrow it too.
        os.chmod(self.path, 0o600)


def _parse_time(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _toml_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _toml_key(value: str) -> str:
    return value if _VALID_NAME.match(value) else _toml_string(value)


# --- the two stores ----------------------------------------------------------------------------


def global_store() -> FileStore:
    """The default. A credential is a fact about the person at the machine, not the repository."""
    return FileStore(xdg_config_dir() / STORE_FILENAME, "global")


def project_store(start: Path | None = None) -> FileStore | None:
    """The project store, when there is a project to hold it."""
    root = find_project_root(start)
    if root is None:
        return None
    return FileStore(root / PROJECT_DIR / STORE_FILENAME, "project")


def store_for(project: bool, start: Path | None = None) -> FileStore:
    """The store a write targets.

    Raises:
        UseComputerError: when ``--project`` was asked for outside a project.
    """
    if not project:
        return global_store()
    found = project_store(start)
    if found is None:
        raise UseComputerError(
            "no project here to store a secret in; run `use-computer config init`, "
            "or drop --project to use the global store"
        )
    return found


class Secrets:
    """Resolution across the environment and the two stores."""

    def __init__(
        self, *, start: Path | None = None, environ: dict[str, str] | None = None
    ) -> None:
        self._environ = dict(os.environ if environ is None else environ)
        self._project = project_store(start)
        self._global = global_store()

    def get(self, name: str) -> SecretStr | None:
        """The value, looked up environment first, then project, then global."""
        from_env = self._environ.get(env_var_for(name))
        if from_env is not None:
            return SecretStr(from_env)
        for store in (self._project, self._global):
            if store is None:
                continue
            found = store.get(name)
            if found is not None:
                return found
        return None

    def require(self, name: str) -> SecretStr:
        """The value, or the refusal that tells the agent to stop rather than improvise.

        Raises:
            SecretNotFoundError: when no store has it.
        """
        found = self.get(name)
        if found is None:
            raise SecretNotFoundError(name)
        return found

    def entries(self) -> list[SecretEntry]:
        """Every name, with the store it came from. Never a value.

        A name present in both stores is reported once, as the project one -- which is the one
        ``resolve`` would use, and reporting the shadowed copy would be reporting a value that
        nothing will ever type.
        """
        seen: dict[str, SecretEntry] = {}
        for store in (self._global, self._project):
            if store is None:
                continue
            for entry in store.entries():
                seen[entry.name] = entry
        for key in self._environ:
            if not key.startswith(ENV_SECRET_PREFIX):
                continue
            name = key[len(ENV_SECRET_PREFIX) :].lower().replace("_", "-")
            seen[name] = SecretEntry(name=name, store="env")
        return sorted(seen.values(), key=lambda entry: entry.name)
