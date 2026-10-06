"""Write the fixture notebooks in tests/fixtures, one per rendering case.

    uv run python scripts/make_fixtures.py

The notebooks are committed; rerun this only to add or change a case, then regenerate the
expected HTML with `uv run pytest --update-golden` and read the diff.
"""

import base64
import json
from pathlib import Path

from nbformat import v4

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# A 2x2 red PNG.
PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP8z8DAwMDAxAAGAA0GAQHt"
    "cnjRAAAAAElFTkSuQmCC"
)
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
    '<script>alert(1)</script><rect width="40" height="20" fill="#268bd2"/></svg>'
)
PANDAS = """<div>
<style scoped>
    .dataframe tbody tr th:only-of-type { vertical-align: middle; }
    .dataframe thead th { text-align: right; }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;"><th></th><th>system</th><th>calls</th><th>cost</th></tr>
  </thead>
  <tbody>
    <tr><th>0</th><td>mem0</td><td>12</td><td>0.004</td></tr>
    <tr><th>1</th><td>letta</td><td>1,340</td><td>-0.5</td></tr>
  </tbody>
</table>
</div>"""
PROSE_TABLE = """<table border="1" class="dataframe">
  <thead><tr><th></th><th>level</th><th>job</th></tr></thead>
  <tbody>
    <tr><th>0</th><td>EXPLICIT</td><td>atomic self-contained facts about the user, with absolute
    dates wherever the message gives a relative one</td></tr>
    <tr><th>1</th><td>DEDUCTIVE</td><td>logical implications of those facts</td></tr>
  </tbody>
</table>"""


def md(source: str, **kw):
    return v4.new_markdown_cell(source, **kw)


def code(source: str, outputs: list | None = None, count: int | None = 1):
    return v4.new_code_cell(source, outputs=outputs or [], execution_count=count)


def stream(text: str, name: str = "stdout"):
    return v4.new_output("stream", name=name, text=text)


def display(data: dict, **metadata):
    return v4.new_output("display_data", data=data, metadata=metadata)


def result(data: dict, count: int = 1):
    return v4.new_output("execute_result", data=data, execution_count=count)


