"""Markdown to HTML, for notebook cells and for standalone `.md` files."""

import re
from pathlib import Path

from nbconvert.filters.markdown_mistune import IPythonRenderer, MarkdownWithMath

from .document import Rendered, finish

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


class ReaderMarkdownRenderer(IPythonRenderer):
    """Math comes out in its own element instead of as text between dollar signs.

    That makes "does this page have math" an exact question, and lets the math renderer
    touch only these elements, never a `$` that a cell happened to print.
    """

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
