from pathlib import Path

import pytest

from lectern.paths import ignored, resolve


def test_documents_images_and_directories_resolve(root: Path):
    assert resolve(root, "notebooks/sample.ipynb") == (root / "notebooks/sample.ipynb").resolve()
    assert resolve(root, "docs/pixel.png") is not None
    assert resolve(root, "docs/") == (root / "docs").resolve()
    assert resolve(root, "") == root.resolve()


@pytest.mark.parametrize(
    "rel",
    [
        "../outside.md",
        "docs/../../outside.md",
        ".env",
        ".venv/hidden.md",
        "notebooks/sample.py",
        "data.csv",
        "docs\\note.md",
        "docs/note.md\x00.png",
        # A symlink inside the root that points out of it.
        "escape.md",
    ],
)
def test_everything_else_is_refused(root: Path, rel: str):
    assert resolve(root, rel) is None


def test_absolute_path_stays_under_the_root(root: Path):
    # Leading slashes are dropped, so this names <root>/etc/passwd, which does not exist.
    target = resolve(root, "/etc/passwd")
    assert target is not None and target.is_relative_to(root.resolve()) and not target.exists()


def ignore(root: Path, text: str) -> None:
    (root / ".lecternignore").write_text(text)


def test_an_ignored_name_is_refused_at_any_depth(root: Path):
    (root / "docs" / "private").mkdir()
    (root / "docs" / "private" / "plan.md").write_text("# Plan\n")
    ignore(root, "# not for the tablet\n\nprivate/\n*.png\n")

    assert resolve(root, "docs/private/plan.md") is None
    assert resolve(root, "docs/private/") is None
    assert resolve(root, "docs/pixel.png") is None
    assert resolve(root, "docs/note.md") is not None
    assert resolve(root, "") is not None


def test_an_ignored_path_is_counted_from_the_top(root: Path):
    (root / "notebooks" / "docs").mkdir()
    (root / "notebooks" / "docs" / "note.md").write_text("# Another\n")
    ignore(root, "/docs\nnotebooks/sample.ipynb\n")

    assert resolve(root, "docs/note.md") is None
    assert resolve(root, "notebooks/sample.ipynb") is None
    assert resolve(root, "notebooks/docs/note.md") is not None


def test_ignoring_does_not_depend_on_letter_case(root: Path):
    ignore(root, "Docs\n")

    assert resolve(root, "docs/note.md") is None
    assert resolve(root, "DOCS/note.md") is None


def test_a_link_to_something_ignored_is_refused(root: Path):
    (root / "shown.md").symlink_to(root / "docs" / "note.md")
    assert resolve(root, "shown.md") is not None

    ignore(root, "docs\n")

    assert resolve(root, "shown.md") is None


def test_the_ignore_list_is_followed_as_it_changes(root: Path):
    assert not ignored(root, ["docs", "note.md"])
    ignore(root, "docs\n")
    assert ignored(root, ["docs", "note.md"])
    ignore(root, "notebooks\n")
    assert not ignored(root, ["docs", "note.md"])
    (root / ".lecternignore").unlink()
    assert not ignored(root, ["notebooks", "sample.ipynb"])
