from pathlib import Path

from nbformat import v4

from lectern.render import render_document

from .conftest import write_notebook


def test_notebook_fragment_has_no_notebook_chrome(root: Path):
    rendered = render_document(root / "notebooks" / "sample.ipynb")
    fragment = rendered.fragment

    assert "In&nbsp;[" not in fragment and "In [" not in fragment
    assert "<style" not in fragment
    assert "<script" not in fragment and "alert(1)" not in fragment
    assert "output_area" not in fragment and "input_area" not in fragment
    # The HTML form of an output is what shows when its javascript form is dropped.
    assert "<p>shown</p>" in fragment


def test_notebook_structure(root: Path):
    fragment = render_document(root / "notebooks" / "sample.ipynb").fragment

    assert fragment.count('<section class="cell md"') == 1
    assert fragment.count('<section class="cell code"') == 2
    assert '<details class="src" data-lines="2" open' in fragment
    assert '<span class="cell-n" title="This cell in the notebook">[1]</span>' in fragment
    # A cell that was never run is numbered among the code cells instead.
    assert ">#2</span>" in fragment
    # The 40-line cell starts collapsed and says how long it is.
    assert "Code · 40 lines" in fragment
    assert '<pre class="stream wrap"><span class="l">hello\n</span>' in fragment
    assert "world &lt;b&gt;" in fragment
    assert '<pre class="stream wrap stderr">' in fragment
    assert '<pre class="error">' in fragment and "ansi-red-fg" in fragment
    assert '<table class="dataframe data-table">' in fragment
    assert '<td class="num">0.75</td>' in fragment


def test_title_toc_and_math(root: Path):
    rendered = render_document(root / "notebooks" / "sample.ipynb")

    assert rendered.title == "Sample notebook"
    assert [(h.level, h.text) for h in rendered.toc] == [
        (1, "Sample notebook"),
        (2, "Part"),
        (2, "Part"),
    ]
    ids = [h.id for h in rendered.toc]
    assert len(set(ids)) == len(ids)
    assert all(f'id="{i}"' in rendered.fragment for i in ids)
    assert rendered.has_math
    assert '<span class="math inline">x_1</span>' in rendered.fragment


def test_links_in_a_notebook(root: Path):
    fragment = render_document(root / "notebooks" / "sample.ipynb").fragment

    assert '<a href="sample.ipynb">script</a>' in fragment
    assert '<a href="../docs/note.md">doc</a>' in fragment
    assert '<a href="https://example.com" rel="noopener" target="_blank">site</a>' in fragment


def test_notebook_without_cell_ids_or_heading(tmp_path: Path):
    path = write_notebook(tmp_path / "old.ipynb", [v4.new_markdown_cell("just text")])
    raw = path.read_text().replace('"nbformat_minor": 5', '"nbformat_minor": 4')
    lines = [line for line in raw.splitlines() if '"id":' not in line]
    path.write_text("\n".join(lines))

    rendered = render_document(path)

    assert rendered.title == "old"
    assert 'id="c-n0"' in rendered.fragment
    assert not rendered.has_math


def test_markdown_file(root: Path):
    rendered = render_document(root / "docs" / "note.md")

    assert rendered.title == "A note"
    assert rendered.fragment.startswith('<section class="cell md">')
    assert '<a href="other.md">x</a>' in rendered.fragment


def test_markdown_front_matter_is_not_shown(tmp_path: Path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: hidden\n---\n# Shown\n")

    rendered = render_document(path)

    assert rendered.title == "Shown"
    assert "hidden" not in rendered.fragment
