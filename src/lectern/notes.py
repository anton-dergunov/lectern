"""Highlights and remarks on a document, kept in a file beside it.

analysis.ipynb  ->  analysis.notes.json

    {"version": 1, "notes": [{"id": …, "cell": "c-…", "start": 12, "quote": "the words",
      "prefix": "…", "suffix": "…", "note": "a remark", "created": …, "updated": …}]}

This is the one thing lectern writes on a device's say-so. What is written is never what
was sent: the notes are checked field by field and the file is composed here, at a path
worked out from the document's, so a request can neither name a file nor put anything in
one but notes.
"""

import hashlib
import json
import os
import re
import threading
from pathlib import Path

VERSION = 1
SUFFIX = ".notes.json"
MOST_NOTES = 2000
# The longest value of each text field, and the two that must be there.
TEXT = {
    "id": 64,
    "cell": 200,
    "quote": 2000,
    "prefix": 64,
    "suffix": 64,
    "note": 10000,
    "created": 40,
    "updated": 40,
}
_ID = re.compile(r"[A-Za-z0-9_-]+")

_lock = threading.Lock()


class NotesError(Exception):
    """Notes that cannot be kept as they were sent."""


class Stale(Exception):
    """The file has changed since the sender read it; `current` is what it holds now."""

    def __init__(self, current: dict) -> None:
        super().__init__("the notes have changed")
        self.current = current


def notes_path(doc: Path) -> Path:
    """Where a document's notes are kept: beside it, under its own name."""
    # A notebook and a markdown file of one name would otherwise share a file.
    if doc.suffix.lower() == ".md" and doc.with_suffix(".ipynb").exists():
        return doc.with_name(doc.name + SUFFIX)
    return doc.with_suffix(SUFFIX)


def _read(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {"rev": "", "notes": []}
    rev = hashlib.sha1(raw).hexdigest()[:16]
    try:
        notes = json.loads(raw)["notes"]
        if not isinstance(notes, list):
            raise TypeError("notes is not a list")
    except (ValueError, KeyError, TypeError) as error:
        # Edited by hand into something else. Not to be written over without a look.
        raise NotesError(f"{path.name} cannot be read: {error}") from error
    return {"rev": rev, "notes": [note for note in notes if isinstance(note, dict)]}


def load(doc: Path) -> dict:
    """`{"rev": …, "notes": […]}`; `rev` names this version of the file, "" for none."""
    return _read(notes_path(doc))


def _checked(notes: object) -> list[dict]:
    if not isinstance(notes, list):
        raise NotesError("notes must be a list")
    if len(notes) > MOST_NOTES:
        raise NotesError(f"more than {MOST_NOTES} notes")
    checked = []
    seen = set()
    for note in notes:
        if not isinstance(note, dict):
            raise NotesError("a note must be an object")
        unknown = set(note) - set(TEXT) - {"start"}
        if unknown:
            raise NotesError(f"unknown field {sorted(unknown)[0]!r}")
        clean = {}
        for name, longest in TEXT.items():
            value = note.get(name, "")
            if not isinstance(value, str) or len(value) > longest:
                raise NotesError(f"{name} must be text of at most {longest} characters")
            clean[name] = value
        start = note.get("start", 0)
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            raise NotesError("start must be a whole number")
        if not _ID.fullmatch(clean["id"]) or clean["id"] in seen:
            raise NotesError("each note needs an id of its own, of letters, digits, - and _")
        if not clean["quote"].strip():
            raise NotesError("a note needs the text it is about")
        seen.add(clean["id"])
        checked.append({"id": clean.pop("id"), "cell": clean.pop("cell"), "start": start, **clean})
    return checked


def save(doc: Path, notes: object, rev: str) -> dict:
    """Replace the document's notes, if `rev` is still the version on disk.

    Returns what `load` would now. Raises NotesError for notes that do not pass, and Stale
    when another device got there first.
    """
    checked = _checked(notes)
    path = notes_path(doc)
    with _lock:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise NotesError(f"{path.name} is not a plain file")
        current = _read(path)
        if rev != current["rev"]:
            raise Stale(current)
        if not checked:
            path.unlink(missing_ok=True)
            return {"rev": "", "notes": []}
        text = json.dumps({"version": VERSION, "notes": checked}, indent=2, ensure_ascii=False)
        # Whole or not at all: a reader, or git, never sees half a file.
        scratch = path.with_name(f".{path.name}.tmp")
        scratch.write_text(text + "\n", encoding="utf-8")
        os.replace(scratch, path)
        return _read(path)


# ---- As markdown, to read on the laptop ----

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


def _places(doc: Path) -> dict[str, tuple[int, str, str, str]]:
    """For each cell id as the page has it: its order, its label, the heading it is under
    and its source."""
    if doc.suffix.lower() != ".ipynb":
        return {"": (0, "", "", doc.read_text(encoding="utf-8"))}
    cells = json.loads(doc.read_text(encoding="utf-8")).get("cells", [])
    places = {}
    heading = ""
    code_cells = 0
    for index, cell in enumerate(cells):
        source = cell.get("source", "")
        source = source if isinstance(source, str) else "".join(source)
        label = ""
        if cell.get("cell_type") == "code":
            # The number the page shows beside the cell (render/notebook.py).
            code_cells += 1
            count = cell.get("execution_count")
            label = f"[{count}]" if count else f"#{code_cells}"
        places[f"c-{cell.get('id') or f'n{index}'}"] = (index, label, heading, source)
        if cell.get("cell_type") == "markdown":
            found = _HEADING.findall(source)
            if found:
                heading = found[-1][1]
    return places


def _heading_for(note: dict, under: str, source: str, is_prose: bool) -> str:
    """The heading a note's words are under: the last one above them in their own cell."""
    if not is_prose:
        return under
    # The words as written and as rendered differ by markup, so fewer and fewer of the
    # opening words are looked for until some are found.
    words = note.get("quote", "").split("\n")[0].split()[:6]
    at = -1
    while words and at < 0:
        at = source.find(" ".join(words))
        words.pop()
    above = [m for m in _HEADING.finditer(source) if at < 0 or m.start() <= at]
    if at < 0:
        above = above[:1]
    return above[-1].group(2) if above else under


def _quoted(text: str) -> str:
    return "\n".join(f"> {line}".rstrip() for line in text.split("\n"))


def to_markdown(doc: Path) -> str:
    """The document's notes in reading order, each under its heading and cell number."""
    notes = load(doc)["notes"]
    places = _places(doc)
    lines = [f"# Notes on {doc.name}", ""]
    if not notes:
        return "\n".join([*lines, "Nothing is marked.", ""])

    def entry(note: dict, label: str) -> list[str]:
        out = [f"Cell {label}:", ""] if label else []
        out += [_quoted(note.get("quote", "")), ""]
        if note.get("note"):
            out += [note["note"], ""]
        return out

    placed = [note for note in notes if note.get("cell", "") in places]
    placed.sort(key=lambda note: (places[note.get("cell", "")][0], note.get("start", 0)))
    current = None
    for note in placed:
        _, label, under, source = places[note.get("cell", "")]
        heading = _heading_for(note, under, source, is_prose=not label)
        if heading != current:
            current = heading
            if heading:
                lines += [f"## {heading}", ""]
        lines += entry(note, label)
    lost = [note for note in notes if note.get("cell", "") not in places]
    if lost:
        lines += ["## From cells that are no longer in the notebook", ""]
        for note in lost:
            lines += entry(note, "")
    return "\n".join(lines)
