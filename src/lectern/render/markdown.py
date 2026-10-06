"""Markdown to HTML, for notebook cells and for standalone `.md` files."""

import re
from html import unescape as html_unescape
from pathlib import Path

from nbconvert.filters.markdown_mistune import IPythonRenderer, MarkdownWithMath

from .document import Rendered, finish

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_IMG_SRC = re.compile(
    r"""(?P<before><img\b[^>]*?\bsrc\s*=\s*(?P<quote>["']))(?P<src>.*?)(?P=quote)""",
    re.IGNORECASE | re.DOTALL,
)


class ReaderMarkdownRenderer(IPythonRenderer):
    """Math comes out in its own element instead of as text between dollar signs.

    That makes "does this page have math" an exact question, and lets the math renderer
    touch only these elements, never a `$` that a cell happened to print.
    """

    def _html_embed_images(self, html: str) -> str:
        """Embed the images of a piece of raw HTML without rewriting the HTML around them.

        The inherited version parses each piece by itself and writes it back out. Raw HTML
        reaches the renderer in pieces (an opening `<details>` and its closing tag are
        separate blocks, with the markdown between them; so are `<b>` and `</b>`), and a
        piece parsed alone gets its open tags closed: the `<details>` ends up empty and
        its content outside it.
        """

        def embed(match: re.Match) -> str:
            data = self._src_to_base64(html_unescape(match["src"]))
            return match[0] if data is None else f"{match['before']}{data}{match['quote']}"

        return _IMG_SRC.sub(embed, html)

    def inline_math(self, body: str) -> str:
        return f'<span class="math inline">{self.escape_html(body)}</span>'

    # Display math is still inline content to the parser, so it lands inside a <p>:
    # a span, shown as a block by the stylesheet.
    def block_math(self, body: str) -> str:
        return f'<span class="math display">{self.escape_html(body)}</span>'

    def latex_environment(self, name: str, body: str) -> str:
        name, body = self.escape_html(name), self.escape_html(body)
        return f'<span class="math display">\\begin{{{name}}}{body}\\end{{{name}}}</span>'


def markdown_to_html(source: str, **renderer_options) -> str:
    renderer = ReaderMarkdownRenderer(escape=False, **renderer_options)
    return MarkdownWithMath(renderer=renderer).render(source)


def render_markdown(path: Path) -> Rendered:
    source = _FRONT_MATTER.sub("", path.read_text(encoding="utf-8"), count=1)
    html = markdown_to_html(source)
    return finish(f'<section class="cell md">\n{html}</section>\n', path)
