import json
from pathlib import Path

import pytest
from nbformat import v4

from lectern import notes
from lectern.cli import main

from .conftest import write_notebook


def note(**fields) -> dict:
    return {"id": "a1", "cell": "c-x", "start": 0, "quote": "some words", **fields}


@pytest.fixture
def doc(tmp_path: Path) -> Path:
    path = tmp_path / "analysis.ipynb"
    path.write_text("{}")
    return path


def test_notes_are_kept_beside_the_document(tmp_path: Path):
    notebook, page = tmp_path / "analysis.ipynb", tmp_path / "analysis.md"
    assert notes.notes_path(notebook) == tmp_path / "analysis.notes.json"
    assert notes.notes_path(page) == tmp_path / "analysis.notes.json"
    # Both exist: the notebook keeps the plain name and the markdown file gets its own.
    notebook.write_text("{}")
    assert notes.notes_path(notebook) == tmp_path / "analysis.notes.json"
    assert notes.notes_path(page) == tmp_path / "analysis.md.notes.json"


def test_what_is_saved_is_what_is_loaded(doc: Path):
    assert notes.load(doc) == {"rev": "", "notes": []}

    kept = notes.save(doc, [note(note="A remark", suffix=" after")], "")
    assert kept == notes.load(doc) and kept["rev"]
    assert kept["notes"][0]["note"] == "A remark" and kept["notes"][0]["prefix"] == ""
    on_disk = json.loads(notes.notes_path(doc).read_text())
    assert on_disk["version"] == 1 and on_disk["notes"] == kept["notes"]
    # Nothing of the writing is left lying beside it.
    assert sorted(p.name for p in doc.parent.iterdir()) == ["analysis.ipynb", "analysis.notes.json"]


def test_a_save_from_an_old_version_is_handed_the_new_one(doc: Path):
    first = notes.save(doc, [note()], "")
    second = notes.save(doc, [note(), note(id="b2")], first["rev"])

    with pytest.raises(notes.Stale) as stale:
        notes.save(doc, [note(id="c3")], first["rev"])
    assert stale.value.current == second and notes.load(doc) == second
    with pytest.raises(notes.Stale):
        notes.save(doc, [note(id="c3")], "")


def test_no_notes_means_no_file(doc: Path):
    kept = notes.save(doc, [note()], "")
    assert notes.save(doc, [], kept["rev"]) == {"rev": "", "notes": []}
    assert not notes.notes_path(doc).exists()


@pytest.mark.parametrize(
    "sent",
    [
        {"not": "a list"},
        ["not an object"],
        [note(id="")],
        [note(id="../x")],
        [note(), note()],
        [note(quote="  ")],
        [note(quote="x" * 2001)],
        [note(start=-1)],
        [note(start="3")],
        [note(note=["a list"])],
        [note(path="/etc/passwd")],
        [note(id=f"n{n}") for n in range(2001)],
    ],
)
def test_notes_that_are_not_notes_are_refused(doc: Path, sent):
    with pytest.raises(notes.NotesError):
        notes.save(doc, sent, "")
    assert not notes.notes_path(doc).exists()


def test_a_link_in_the_files_place_is_not_written_through(doc: Path, tmp_path: Path):
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text("mine")
    notes.notes_path(doc).symlink_to(elsewhere)

    with pytest.raises(notes.NotesError):
        notes.save(doc, [note()], "")
    assert elsewhere.read_text() == "mine"


def test_a_file_that_is_not_notes_is_left_alone(doc: Path):
    notes.notes_path(doc).write_text("{ half")
    with pytest.raises(notes.NotesError):
        notes.load(doc)
    with pytest.raises(notes.NotesError):
        notes.save(doc, [note()], "")
    assert notes.notes_path(doc).read_text() == "{ half"


def markdown(source: str, cell_id: str):
    return v4.new_markdown_cell(source, id=cell_id)


def code(source: str, cell_id: str, count: int | None):
    return v4.new_code_cell(source, id=cell_id, execution_count=count)


def test_notes_as_markdown(tmp_path: Path, capsys):
    doc = write_notebook(
        tmp_path / "study.ipynb",
        [
            markdown("# Study\n\nAn opening.\n\n## Method\n\nHow it was *done*, at length.", "m1"),
            code("fit(model)", "k1", 7),
            markdown("## Results\n\nWhat came of it.", "m2"),
            code("plot()", "k2", None),
        ],
    )
    notes.save(
        doc,
        [
            note(id="n4", cell="c-k2", quote="plot()"),
            note(id="n5", cell="c-deleted", quote="words from a cell since deleted", note="Why?"),
            note(id="n2", cell="c-m1", start=40, quote="How it was done", note="Not\nconvinced."),
            note(id="n3", cell="c-k1", quote="fit(model)", note="Check the seed"),
            note(id="n1", cell="c-m1", start=8, quote="An opening."),
        ],
        "",
    )

    assert notes.to_markdown(doc) == "\n".join(
        [
            "# Notes on study.ipynb",
            "",
            "## Study",
            "",
            "> An opening.",
            "",
            "## Method",
            "",
            "> How it was done",
            "",
            "Not\nconvinced.",
            "",
            "Cell [7]:",
            "",
            "> fit(model)",
            "",
            "Check the seed",
            "",
            "## Results",
            "",
            "Cell #2:",
            "",
            "> plot()",
            "",
            "## From cells that are no longer in the notebook",
            "",
            "> words from a cell since deleted",
            "",
            "Why?",
            "",
        ]
    )

    assert main(["notes", str(doc)]) == 0
    assert capsys.readouterr().out == notes.to_markdown(doc)
    # A folder: every document in it that has notes, and no others.
    (tmp_path / "plain.md").write_text("# Plain\n\nNothing marked here.\n")
    assert main(["notes", str(tmp_path)]) == 0
    assert capsys.readouterr().out == notes.to_markdown(doc)
    assert main(["notes", str(tmp_path / "plain.md")]) == 0
    assert "Nothing is marked." in capsys.readouterr().out
    assert main(["notes", str(tmp_path / "missing.ipynb")]) == 1
