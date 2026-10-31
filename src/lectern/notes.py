"""Highlights and remarks on a document, kept in a file beside it.

analysis.ipynb  ->  analysis.notes.json

    {"version": 1, "notes": [{"id": …, "cell": "c-…", "start": 12, "quote": "the words",
      "prefix": "…", "suffix": "…", "note": "a remark", "author": "Anton",
      "created": …, "updated": …}]}

`author` is optional: notes made before it existed, or by a reader who has not given a name,
have none.

This is the one thing lectern writes on a device's say-so. What is written is never what
was sent: the notes are checked field by field and the file is composed here, at a path
worked out from the document's, so a request can neither name a file nor put anything in
one but notes.
"""

import hashlib
import json
import os
import random
import re
import threading
import time
from datetime import datetime, timezone
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
    "author": 64,
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
        if not clean["author"]:
            del clean["author"]  # files stay as they were for notes without one
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


# ---- Added from the command line, by name of their author ----

# What the reader leaves out of the text it marks (`NOT_MARKED` in static/reader.js).
_NOT_MARKED_TAGS = {"button", "summary"}
_NOT_MARKED_CLASSES = {"cell-n", "stream-tools", "anchor-link", "katex-mathml", "diagram"}
CONTEXT = 32  # characters kept on each side of a quote, as the reader keeps


def page_text(doc: Path) -> tuple[str, dict[str, tuple[int, int]]]:
    """The document's text as the reader builds it, and where each cell's text lies in it.

    The reader joins the text of every cell on the page, leaving out buttons, cell numbers
    and diagrams; notes are anchored in that text. This rebuilds it from the same rendered
    page, so that a quote can be found before it is saved. Formulas are typeset on the
    device, so text inside one may not match.
    """
    from bs4 import BeautifulSoup, Comment, NavigableString

    from .render import render_document

    soup = BeautifulSoup(render_document(doc).fragment, "html.parser")
    pieces: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    length = 0

    def left_out(node) -> bool:
        for parent in node.parents:
            if parent.name in _NOT_MARKED_TAGS:
                return True
            if _NOT_MARKED_CLASSES & set(parent.get("class") or []):
                return True
        return False

    for cell in soup.find_all(recursive=False):
        if "cell" not in (cell.get("class") or []):
            continue
        start = length
        for node in cell.descendants:
            if not isinstance(node, NavigableString) or isinstance(node, Comment):
                continue
            if left_out(node):
                continue
            pieces.append(str(node))
            length += len(node)
        spans.setdefault(cell.get("id", ""), (start, length))
    return "".join(pieces), spans


def _new_id() -> str:
    # As the reader makes them: the time and a few random letters, in base 36.
    def base36(n: int) -> str:
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        out = ""
        while n:
            n, r = divmod(n, 36)
            out = digits[r] + out
        return out or "0"

    return base36(int(time.time() * 1000)) + base36(random.getrandbits(40))[:6]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def anchor(text: str, spans: dict[str, tuple[int, int]], quote: str) -> dict | str:
    """Where a quote is in the page text, as a note records it, or why it cannot be kept."""
    quote = quote.strip()
    if not quote:
        return "the quote is empty"
    found = []
    at = text.find(quote)
    while at >= 0:
        found.append(at)
        at = text.find(quote, at + 1)
    if not found:
        return "not in the text as the page shows it (quote the words as read, without markdown)"
    if len(found) > 1:
        return f"appears {len(found)} times; quote more words so that it is found once"
    at = found[0]
    cell = next((cid for cid, (s, e) in spans.items() if s <= at < e), "")
    start = at - spans.get(cell, (0, 0))[0]
    return {
        "cell": cell,
        "start": start,
        "quote": quote,
        "prefix": text[max(0, at - CONTEXT) : at],
        "suffix": text[at + len(quote) : at + len(quote) + CONTEXT],
    }


def add(doc: Path, entries: list[dict], author: str) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Add notes by `author` to a document: each entry a {"quote", "note"}.

    Returns the notes added and the entries left out, each with the reason. Nothing is
    saved if no entry can be kept.
    """
    text, spans = page_text(doc)
    added, refused = [], []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("quote"), str):
            refused.append((entry, "each entry needs a quote"))
            continue
        place = anchor(text, spans, entry["quote"])
        if isinstance(place, str):
            refused.append((entry, place))
            continue
        now = _now()
        added.append(
            {
                "id": _new_id(),
                **place,
                "note": str(entry.get("note", "")),
                "author": author,
                "created": now,
                "updated": now,
            }
        )
    if added:
        _replace(doc, lambda notes: notes + added)
    return added, refused


def clear(doc: Path, author: str) -> int:
    """Remove every note by `author`; returns how many there were."""
    removed = 0

    def without(notes: list[dict]) -> list[dict]:
        nonlocal removed
        kept = [note for note in notes if note.get("author", "") != author]
        removed = len(notes) - len(kept)
        return kept

    _replace(doc, without)
    return removed


def _replace(doc: Path, change) -> dict:
    """Apply `change` to the notes on disk, trying again if a device saves in between."""
    for _ in range(3):
        current = load(doc)
        try:
            return save(doc, change(current["notes"]), current["rev"])
        except Stale:
            continue
    raise NotesError("the notes kept changing while they were being saved; try again")


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


def to_markdown(doc: Path, author: str | None = None) -> str:
    """The document's notes in reading order, each under its heading and cell number.

    With `author`, only that author's notes ("" for notes with none)."""
    notes = load(doc)["notes"]
    if author is not None:
        notes = [note for note in notes if note.get("author", "") == author]
    places = _places(doc)
    lines = [f"# Notes on {doc.name}", ""]
    if not notes:
        return "\n".join([*lines, "Nothing is marked.", ""])

    def entry(note: dict, label: str) -> list[str]:
        out = [f"Cell {label}:", ""] if label else []
        out += [_quoted(note.get("quote", "")), ""]
        who = f"**{note['author']}:** " if note.get("author") else ""
        if note.get("note"):
            out += [who + note["note"], ""]
        elif who:
            out += [f"*Marked by {note['author']}*", ""]
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
