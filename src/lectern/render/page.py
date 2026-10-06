"""The page shell around a rendered fragment, a listing or an error."""

import hashlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

PACKAGE = Path(__file__).resolve().parent.parent
TEMPLATES = PACKAGE / "templates"
STATIC = PACKAGE / "static"

THEME_COLOR = "#fdf6e3"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(default=True),
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True)
class Crumb:
    name: str
    href: str


@cache
def asset_hash() -> str:
    """Changes whenever a stylesheet, icon or template does, so cached pages are dropped."""
    digest = hashlib.sha1()
    for directory in (STATIC, TEMPLATES):
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            digest.update(path.relative_to(PACKAGE).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def static_url() -> str:
    return f"/_static/{asset_hash()}"


def render_page(template: str, **context) -> str:
    return _env.get_template(template).render(
        static=static_url(), theme_color=THEME_COLOR, **context
    )
