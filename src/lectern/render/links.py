"""Pointing a document's links at what the reader can actually open."""

from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from bs4 import BeautifulSoup

# jupytext names for the script paired with `name.ipynb`, most specific first.
PAIRED_SUFFIXES = (".nb.py", ".py")


def rewrite_links(soup: BeautifulSoup, doc: Path) -> None:
    """Send links to a paired `.py` script to its notebook; open external links in a new tab.

    Other relative links are left alone: URLs mirror the directory tree, so the browser
    resolves `../docs/x.md` to the right page by itself.
    """
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") or (href.startswith("/") and not href.startswith("//")):
            continue
        parts = urlsplit(href)
        if parts.scheme or parts.netloc:
            if parts.scheme in ("http", "https", ""):
                a["target"] = "_blank"
                a["rel"] = "noopener"
            continue
        path = unquote(parts.path)
        for suffix in PAIRED_SUFFIXES:
            if not path.endswith(suffix):
                continue
            if (doc.parent / (path[: -len(suffix)] + ".ipynb")).is_file():
                notebook = parts.path[: -len(suffix)] + ".ipynb"
                a["href"] = urlunsplit(parts._replace(path=notebook))
            break
