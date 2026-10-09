from pathlib import Path

from lectern import library


def test_discover_skips_hidden_build_and_other_files(root: Path):
    found = {p.relative_to(root).as_posix() for p in library.discover(root)}

    assert found == {"notebooks/sample.ipynb", "docs/note.md", "escape.md"}


def test_discover_leaves_out_what_the_root_ignores(root: Path):
    (root / "notebooks" / "drafts").mkdir()
    (root / "notebooks" / "drafts" / "rough.md").write_text("# Rough\n")
    (root / ".lecternignore").write_text("drafts\n/docs\n")

    found = {p.relative_to(root).as_posix() for p in library.discover(root)}
    assert found == {"notebooks/sample.ipynb", "escape.md"}
    # A folder inside the root is listed by the root's list, not by one of its own.
    inside = library.discover(root / "notebooks", root)
    assert [p.name for p in inside] == ["sample.ipynb"]
    assert [g.name for g in library.listing(root / "notebooks", root=root).groups] == [""]


def test_describe_notebook(root: Path):
    description = library.describe(root / "notebooks" / "sample.ipynb")

    assert description.title == "Sample notebook"
    # The paragraph under the heading, as plain text, stopping before the next heading.
    assert description.summary == "The first paragraph, with a script, a doc and a site."
    assert description.minutes >= 1


def test_describe_falls_back_to_the_file_name(tmp_path: Path):
    broken = tmp_path / "half-saved.ipynb"
    broken.write_text('{"cells": [')
    plain = tmp_path / "plain.md"
    plain.write_text("no heading here\n")

    assert library.describe(broken).title == "half-saved"
    assert library.describe(plain).title == "plain"


def test_describe_follows_the_file(tmp_path: Path):
    path = tmp_path / "doc.md"
    path.write_text("# One\n")
    assert library.describe(path).title == "One"

    path.write_text("# Two, longer\n")
    assert library.describe(path).title == "Two, longer"


def test_listing_groups_by_directory_with_relative_links(root: Path):
    listing = library.listing(root)

    assert [g.name for g in listing.groups] == ["", "docs", "notebooks"]
    notebooks = listing.groups[2]
    assert notebooks.href == "notebooks/"
    assert [e.href for e in notebooks.notebooks] == ["notebooks/sample.ipynb"]
    assert [e.title for e in listing.groups[1].pages] == ["A note"]
    # Too few documents for a "recently changed" strip to add anything.
    assert listing.recent == []


def test_listing_of_a_subdirectory_links_relative_to_it(root: Path):
    listing = library.listing(root / "notebooks")

    assert [(g.name, [e.href for e in g.notebooks]) for g in listing.groups] == [
        ("", ["sample.ipynb"])
    ]


def test_recent_strip_appears_in_a_large_folder(tmp_path: Path):
    for i in range(12):
        (tmp_path / f"doc{i:02}.md").write_text(f"# Doc {i}\n")

    assert len(library.listing(tmp_path).recent) == library.RECENT