CASES: dict[str, list] = {
    "markdown-table-and-fence": [
        md(
            "# Markdown\n\nA paragraph with **bold**, *emphasis*, `code` and a "
            "[link](https://example.com).\n\n"
            "| Notebook | What it shows |\n|---|---|\n| `a.py` | the first thing |\n"
            "| `b.py` | the second thing |\n\n"
            "```python\ndef f(x):\n    return x + 1  # a comment\n```\n\n"
            "```\nplain fence\n```\n\n> A quotation.\n\n1. one\n2. two\n\n- [ ] open\n- [x] done\n"
        )
    ],
    "long-stream-lines": [
        code(
            "print(text)",
            [
                stream(
                    "short line\n" + "a long line of printed prose that goes on " * 9 + "\n\nend\n"
                )
            ],
        )
    ],
    "tall-stream": [
        code("for i in range(80): print(i)", [stream("".join(f"row {i}\n" for i in range(80)))])
    ],
    "stderr": [code("warn()", [stream("out\n"), stream("UserWarning: careful\n", "stderr")])],
    "ansi-stream": [
        code(
            "print(colored)",
            [stream("\x1b[31mred across\ntwo lines\x1b[0m plain \x1b[1;32mbold green\x1b[0m\n")],
        )
    ],
    "pandas-table": [code("df", [result({"text/html": PANDAS, "text/plain": "   system  calls"})])],
    "prose-table": [code("df", [result({"text/html": PROSE_TABLE, "text/plain": "   level"})])],
    "png": [
        code(
            "plt.show()",
            [
                display(
                    {"image/png": PNG, "text/plain": "<Figure>"},
                    **{"image/png": {"width": 320, "height": 240}},
                )
            ],
        )
    ],
    "svg": [code("draw()", [display({"image/svg+xml": SVG, "text/plain": "<SVG>"})])],
    "error": [
        code(
            "1 / 0",
            [
                v4.new_output(
                    "error",
                    ename="ZeroDivisionError",
                    evalue="division by zero",
                    traceback=[
                        "\x1b[0;31m-----------------------------------\x1b[0m",
                        "\x1b[0;31mZeroDivisionError\x1b[0m  Traceback (most recent call last)",
                        "Cell \x1b[0;32mIn[1], line 1\x1b[0m\n\x1b[0;32m----> 1\x1b[0m 1 / 0",
                        "\x1b[0;31mZeroDivisionError\x1b[0m: division by zero",
                    ],
                )
            ],
        )
    ],
    "math": [
        md(
            "# Math\n\nInline $x_1 < y$ and a price of \\$5.\n\n$$\\sum_{i=1}^n i = "
            "\\frac{n(n+1)}{2}$$\n\n\\begin{align}a &= b\\\\c &= d\\end{align}\n"
        ),
        code("print('$PATH is not math')", [stream("$PATH is not math $x$\n")]),
    ],
    "latex-output": [
        code(
            "Math('x^2')", [result({"text/latex": "$\\displaystyle x^{2}$", "text/plain": "x**2"})]
        )
    ],
    "plotly-only": [
        code(
            "fig.show()", [display({"application/vnd.plotly.v1+json": {"data": [], "layout": {}}})]
        )
    ],
    "plotly-with-picture": [
        code(
            "fig.show()",
            [
                display(
                    {
                        "application/vnd.plotly.v1+json": {"data": [], "layout": {}},
                        "text/html": '<div id="p1"></div><script>Plotly.newPlot("p1")</script>',
                        "image/png": PNG,
                    }
                )
            ],
        )
    ],
    "script-only-html": [
        code("chart", [result({"text/html": '<div id="c1"></div><script>draw("c1")</script>'})])
    ],
    "long-traceback": [
        code(
            "deep()",
            [
                v4.new_output(
                    "error",
                    ename="RecursionError",
                    evalue="maximum recursion depth exceeded",
                    traceback=[
                        "Traceback (most recent call last)",
                        *[f'  File "deep.py", line {n}, in deep\n    deep()' for n in range(1, 16)],
                        "\x1b[0;31mRecursionError\x1b[0m: maximum recursion depth exceeded",
                    ],
                )
            ],
        )
    ],
    "widget": [
        code(
            "slider",
            [
                display(
                    {
                        "application/vnd.jupyter.widget-view+json": {
                            "model_id": "abc",
                            "version_major": 2,
                            "version_minor": 0,
                        },
                        "text/plain": "IntSlider(value=3)",
                    }
                )
            ],
        )
    ],
    "javascript": [
        code(
            "show()",
            [
                display(
                    {
                        "application/javascript": "alert(1)",
                        "text/html": '<script>alert(2)</script><p onclick="x()">kept text</p>',
                    }
                )
            ],
        )
    ],
    "attachment": [
        md(
            "# Attachment\n\n![a red square](attachment:square.png)\n",
            attachments={"square.png": {"image/png": PNG}},
        )
    ],
    "long-code-cell": [code("\n".join(f"value_{i} = {i}" for i in range(45)), count=7)],
    "no-h1": [md("## Only a second-level heading\n\nText.\n\n## Only a second-level heading\n")],
    "never-run": [
        code("x = 1", count=None),
        md("Text between."),
        code("", [stream("orphan\n")], count=None),
    ],
    "raw-html-in-markdown": [
        md(
            "# Raw\n\n<details><summary>More</summary>\n\nHidden text.\n\n</details>\n\n<b>bold</b>\n"
        )
    ],
}

# Long enough to scroll through several screens: for the browser checks, not a golden case.
LONG_READ = [md("# A long read\n\nAn opening paragraph, so the listing has a summary to show.\n")]
for part in range(1, 13):
    LONG_READ.append(
        md(f"## Part {part}\n\n" + ("Sentence after sentence of prose to read. " * 40) + "\n")
    )
    LONG_READ.append(
        code(
            f"result = step({part})\nprint(result)",
            [stream(f"step {part} done\n" + "a printed line\n" * 6)],
            count=part,
        )
    )
    if part % 4 == 0:
        LONG_READ.append(md(f"### Aside {part // 4}\n\nA shorter remark.\n"))


def write(name: str, cells: list, minor: int = 5) -> None:
    for index, cell in enumerate(cells):
        cell["id"] = f"cell-{index}"
    nb = v4.new_notebook(cells=cells)
    nb.metadata["language_info"] = {"name": "python", "pygments_lexer": "ipython3"}
    data = json.loads(json.dumps(nb))
    if minor < 5:
        data["nbformat_minor"] = minor
        for cell in data["cells"]:
            del cell["id"]
    (FIXTURES / f"{name}.ipynb").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    assert base64.b64decode(PNG).startswith(b"\x89PNG")
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, cells in CASES.items():
        write(name, cells)
    write("no-cell-ids", [md("# Old format\n\nSaved by nbformat 4.4."), code("1 + 1")], minor=4)
    write("long-read", LONG_READ)
    print(f"wrote {len(CASES) + 2} notebooks to {FIXTURES}")


if __name__ == "__main__":
    main()
