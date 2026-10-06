import os
from pathlib import Path

import pytest

from lectern import cache
from lectern.cache import RenderCache, RenderError
from lectern.render import Rendered


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(cache, "RETRY_DELAY", 0)


class CountingRenderer:
    """Renders a file as its text; a file containing "broken" fails like a half-saved one."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, path: Path) -> Rendered:
        self.calls += 1
        text = path.read_text()
        if "broken" in text:
            raise ValueError("not JSON")
        return Rendered(text, [], path.stem, False)


def rewrite(path: Path, text: str) -> None:
    """Write `text` and move the mtime on, as a real save a moment later would."""
    before = path.stat().st_mtime_ns if path.exists() else 0
    path.write_text(text)
    os.utime(path, ns=(before + 1_000_000_000, before + 1_000_000_000))


def test_unchanged_file_renders_once(tmp_path: Path):
    path = tmp_path / "a.md"
    path.write_text("one")
    render = CountingRenderer()
    cached = RenderCache(render)

    first, second = cached.get(path), cached.get(path)

    assert render.calls == 1
    assert first.rendered.fragment == "one"
    assert first.etag == second.etag and not second.stale


def test_changed_file_renders_again_with_a_new_etag(tmp_path: Path):
    path = tmp_path / "a.md"
    path.write_text("one")
    render = CountingRenderer()
    cached = RenderCache(render)
    first = cached.get(path)

    rewrite(path, "two")
    second = cached.get(path)

    assert render.calls == 2
    assert second.rendered.fragment == "two"
    assert second.etag != first.etag


def test_broken_file_serves_the_last_good_render(tmp_path: Path):
    path = tmp_path / "a.md"
    path.write_text("good")
    cached = RenderCache(CountingRenderer())
    cached.get(path)

    rewrite(path, "broken")
    hit = cached.get(path)

    assert hit.stale and hit.rendered.fragment == "good"

    rewrite(path, "fixed")
    assert cached.get(path).rendered.fragment == "fixed"


def test_broken_file_with_no_earlier_render_raises(tmp_path: Path):
    path = tmp_path / "a.md"
    path.write_text("broken")
    render = CountingRenderer()

    with pytest.raises(RenderError, match="not JSON"):
        RenderCache(render).get(path)
    # Tried twice: the first failure may have caught the file mid-save.
    assert render.calls == 2


def test_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        RenderCache(CountingRenderer()).get(tmp_path / "gone.md")


def test_least_recently_used_entry_is_dropped(tmp_path: Path):
    render = CountingRenderer()
    cached = RenderCache(render, size=2)
    paths = [tmp_path / f"{name}.md" for name in "abc"]
    for path in paths:
        path.write_text(path.stem)
        cached.get(path)

    cached.get(paths[2])
    assert render.calls == 3
    cached.get(paths[0])
    assert render.calls == 4
