"""A static copy of the reader: the same pages, written to a directory to publish."""

import os
import shutil
import tomllib
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from . import library
from .paths import IMAGE_SUFFIXES
from .render import Rendered, render_document
from .render.page import CSP, STATIC, Crumb, asset_hash, render_page

CONFIG_NAME = "lectern.toml"
FAMILIES = ("solarized", "plain", "eink")
MARKDOWN = ("linked", "all", "none")


class BuildError(Exception):
    """Something about the request that the person running the build has to fix."""


@dataclass
class SiteOptions:
    title: str
    description: str = ""
    # With these, the index links each notebook's source, and links to files that are not
    # part of the site (scripts, data) go to the repository instead of nowhere.
    repo_url: str = ""
    branch: str = "main"
    theme: str = "solarized"
    # Which markdown files become pages: those a built page links to, every one, or none.
    # A repository's markdown is mostly not written for the site's readers (README, notes
    # for tools), so publishing all of it has to be asked for.
    markdown: str = "linked"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


@dataclass
class Built:
    notebooks: int
    pages: int
    skipped: list[str]
    size: int


def load_options(src: Path, flags: dict, environ: dict[str, str] | None = None) -> SiteOptions:
    """Each value from the command line, else `lectern.toml` in the source directory, else
    the GitHub Actions environment, else a default."""
    environ = os.environ if environ is None else environ
    config: dict = {}
    config_path = src / CONFIG_NAME
    if config_path.is_file():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise BuildError(f"{config_path}: {error}") from error
        known = set(SiteOptions.__dataclass_fields__)
        if unknown := sorted(set(config) - known):
            raise BuildError(
                f"{config_path}: unknown setting {', '.join(unknown)} "
                f"(known: {', '.join(sorted(known))})"
            )

    def pick(name: str, fallback):
        if flags.get(name):
            return flags[name]
        return config.get(name) or fallback

    repository = environ.get("GITHUB_REPOSITORY", "")
    options = SiteOptions(
        title=pick("title", src.name),
        description=pick("description", ""),
        repo_url=pick("repo_url", f"https://github.com/{repository}" if repository else ""),
        branch=pick("branch", environ.get("GITHUB_REF_NAME") or "main"),
        theme=pick("theme", "solarized"),
        markdown=pick("markdown", "linked"),
        include=list(pick("include", [])),
        exclude=list(pick("exclude", [])),
    )
    options.repo_url = options.repo_url.rstrip("/")
    if options.theme not in FAMILIES:
        raise BuildError(f"theme must be one of {', '.join(FAMILIES)}, not {options.theme!r}")
    if options.markdown not in MARKDOWN:
        raise BuildError(f"markdown must be one of {', '.join(MARKDOWN)}, not {options.markdown!r}")
    return options


def _selected(rel: str, options: SiteOptions) -> bool:
    # fnmatch's * crosses directory separators, so `tools/*` covers everything under tools.
    if options.include and not any(fnmatch(rel, pattern) for pattern in options.include):
        return False
    return not any(fnmatch(rel, pattern) for pattern in options.exclude)


def _prepare_output(out: Path, src: Path, clean: bool) -> None:
    if out == src or src.is_relative_to(out):
        raise BuildError(f"the output directory {out} would overwrite the source")
    if clean and out.exists() and any(out.iterdir()):
        # Only ever empty a directory that an earlier build filled.
        if not (out / "_static" / "reader.css").is_file():
            raise BuildError(f"not emptying {out}: it was not written by lectern build")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)


def _html_name(rel: PurePosixPath) -> PurePosixPath:
    return rel.with_suffix(".html")


def _target(rel: PurePosixPath, reference: str) -> PurePosixPath | None:
    """The source-relative path that a relative URL in the document `rel` names, or None
    if it leaves the source directory."""
    resolved = os.path.normpath((rel.parent / unquote(reference)).as_posix())
    return None if resolved.startswith("..") else PurePosixPath(resolved)


def _relative_links(soup: BeautifulSoup, tag: str, attribute: str):
    for element in soup.find_all(tag, **{attribute: True}):
        parts = urlsplit(element[attribute])
        if parts.scheme or parts.netloc or not parts.path or parts.path.startswith("/"):
            continue
        yield element, parts


def _linked_markdown(fragment: str, rel: PurePosixPath) -> list[PurePosixPath]:
    soup = BeautifulSoup(fragment, "html.parser")
    targets = (_target(rel, parts.path) for _, parts in _relative_links(soup, "a", "href"))
    return [t for t in targets if t is not None and t.suffix.lower() == ".md"]


