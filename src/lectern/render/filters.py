"""Template filters and HTML clean-up for cell outputs."""

import re

from bs4 import BeautifulSoup, Tag
from markupsafe import Markup, escape
from nbconvert.filters import ansi2html

# A table with any cell longer than this is read like prose, so its cells wrap.
PROSE_CELL = 60

_NUMBER = re.compile(r"[-+−]?[\d,]*\.?\d+(?:[eE][-+]?\d+)?%?")
_SPAN = re.compile(r"<span[^>]*>|</span>")


def _wrap_table(soup: BeautifulSoup, table: Tag) -> None:
    table.attrs.pop("border", None)
    for row in table.find_all("tr"):
        row.attrs.pop("style", None)
    cells = table.find_all(["td", "th"])
    prose = any(len(cell.get_text()) > PROSE_CELL for cell in cells)
    table["class"] = [*table.get("class", []), "prose-table" if prose else "data-table"]
    for cell in cells:
        if cell.name == "td" and _NUMBER.fullmatch(cell.get_text().strip()):
            cell["class"] = [*cell.get("class", []), "num"]
    table.wrap(soup.new_tag("div", attrs={"class": "table-wrap"}))


def wrap_tables(soup: BeautifulSoup) -> None:
    """Give every table not yet wrapped (those in markdown cells) a scrolling wrapper."""
    for table in soup.find_all("table"):
        if not table.find_parent(class_="table-wrap"):
            _wrap_table(soup, table)


# Elements that show something without containing any text.
_VISIBLE = ["img", "svg", "table", "video", "audio", "canvas", "iframe", "math", "hr"]

# An output's lines of traceback above which it starts folded.
LONG_TRACEBACK = 25


def placeholder(what: str) -> str:
    """The note left where an output cannot be shown, as HTML."""
    return (
        f'<p class="placeholder"><strong>{escape(what)}</strong> '
        "This output needs a running notebook and is not shown here.</p>"
    )


def clean_table_html(html: str) -> Markup:
    """An HTML output without its own styling or scripts, tables wrapped and classified.

    pandas ships a `<style scoped>` block, `border="1"` and a right-aligned header row with
    every DataFrame; all three fight the theme. Scripts would be blocked by the page's CSP
    anyway; an output that was nothing but a script (a plot drawn in the browser) would
    leave an empty space, so it is replaced by a note saying what was there.
    """
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script")
    for tag in [*scripts, *soup.find_all("style")]:
        tag.decompose()
    if scripts and not soup.get_text(strip=True) and not soup.find(_VISIBLE):
        return Markup(placeholder("Interactive output."))
    for table in soup.find_all("table"):
        _wrap_table(soup, table)
    return Markup(str(soup))


def error_html(output: dict) -> Markup:
    """A traceback: colours kept, the line naming the error in bold, a long one folded
    under that line so the page is not taken over by it."""
    lines = ansi2html("\n".join(output.get("traceback", []))).split("\n")
    last = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip()), None)
    # Left alone if a colour span runs across the line's end: wrapping it would misnest.
    if last is not None and lines[last].count("<span") == lines[last].count("</span>"):
        lines[last] = f"<strong>{lines[last]}</strong>"
    block = f'<pre class="error">{"\n".join(lines).strip("\n")}</pre>'
    if len(lines) <= LONG_TRACEBACK:
        return Markup(block)
    name = escape(f"{output.get('ename', 'Error')}: {output.get('evalue', '')}".strip(": "))
    return Markup(
        f'<details class="traceback"><summary><strong>{name}</strong>'
        f'<span class="label"> · {len(lines)} lines</span></summary>{block}</details>'
    )


def stream_lines(html: str) -> Markup:
    """Each line of already-escaped output in its own `<span class="l">`.

    The stylesheet gives those spans a hanging indent, so a wrapped line is told apart from
    a new one. An ANSI colour span that runs across a line break is closed at the end of the
    line and reopened on the next, keeping the markup nested properly.
    """
    lines = str(html).split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    out: list[str] = []
    open_spans: list[str] = []
    for line in lines:
        prefix = "".join(open_spans)
        for tag in _SPAN.findall(line):
            if tag != "</span>":
                open_spans.append(tag)
            elif open_spans:
                open_spans.pop()
        out.append(f'<span class="l">{prefix}{line}{"</span>" * len(open_spans)}\n</span>')
    return Markup("".join(out))
