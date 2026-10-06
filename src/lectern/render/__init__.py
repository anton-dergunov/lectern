"""Turning a notebook or markdown file into an HTML fragment for the page shell."""

from pathlib import Path

from .document import Rendered

# Part of every cache key: raise it when a change here alters the HTML for an unchanged file.
RENDER_VERSION = 2

__all__ = ["RENDER_VERSION", "Rendered", "render_document"]


def render_document(path: Path) -> Rendered:
    # Imported late: nbconvert takes about half a second to import.
    if path.suffix.lower() == ".ipynb":
        from .notebook import render_notebook

        return render_notebook(path)
    from .markdown import render_markdown

    return render_markdown(path)
