import threading
from pathlib import Path

import nbformat
import pytest
from nbformat import v4

from lectern.server.app import make_server

PANDAS_HTML = """<div>
<style scoped>
    .dataframe tbody tr th { vertical-align: top; }
</style>
<table border="1" class="dataframe">
  <thead><tr style="text-align: right;"><th></th><th>name</th><th>score</th></tr></thead>
  <tbody><tr><th>0</th><td>alpha</td><td>0.75</td></tr></tbody>
</table>
</div>"""


def write_notebook(path: Path, cells: list, **metadata) -> Path:
    nb = v4.new_notebook(cells=cells, metadata=metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, path)
    return path


def sample_cells() -> list:
    return [
        v4.new_markdown_cell(
            "# Sample notebook\n\nThe *first* paragraph, with a [script](sample.py), "
            "a [doc](../docs/note.md) and a [site](https://example.com).\n\n"
            "## Part\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n## Part\n\nInline $x_1$ math."
        ),
        v4.new_code_cell(
            "import pandas as pd\nprint('hello')",
            execution_count=1,
            outputs=[
                v4.new_output("stream", name="stdout", text="hello\nworld <b>\n"),
                v4.new_output("stream", name="stderr", text="careful\n"),
                v4.new_output(
                    "execute_result",
                    execution_count=1,
                    data={"text/html": PANDAS_HTML, "text/plain": "   name  score"},
                ),
                v4.new_output(
                    "display_data",
                    data={
                        "application/javascript": "alert(1)",
                        "text/html": "<script>alert(1)</script><p>shown</p>",
                    },
                ),
                v4.new_output(
                    "error",
                    ename="ValueError",
                    evalue="bad",
                    traceback=["\x1b[0;31mValueError\x1b[0m: bad"],
                ),
            ],
        ),
        v4.new_code_cell("\n".join(f"x{i} = {i}" for i in range(40))),
    ]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A served directory: one notebook with its paired script, some markdown, and
    files that must never be served."""
    root = tmp_path / "proj"
    write_notebook(root / "notebooks" / "sample.ipynb", sample_cells())
    (root / "notebooks" / "sample.py").write_text("print('hello')\n")
    (root / "docs").mkdir()
    (root / "docs" / "note.md").write_text("# A note\n\nSome text, see [x](other.md).\n")
    (root / "docs" / "pixel.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / ".env").write_text("SECRET=1\n")
    (root / "data.csv").write_text("a,b\n")
    (root / ".venv").mkdir()
    (root / ".venv" / "hidden.md").write_text("# hidden\n")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "dep.md").write_text("# dep\n")
    (tmp_path / "outside.md").write_text("# outside\n")
    (root / "escape.md").symlink_to(tmp_path / "outside.md")
    return root


@pytest.fixture
def server(root: Path):
    server = make_server({"proj": root}, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
