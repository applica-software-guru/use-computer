"""Removing screenshots: only the ones this tool wrote, and never the directory."""

from __future__ import annotations

from pathlib import Path

from use_computer.config import GITIGNORE_LINES, ensure_gitignore
from use_computer.prune import ours, prune


def shot(directory: Path, stamp: str, label: str = "click") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stamp}-{label}.png"
    path.write_bytes(b"x" * 10)
    return path


def test_it_recognises_only_the_names_it_writes() -> None:
    assert ours(Path("20260905T094734.680Z-click.png"))
    assert ours(Path("20260905T094734.680Z-screenshot.png"))
    assert not ours(Path("holiday.png"))
    assert not ours(Path("screenshot.png"))
    assert not ours(Path("20260905-click.png"))


def test_a_file_it_did_not_write_is_counted_and_left(tmp_path: Path) -> None:
    # `screenshot-dir` is configurable, and the first person to point it at their Pictures folder
    # must not lose anything. This tool refuses to guess everywhere else.
    shot(tmp_path, "20260905T094734.680Z")
    stranger = tmp_path / "holiday.png"
    stranger.write_bytes(b"mine")

    result = prune(tmp_path)
    assert len(result.removed) == 1
    assert result.skipped == 1
    assert stranger.exists()
    assert "left 1 file this tool did not write" in result.describe()


def test_dry_run_removes_nothing_and_says_so(tmp_path: Path) -> None:
    kept = shot(tmp_path, "20260905T094734.680Z")
    result = prune(tmp_path, dry_run=True)
    assert kept.exists()
    assert result.performed is False
    assert result.describe().startswith("would remove 1 screenshot ")


def test_keep_leaves_the_most_recent_by_name(tmp_path: Path) -> None:
    # The name is the record -- which is why it was made to sort -- not the filesystem's mtime.
    old = shot(tmp_path, "20260905T090000.000Z")
    new = shot(tmp_path, "20260905T100000.000Z")
    prune(tmp_path, keep=1)
    assert new.exists()
    assert not old.exists()


def test_the_directory_itself_survives(tmp_path: Path) -> None:
    shot(tmp_path, "20260905T094734.680Z")
    prune(tmp_path)
    assert tmp_path.exists()


def test_a_missing_directory_is_not_an_error(tmp_path: Path) -> None:
    result = prune(tmp_path / "nowhere")
    assert result.removed == ()
    assert "does not exist" in result.describe()


def test_the_gitignore_is_written_once_and_never_overwritten(tmp_path: Path) -> None:
    project = tmp_path / ".use-computer"
    ensure_gitignore(project)
    assert (project / ".gitignore").read_text().splitlines() == list(GITIGNORE_LINES)

    (project / ".gitignore").write_text("mine\n")
    ensure_gitignore(project)
    assert (project / ".gitignore").read_text() == "mine\n"  # somebody else's, left alone
