"""Finding the documents under a root and describing them for the listing page."""

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from .paths import DOC_SUFFIXES

SKIP_DIRS = {
    "_site",
    "node_modules",
    "venv",
    "__pycache__",
    "dist",
    "build",
}
RECENT = 5
WORDS_PER_MINUTE = 200


@dataclass(frozen=True)
class Description:
    title: str
    summary: str
    minutes: int


@dataclass(frozen=True)
class Entry:
    href: str
    path: str
    name: str
    title: str
    summary: str
    minutes: int
    mtime: float
    modified: str


@dataclass
class Group:
    """The documents directly inside one directory."""

    name: str
    href: str
    notebooks: list[Entry] = field(default_factory=list)
    pages: list[Entry] = field(default_factory=list)


@dataclass
class Listing:
    groups: list[Group]
    recent: list[Entry]


def discover(top: Path) -> list[Path]:
    """Notebooks and markdown files under `top`, skipping hidden and build directories."""
    found: list[Path] = []

    def walk(directory: str) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name.lower())
        except OSError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            # Symlinked directories are not followed: they may loop or leave the root.
            if entry.is_dir(follow_symlinks=False):
                if entry.name not in SKIP_DIRS:
                    walk(entry.path)
            elif entry.is_file() and Path(entry.name).suffix.lower() in DOC_SUFFIXES:
                found.append(Path(entry.path))

    walk(str(top))
    return found


def _plain(text: str) -> str:
    """Markdown inline syntax removed, for showing a summary as plain text."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*\*|__|`", "", text)
    return re.sub(r"(?<!\w)[*_](\S(?:[^*_]*\S)?)[*_](?!\w)", r"\1", text)


def _heading_and_paragraph(lines: list[str]) -> tuple[str, str] | None:
    heading = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    if heading is None:
        return None
    paragraph: list[str] = []
    for line in lines[heading + 1 :]:
        line = line.strip()
        if not line:
            if paragraph:
                break
            continue
        if line.startswith("#"):
            break
        paragraph.append(line)
    return _plain(lines[heading][2:].strip()), _plain(" ".join(paragraph))


def _source(cell: dict) -> str:
    source = cell.get("source", "")
    return source if isinstance(source, str) else "".join(source)


def _describe(path: Path) -> Description:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return Description(path.stem, "", 1)
    if path.suffix.lower() == ".md":
        found = _heading_and_paragraph(text.splitlines())
        title, summary = found or (path.stem, "")
        words = len(text.split())
    else:
        try:
            cells = json.loads(text).get("cells", [])
        except (json.JSONDecodeError, AttributeError):
            return Description(path.stem, "", 1)
        title, summary, words = path.stem, "", 0
        described = False
        for cell in cells:
            source = _source(cell)
            words += len(source.split())
            if not described and cell.get("cell_type") == "markdown":
                if found := _heading_and_paragraph(source.splitlines()):
                    title, summary = found
                    described = True
    return Description(title, summary, max(1, round(words / WORDS_PER_MINUTE)))


_descriptions: dict[Path, tuple[tuple[int, int], Description]] = {}


def describe(path: Path) -> Description:
    """Title from the first `# ` heading, summary from the paragraph under it."""
    stat = path.stat()
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _descriptions.get(path)
    if cached and cached[0] == stamp:
        return cached[1]
    description = _describe(path)
    _descriptions[path] = (stamp, description)
    return description


def _modified(mtime: float) -> str:
    when = datetime.fromtimestamp(mtime)
    return f"{when.day} {when:%b %Y}"


def _source_href(rel: PurePosixPath) -> str:
    return quote(str(rel))


def listing(
    top: Path,
    paths: list[Path] | None = None,
    href: Callable[[PurePosixPath], str] = _source_href,
) -> Listing:
    """Everything readable under `top`, grouped by directory, with links relative to it.

    A static build passes the documents it chose and where each one's page is.
    """
    groups: dict[tuple[str, ...], Group] = {}
    entries: list[Entry] = []
    for path in discover(top) if paths is None else paths:
        rel = path.relative_to(top)
        try:
            description = describe(path)
            mtime = path.stat().st_mtime
        except OSError:  # deleted between the walk and the read
            continue
        entry = Entry(
            href=href(PurePosixPath(rel.as_posix())),
            path=rel.as_posix(),
            name=rel.name,
            title=description.title,
            summary=description.summary,
            minutes=description.minutes,
            mtime=mtime,
            modified=_modified(mtime),
        )
        entries.append(entry)
        parts = rel.parent.parts
        group = groups.get(parts)
        if group is None:
            name = "/".join(parts)
            group = groups[parts] = Group(name, quote(name) + "/" if name else "")
        (group.notebooks if path.suffix.lower() == ".ipynb" else group.pages).append(entry)

    ordered = [groups[parts] for parts in sorted(groups, key=lambda p: [s.lower() for s in p])]
    for group in ordered:
        # A folder's README introduces it, so it leads the folder's pages.
        group.pages.sort(key=lambda e: not e.name.lower().startswith("readme."))
    recent = sorted(entries, key=lambda e: e.mtime, reverse=True)[:RECENT]
    # In a small folder the strip would only repeat most of what is below it.
    return Listing(ordered, recent if len(entries) > 2 * RECENT else [])


def count(root: Path) -> tuple[int, int]:
    """How many notebooks and markdown files the root holds, for the launch summary."""
    found = discover(root)
    notebooks = sum(1 for p in found if p.suffix.lower() == ".ipynb")
    return notebooks, len(found) - notebooks
