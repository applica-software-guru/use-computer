"""Removing the screenshots this tool wrote.

CR-004 left it open -- "they are not pruned. The directory grows, and that is the user's to manage
for now" -- and with the pictures inside the project, for now has run out.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

#: Exactly the names :meth:`Session._screenshot_path` writes: a sortable UTC stamp, a label, .png.
#: A pattern rather than "every .png in there", because `screenshot-dir` is configurable and the
#: first person to point it at their Pictures folder must not lose anything. This tool refuses to
#: guess everywhere else; it will not guess about deleting.
OURS = re.compile(r"^\d{8}T\d{6}\.\d{3}Z-[a-z_]+\.png$")


class PruneResult(BaseModel):
    """What a prune did, or would do."""

    model_config = ConfigDict(frozen=True)

    directory: Path
    removed: tuple[Path, ...] = ()
    kept: int = 0
    skipped: int = 0
    bytes_freed: int = 0
    performed: bool = True

    def describe(self) -> str:
        if not self.directory.exists():
            return f"nothing to remove: {self.directory} does not exist"
        verb = "removed" if self.performed else "would remove"
        megabytes = self.bytes_freed / 1_000_000
        count = len(self.removed)
        parts = [
            f"{verb} {count} screenshot{'' if count == 1 else 's'} "
            f"({megabytes:.1f} MB) from {self.directory}"
        ]
        if self.kept:
            parts.append(f"kept {self.kept}")
        if self.skipped:
            # Said out loud: silence here would look like the files had been deleted.
            noun = "file" if self.skipped == 1 else "files"
            parts.append(f"left {self.skipped} {noun} this tool did not write")
        return ", ".join(parts)


def ours(path: Path) -> bool:
    return bool(OURS.match(path.name))


def prune(directory: Path, *, keep: int = 0, dry_run: bool = False) -> PruneResult:
    """Delete the screenshots in ``directory``, newest ``keep`` survive.

    Only files this tool wrote, and never the directory itself. Anything else in there belongs to
    somebody else and is counted, not touched.

    ``keep`` uses the timestamp in the name rather than the filesystem: the name is the record,
    which is why it was made to sort.
    """
    if not directory.exists():
        return PruneResult(directory=directory, performed=not dry_run)

    entries = sorted(directory.iterdir())
    mine = [path for path in entries if path.is_file() and ours(path)]
    skipped = len([path for path in entries if path.is_file() and not ours(path)])

    doomed = mine[: len(mine) - keep] if keep else mine
    freed = 0
    removed: list[Path] = []
    for path in doomed:
        size = path.stat().st_size
        if not dry_run:
            try:
                path.unlink()
            except OSError:
                continue
        removed.append(path)
        freed += size

    return PruneResult(
        directory=directory,
        removed=tuple(removed),
        kept=len(mine) - len(removed),
        skipped=skipped,
        bytes_freed=freed,
        performed=not dry_run,
    )


__all__ = ["PruneResult", "ours", "prune"]
