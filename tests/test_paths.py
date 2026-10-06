from pathlib import Path

import pytest

from lectern.paths import resolve


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
