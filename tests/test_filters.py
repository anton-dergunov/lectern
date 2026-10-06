from lectern.render.filters import clean_table_html, stream_lines

from .conftest import PANDAS_HTML


def test_pandas_table_loses_its_own_styling():
    html = str(clean_table_html(PANDAS_HTML))

    assert "<style" not in html
    assert "border=" not in html
    assert "text-align" not in html
    assert '<div class="table-wrap"><table class="dataframe data-table">' in html


def test_table_with_a_long_cell_is_a_prose_table():
    html = str(clean_table_html(f"<table><tr><td>{'word ' * 20}</td></tr></table>"))

    assert 'class="prose-table"' in html


def test_only_numeric_cells_are_marked():
    html = str(clean_table_html("<table><tr><td>-1,200.5</td><td>12%</td><td>v2</td></tr></table>"))

    assert html.count('class="num"') == 2
    assert "<td>v2</td>" in html


def test_stream_lines_wraps_each_line_once():
    assert str(stream_lines("a\n\nb\n")) == (
        '<span class="l">a\n</span><span class="l">\n</span><span class="l">b\n</span>'
    )


def test_stream_lines_keeps_colour_spans_nested_across_lines():
    html = str(stream_lines('<span class="ansi-red-fg">one\ntwo</span> three'))

    assert html == (
        '<span class="l"><span class="ansi-red-fg">one</span>\n</span>'
        '<span class="l"><span class="ansi-red-fg">two</span> three\n</span>'
    )
