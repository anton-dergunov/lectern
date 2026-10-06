"""The steps every rendered document goes through, whatever it was rendered from."""

from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from .filters import wrap_tables
from .links import rewrite_links
from .toc import Heading, extract_toc


@dataclass(frozen=True)
class Rendered:
    fragment: str
    toc: list[Heading]
    title: str
    has_math: bool


def finish(html: str, path: Path) -> Rendered:
    soup = BeautifulSoup(html, "html.parser")
    wrap_tables(soup)
    rewrite_links(soup, path)
    toc, title = extract_toc(soup)
    fragment = str(soup)
    return Rendered(fragment, toc, title or path.stem, 'class="math' in fragment)
