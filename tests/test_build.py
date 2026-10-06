import html
from pathlib import Path

import pytest
from nbformat import v4

from lectern.build import BuildError, SiteOptions, build, load_options
from lectern.cli import main

from .conftest import write_notebook


@pytest.fixture
def src(tmp_path: Path) -> Path:
    """A repository: a notebook that links around, one two directories down, and markdown
    that is and is not linked from a notebook."""
    src = tmp_path / "repo"
    write_notebook(
        src / "study" / "first.ipynb",
        [
            v4.new_markdown_cell(
                "# First study\n\nThe opening paragraph.\n\n"
                "[script](first.py) [deep](a/b/deep.ipynb#part) [notes](../docs/notes.md) "
                "[data](../data.csv) [gone](missing.md) [site](https://example.com)"
            )
        ],
    )
    (src / "study" / "first.py").write_text("x = 1\n")
    write_notebook(src / "study" / "a" / "b" / "deep.ipynb", [v4.new_markdown_cell("# Deep")])
    (src / "docs").mkdir()
    (src / "docs" / "notes.md").write_text("# Notes\n\n![dot](dot.png) [more](more.md)\n")
    (src / "docs" / "more.md").write_text("# More\n")
    (src / "docs" / "dot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (src / "README.md").write_text("# Readme, not for the site\n")
    (src / "data.csv").write_text("a,b\n")
    return src


def options(**kw) -> SiteOptions:
    return SiteOptions(title="Studies", **kw)


def files(out: Path) -> set[str]:
    return {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}


def test_output_tree(src: Path, tmp_path: Path):
    out = tmp_path / "site"
    built = build(src, out, options())

    written = files(out)
    assert {
        "index.html",
        ".nojekyll",
        "study/first.html",
        "study/a/b/deep.html",
        # Reached from the notebook, directly and through another page.
        "docs/notes.html",
        "docs/more.html",
        # Used by a built page.
        "docs/dot.png",
        "_static/reader.css",
        "_static/reader.js",
        "_static/icons/icon.svg",
    } <= written
    # Markdown nothing links to stays out, and so does everything that is not a document.
    assert not {"README.html", "data.csv", "study/first.py"} & written
    assert (built.notebooks, built.pages, built.skipped) == (2, 2, [])


def test_assets_are_linked_relative_to_each_page(src: Path, tmp_path: Path):
    out = tmp_path / "site"
    build(src, out, options())

    assert 'href="_static/reader.css?v=' in (out / "index.html").read_text()
    assert 'href="../_static/reader.css?v=' in (out / "study/first.html").read_text()
    deep = (out / "study/a/b/deep.html").read_text()
    assert 'src="../../../_static/reader.js?v=' in deep
    assert 'href="../../../index.html"' in deep
    for page in out.rglob("*.html"):
        assert '"/_static' not in page.read_text(), page


def test_pages_stand_alone_without_a_server(src: Path, tmp_path: Path):
    out = tmp_path / "site"
    build(src, out, options())
    page = html.unescape((out / "study/first.html").read_text())

    assert "<html" in page and " data-static" in page
    assert 'http-equiv="Content-Security-Policy"' in page and "script-src 'self'" in page
    assert "manifest.webmanifest" not in page
    assert "<title>First study</title>" in page


def test_links_follow_the_documents_to_their_pages(src: Path, tmp_path: Path):
    out = tmp_path / "site"
    build(src, out, options(repo_url="https://github.com/me/repo", branch="trunk"))
    page = (out / "study/first.html").read_text()

    # The paired script is the notebook itself; other documents keep their relative place.
    assert '<a href="first.html">script</a>' in page
    assert '<a href="a/b/deep.html#part">deep</a>' in page
    assert '<a href="../docs/notes.html">notes</a>' in page
    # A file that is in the repository but not on the site.
    assert 'href="https://github.com/me/repo/blob/trunk/data.csv"' in page
    assert '<a href="missing.md">gone</a>' in page
    assert 'href="https://example.com"' in page
    assert '<a href="more.html">more</a>' in (out / "docs/notes.html").read_text()


def test_index_lists_the_documents(src: Path, tmp_path: Path):
    out = tmp_path / "site"
    site = options(description="What this is.", repo_url="https://github.com/me/repo")
    build(src, out, site)
    index = (out / "index.html").read_text()

    assert "<h1>Studies</h1>" in index and "What this is." in index
    assert 'href="study/first.html"' in index and "The opening paragraph." in index
    assert 'href="https://github.com/me/repo/blob/main/study/first.ipynb"' in index
    assert 'href="docs/notes.html"' in index
    # No directory pages exist to link to, and a checkout's file dates mean nothing.
    assert 'href="study/"' not in index and "Recently changed" not in index


def test_markdown_all_and_none(src: Path, tmp_path: Path):
    build(src, tmp_path / "all", options(markdown="all"))
    build(src, tmp_path / "none", options(markdown="none"))

    assert "README.html" in files(tmp_path / "all")
    assert not [name for name in files(tmp_path / "none") if name.startswith("docs/")]


def test_include_and_exclude(src: Path, tmp_path: Path):
    build(src, tmp_path / "ex", options(exclude=["study/a/*"]))
    build(src, tmp_path / "in", options(include=["study/a/*"]))

    assert "study/a/b/deep.html" not in files(tmp_path / "ex")
    pages = {name for name in files(tmp_path / "in") if not name.startswith("_static/")}
    assert pages == {"index.html", ".nojekyll", "study/a/b/deep.html"}


def test_output_inside_the_source_is_not_built_into_itself(src: Path):
    out = src / "public"
    build(src, out, options(markdown="all"))
    (out / "stray.md").write_text("# Stray\n")
    build(src, out, options(markdown="all"))

    assert not (out / "public").exists() and "stray.html" not in files(out)


def test_clean_only_empties_a_directory_it_built(src: Path, tmp_path: Path):
    mine = tmp_path / "site"
    build(src, mine, options())
    (mine / "old.html").write_text("left over")
    build(src, mine, options(), clean=True)
    assert not (mine / "old.html").exists() and (mine / "index.html").exists()

    theirs = tmp_path / "documents"
    theirs.mkdir()
    (theirs / "thesis.txt").write_text("irreplaceable")
    with pytest.raises(BuildError, match="not emptying"):
        build(src, theirs, options(), clean=True)
    assert (theirs / "thesis.txt").exists()

    with pytest.raises(BuildError, match="overwrite the source"):
        build(src, src, options())


def test_two_documents_for_one_page(src: Path, tmp_path: Path):
    (src / "study" / "first.md").write_text("# The same name\n")
    (src / "index.md").write_text("# Would be the index\n")
    built = build(src, tmp_path / "site", options(markdown="all"))

    assert "<title>First study</title>" in (tmp_path / "site/study/first.html").read_text()
    assert sorted(line.split(":")[0] for line in built.skipped) == ["index.md", "study/first.md"]


def test_options_come_from_flags_then_the_file_then_the_environment(src: Path):
    environ = {"GITHUB_REPOSITORY": "me/from-env", "GITHUB_REF_NAME": "release"}

    bare = load_options(src, {}, {})
    assert (bare.title, bare.repo_url, bare.branch, bare.theme) == ("repo", "", "main", "solarized")

    from_env = load_options(src, {}, environ)
    assert (from_env.repo_url, from_env.branch) == ("https://github.com/me/from-env", "release")

    (src / "lectern.toml").write_text(
        'title = "From the file"\ndescription = "Described."\nexclude = ["tools/*"]\n'
        'repo_url = "https://github.com/me/from-file/"\ntheme = "plain"\n'
    )
    from_file = load_options(src, {}, environ)
    assert from_file.title == "From the file" and from_file.description == "Described."
    assert from_file.repo_url == "https://github.com/me/from-file"
    assert (from_file.exclude, from_file.theme, from_file.branch) == (
        ["tools/*"],
        "plain",
        "release",
    )

    flagged = load_options(
        src, {"title": "From the flag", "branch": "dev", "exclude": None}, environ
    )
    assert (flagged.title, flagged.branch, flagged.exclude) == ("From the flag", "dev", ["tools/*"])


def test_bad_settings_are_explained(src: Path):
    (src / "lectern.toml").write_text('titel = "typo"\n')
    with pytest.raises(BuildError, match="unknown setting titel"):
        load_options(src, {}, {})

    (src / "lectern.toml").write_text('theme = "neon"\n')
    with pytest.raises(BuildError, match="theme must be one of"):
        load_options(src, {}, {})


def test_command_line(src: Path, tmp_path: Path, capsys):
    out = tmp_path / "site"
    assert main(["build", str(src), "-o", str(out), "--title", "Shown", "--markdown", "none"]) == 0
    assert "<h1>Shown</h1>" in (out / "index.html").read_text()
    assert "built 2 notebooks and 0 markdown files" in capsys.readouterr().out

    assert main(["build", str(src), "-o", str(src)]) == 1
    assert "overwrite the source" in capsys.readouterr().err
