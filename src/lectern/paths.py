"""Mapping a URL path onto a file under a served root, and nothing outside it."""

from pathlib import Path

DOC_SUFFIXES = {".ipynb", ".md"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
ALLOWED = DOC_SUFFIXES | IMAGE_SUFFIXES


def resolve(root: Path, rel: str) -> Path | None:
    """The file or directory `rel` names under `root`, or None if it must not be served.

    `rel` is the already percent-decoded URL path below the root name. Dot-prefixed
    components cover both `..` and hidden files; resolving symlinks before the containment
    check stops a link inside the root from pointing out of it.
    """
    if "\x00" in rel or "\\" in rel:
        return None
    parts = [p for p in rel.split("/") if p]
    if any(p.startswith(".") for p in parts):
        return None
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root.resolve()):
        return None
    if target.is_file() and target.suffix.lower() not in ALLOWED:
        return None
    return target