def _localise(
    fragment: str, rel: PurePosixPath, src: Path, built: set[PurePosixPath], options: SiteOptions
) -> tuple[str, list[PurePosixPath]]:
    """Point the fragment's relative links at the built pages, and list the images it uses.

    The output tree mirrors the source tree, so a link to a built document only needs its
    extension changed. A link to any other file in the source goes to the repository when
    one is known.
    """
    soup = BeautifulSoup(fragment, "html.parser")
    for a, parts in _relative_links(soup, "a", "href"):
        linked = _target(rel, parts.path)
        if linked is None:
            continue
        if linked in built:
            page = str(PurePosixPath(parts.path).with_suffix(".html"))
            a["href"] = urlunsplit(parts._replace(path=page))
        elif options.repo_url and (src / linked).is_file():
            a["href"] = f"{options.repo_url}/blob/{quote(options.branch)}/{quote(str(linked))}"
            a["target"] = "_blank"
            a["rel"] = "noopener"

    images = []
    for _, parts in _relative_links(soup, "img", "src"):
        linked = _target(rel, parts.path)
        if linked and linked.suffix.lower() in IMAGE_SUFFIXES and (src / linked).is_file():
            images.append(linked)
    return str(soup), images


def _choose(src: Path, out: Path, options: SiteOptions) -> tuple[dict, list[str]]:
    """The documents to build, each with its render, and those left out with the reason."""
    candidates: dict[PurePosixPath, Path] = {}
    for path in library.discover(src):
        rel = PurePosixPath(path.relative_to(src).as_posix())
        if not path.is_relative_to(out) and _selected(str(rel), options):
            candidates[rel] = path

    chosen: dict[PurePosixPath, Rendered] = {}
    taken: dict[PurePosixPath, str] = {PurePosixPath("index.html"): "the index"}
    skipped: list[str] = []

    def add(rel: PurePosixPath) -> None:
        page = _html_name(rel)
        if page in taken:
            skipped.append(f"{rel}: would be written over {taken[page]} as {page}")
            return
        taken[page] = str(rel)
        chosen[rel] = render_document(candidates[rel])

    # Notebooks first, so that of `x.ipynb` and `x.md` the notebook gets `x.html`.
    for rel in sorted(candidates):
        if rel.suffix.lower() == ".ipynb":
            add(rel)
    pages = sorted(rel for rel in candidates if rel.suffix.lower() == ".md")
    if options.markdown == "all":
        for rel in pages:
            add(rel)
    elif options.markdown == "linked":
        # Follow links outwards from the notebooks, through the markdown they reach.
        queue = list(chosen)
        while queue:
            rel = queue.pop()
            for linked in _linked_markdown(chosen[rel].fragment, rel):
                if (
                    linked in candidates
                    and linked not in chosen
                    and _html_name(linked) not in taken
                ):
                    add(linked)
                    queue.append(linked)
    return {rel: (candidates[rel], chosen[rel]) for rel in sorted(chosen)}, skipped


def build(src: Path, out: Path, options: SiteOptions, clean: bool = False) -> Built:
    src, out = src.resolve(), out.resolve()
    if not src.is_dir():
        raise BuildError(f"{src} is not a directory")
    _prepare_output(out, src, clean)

    documents, skipped = _choose(src, out, options)
    built = set(documents)
    version = f"?v={asset_hash()}"
    for rel, (path, rendered) in documents.items():
        fragment, images = _localise(rendered.fragment, rel, src, built, options)
        up = "../" * (len(rel.parts) - 1)
        html = render_page(
            "page.html.j2",
            static=f"{up}_static",
            version=version,
            static_site=True,
            csp=CSP,
            default_family=options.theme,
            title=rendered.title,
            crumbs=[Crumb(options.title, f"{up}index.html")],
            back=f"{up}index.html",
            fragment=fragment,
            toc=rendered.toc,
            math=rendered.has_math,
            path=str(rel),
            mtime=path.stat().st_mtime_ns,
        )
        target = out / _html_name(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        for image in images:
            copy = out / image
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / image, copy)

    paths = [path for path, _ in documents.values()]
    listing = library.listing(src, paths, href=lambda rel: quote(str(_html_name(rel))))
    # In a checkout every file is as new as every other, so "recently changed" says nothing.
    listing.recent = []
    index = render_page(
        "listing.html.j2",
        static="_static",
        version=version,
        static_site=True,
        csp=CSP,
        default_family=options.theme,
        title=options.title,
        heading=options.title,
        description=options.description,
        source=f"{options.repo_url}/blob/{quote(options.branch)}" if options.repo_url else "",
        crumbs=[Crumb(options.title, "index.html")],
        listing=listing,
    )
    (out / "index.html").write_text(index, encoding="utf-8")

    # KaTeX is most of the assets' weight; a site with no math does not carry it.
    has_math = any(rendered.has_math for _, rendered in documents.values())
    unused = () if has_math else ("katex",)
    shutil.copytree(
        STATIC, out / "_static", dirs_exist_ok=True, ignore=shutil.ignore_patterns(*unused)
    )
    # GitHub Pages runs Jekyll by default, and Jekyll drops directories starting with "_".
    (out / ".nojekyll").touch()

    notebooks = sum(1 for rel in documents if rel.suffix.lower() == ".ipynb")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    return Built(notebooks, len(documents) - notebooks, skipped, size)
