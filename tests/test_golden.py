"""Each fixture notebook renders to exactly the HTML recorded for it.

After a deliberate change to the rendering, run `uv run pytest --update-golden`, read the
diff of tests/golden, and commit it with the change.
"""

import re
from pathlib import Path

import pytest

from lectern.render import render_document

HERE = Path(__file__).resolve().parent
FIXTURES = sorted((HERE / "fixtures").glob("*.ipynb"))
GOLDEN = HERE / "golden"
# The reading-position fixture is all repetition; its HTML would only pad the diff.
CASES = [path for path in FIXTURES if path.stem != "long-read"]


@pytest.mark.parametrize("fixture", CASES, ids=lambda p: p.stem)
def test_fragment_matches_golden(fixture: Path, request: pytest.FixtureRequest):
    fragment = render_document(fixture).fragment
    golden = GOLDEN / f"{fixture.stem}.html"
    if request.config.getoption("--update-golden"):
        GOLDEN.mkdir(exist_ok=True)
        golden.write_text(fragment, encoding="utf-8")
    assert golden.exists(), "no golden file yet: run pytest --update-golden"
    assert fragment == golden.read_text(encoding="utf-8")


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.stem)
def test_no_fixture_leaks_notebook_chrome_or_scripts(fixture: Path):
    rendered = render_document(fixture)
    fragment = rendered.fragment

    assert "In&nbsp;[" not in fragment and "In [" not in fragment
    assert "<style" not in fragment
    assert "<script" not in fragment and "alert(" not in fragment
    ids = [heading.id for heading in rendered.toc]
    assert len(set(ids)) == len(ids)
    cell_ids = re.findall(r'<section class="cell [a-z]+" id="([^"]+)"', fragment)
    assert len(set(cell_ids)) == len(cell_ids)


def test_math_is_found_only_where_there_is_math():
    has_math = {path.stem: render_document(path).has_math for path in FIXTURES}

    assert {name for name, found in has_math.items() if found} == {"math", "latex-output"}


def test_printed_dollar_signs_are_not_math():
    fragment = render_document(HERE / "fixtures" / "math.ipynb").fragment

    assert fragment.count('class="math inline"') == 1
    assert fragment.count('class="math display"') == 2
    assert "$PATH is not math $x$" in fragment
