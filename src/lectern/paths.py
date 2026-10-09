"""Mapping a URL path onto a file under a served root, and nothing outside it."""

from collections.abc import Sequence
from fnmatch import fnmatchcase
from pathlib import Path

DOC_SUFFIXES = {".ipynb", ".md"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
ALLOWED = DOC_SUFFIXES | IMAGE_SUFFIXES
IGNORE_FILE = ".lecternignore"

_patterns: dict[Path, tuple[tuple[int, int], tuple[list[str], list[str]]]] = {}


def _ignore_patterns(root: Path) -> tuple[list[str], list[str]]:
    """The root's ignore list: names to leave out at any depth, and paths from the top.

    Read again whenever the file changes, so a running server follows an edit.
    """
    path = root / IGNORE_FILE
    try:
        stat = path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
        cached = _patterns.get(root)
        if cached and cached[0] == stamp:
            return cached[1]
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        _patterns.pop(root, None)
        return [], []
    names: list[str] = []
    anchored: list[str] = []
    for line in lines:
        pattern = line.strip().rstrip("/").lower()
        if not pattern or pattern.startswith("#"):
            continue
        if "/" in pattern:
            anchored.append(pattern.lstrip("/"))
        else:
            names.append(pattern)
    _patterns[root] = (stamp, (names, anchored))
    return names, anchored


def ignored(root: Path, parts: Sequence[str]) -> bool:
    """Whether the root's `.lecternignore` leaves out the path `parts` lead to.

    A pattern covers what it matches and everything under it. Letter case is not told
    apart: on a Mac `Private/x.md` opens `private/x.md`, which would walk around the list.
    """
    names, anchored = _ignore_patterns(root)
    if not names and not anchored:
        return False
    parts = [part.lower() for part in parts]
    if any(fnmatchcase(part, pattern) for part in parts for pattern in names):
        return True
    return any(
        fnmatchcase("/".join(parts[:depth]), pattern)
        for depth in range(1, len(parts) + 1)
        for pattern in anchored
    )


def resolve(root: Path, rel: str) -> Path | None:
    """The file or directory `rel` names under `root`, or None if it must not be served.

    `rel` is the already percent-decoded URL path below the root name. Dot-prefixed
    components cover both `..` and hidden files; resolving symlinks before the containment
    check stops a link inside the root from pointing out of it. What `.lecternignore`
    names is refused both as asked for and as the file a link leads to.
    """
    if "\x00" in rel or "\\" in rel:
        return None
    parts = [p for p in rel.split("/") if p]
    if any(p.startswith(".") for p in parts):
        return None
    top = root.resolve()
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(top):
        return None
    if ignored(root, parts) or ignored(root, target.relative_to(top).parts):
        return None
    if target.is_file() and target.suffix.lower() not in ALLOWED:
        return None
    return target
