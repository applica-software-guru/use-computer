"""The agent skill, and the commands that install it.

The skill ships as package data *inside* the package. A copy at the repository root would not
be in the wheel, and a skill that is not in the wheel does not exist for anyone who installed
from PyPI.

Nothing here ever writes to or deletes a directory that does not carry this skill's frontmatter
marker: removing a directory someone else owns is unrecoverable, and the marker is the proof of
ownership.
"""

from __future__ import annotations

from enum import Enum
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from use_computer.errors import ConfigError

#: Frontmatter key/value that marks a directory as owned by this skill.
MARKER_KEY = "x-skill-id"
MARKER_VALUE = "use-computer"

#: Directory name the skill is installed under.
SKILL_NAME = "use-computer"
SKILL_FILE = "SKILL.md"

#: The neutral layout, used when a project shows no preference.
NEUTRAL_DIR = Path(".agents") / "skills"
CLAUDE_DIR = Path(".claude") / "skills"


class Scope(str, Enum):
    USER = "user"
    PROJECT = "project"
    AGENTS = "agents"
    CLAUDE = "claude"


class SkillState(BaseModel):
    """Where the skill is, and whether it matches the bundled copy."""

    model_config = ConfigDict(frozen=True)

    scope: Scope
    path: Path
    installed: bool
    owned: bool
    up_to_date: bool

    @property
    def status(self) -> str:
        if not self.installed:
            return "missing"
        if not self.owned:
            return "foreign"
        return "up-to-date" if self.up_to_date else "outdated"


def bundled_text() -> str:
    """The bundled SKILL.md, read as package data -- the package may be zipped."""
    return resources.files(__package__).joinpath(SKILL_FILE).read_text(encoding="utf-8")


def skills_dir(scope: Scope, *, root: Path | None = None, override: Path | None = None) -> Path:
    """The skills directory for a scope.

    The ``project`` scope follows the layout the target project already uses, and defaults to
    the neutral ``.agents/skills`` when neither exists.
    """
    if override is not None:
        return override
    base = root or Path.cwd()
    if scope is Scope.CLAUDE:
        return base / CLAUDE_DIR
    if scope is Scope.AGENTS:
        return base / NEUTRAL_DIR
    if scope is Scope.PROJECT:
        if (base / CLAUDE_DIR).is_dir():
            return base / CLAUDE_DIR
        if (base / NEUTRAL_DIR).is_dir():
            return base / NEUTRAL_DIR
        return base / NEUTRAL_DIR
    home = Path.home()
    if (home / CLAUDE_DIR).is_dir():
        return home / CLAUDE_DIR
    return home / NEUTRAL_DIR


def target_path(scope: Scope, *, root: Path | None = None, override: Path | None = None) -> Path:
    return skills_dir(scope, root=root, override=override) / SKILL_NAME / SKILL_FILE


def carries_marker(path: Path) -> bool:
    """Whether a SKILL.md declares this skill's frontmatter marker."""
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return _marker_in_frontmatter(text)


def _marker_in_frontmatter(text: str) -> bool:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            return False
        key, _, value = line.partition(":")
        if key.strip() == MARKER_KEY and value.strip().strip("\"'") == MARKER_VALUE:
            return True
    return False


def status(scope: Scope, *, root: Path | None = None, override: Path | None = None) -> SkillState:
    path = target_path(scope, root=root, override=override)
    installed = path.is_file()
    owned = carries_marker(path)
    up_to_date = False
    if installed and owned:
        up_to_date = path.read_text(encoding="utf-8") == bundled_text()
    return SkillState(
        scope=scope, path=path, installed=installed, owned=owned, up_to_date=up_to_date
    )


def install(
    scope: Scope,
    *,
    root: Path | None = None,
    override: Path | None = None,
    force: bool = False,
) -> SkillState:
    """Write the bundled skill into the scope's skills directory.

    Raises:
        ConfigError: when a file is already there and ``force`` was not given, or when the
            existing file belongs to another skill.
    """
    path = target_path(scope, root=root, override=override)
    if path.exists():
        if not carries_marker(path):
            raise ConfigError(
                f"{path} exists and does not carry the {MARKER_KEY}: {MARKER_VALUE} marker, so "
                "it belongs to something else. Refusing to touch it."
            )
        if not force:
            raise ConfigError(f"{path} already exists. Pass --force to overwrite it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bundled_text(), encoding="utf-8")
    return status(scope, root=root, override=override)


def update(
    scope: Scope, *, root: Path | None = None, override: Path | None = None
) -> SkillState:
    """Refresh an installed skill. Installing over our own copy is what update means."""
    path = target_path(scope, root=root, override=override)
    if path.exists() and not carries_marker(path):
        raise ConfigError(
            f"{path} does not carry the {MARKER_KEY}: {MARKER_VALUE} marker. Refusing to touch it."
        )
    return install(scope, root=root, override=override, force=True)


def remove(scope: Scope, *, root: Path | None = None, override: Path | None = None) -> SkillState:
    """Delete an installed skill, and only ever one that carries the marker."""
    path = target_path(scope, root=root, override=override)
    if not path.exists():
        return status(scope, root=root, override=override)
    if not carries_marker(path):
        raise ConfigError(
            f"{path} does not carry the {MARKER_KEY}: {MARKER_VALUE} marker, so it belongs to "
            "something else. Refusing to remove it."
        )
    path.unlink()
    parent = path.parent
    if parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
    return status(scope, root=root, override=override)
