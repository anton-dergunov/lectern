from pathlib import Path

from bs4 import BeautifulSoup

from lectern.render.links import rewrite_links


def rewrite(html: str, doc: Path) -> str:
    soup = BeautifulSoup(html, "html.parser")
    rewrite_links(soup, doc)
    return str(soup)


def test_paired_script_links_go_to_the_notebook(tmp_path: Path):
    (tmp_path / "a.ipynb").write_text("{}")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b c.ipynb").write_text("{}")
    doc = tmp_path / "index.md"

    assert rewrite('<a href="a.py#top">a</a>', doc) == '<a href="a.ipynb#top">a</a>'
    assert rewrite('<a href="a.nb.py">a</a>', doc) == '<a href="a.ipynb">a</a>'
    assert rewrite('<a href="sub/b%20c.py">b</a>', doc) == '<a href="sub/b%20c.ipynb">b</a>'


def test_script_without_a_notebook_is_left_alone(tmp_path: Path):
    assert rewrite('<a href="tool.py">t</a>', tmp_path / "index.md") == '<a href="tool.py">t</a>'


def test_only_external_links_open_a_new_tab(tmp_path: Path):
    doc = tmp_path / "index.md"

    assert 'target="_blank"' in rewrite('<a href="https://example.com/x.py">e</a>', doc)
    assert 'target="_blank"' in rewrite('<a href="//example.com">e</a>', doc)
    for href in ("#part", "other.md", "../docs/x.md#y", "mailto:a@example.com"):
        assert "target" not in rewrite(f'<a href="{href}">l</a>', doc)
