"""The `lectern` command."""

import argparse
import errno
import sys
from pathlib import Path

from . import APP_NAME, __version__, library, netinfo


def _roots(paths: list[str], parser: argparse.ArgumentParser) -> dict[str, Path]:
    """Each directory under its own name, which is the first segment of its URLs."""
    roots: dict[str, Path] = {}
    for given in paths or ["."]:
        path = Path(given).expanduser().resolve()
        if not path.is_dir():
            parser.error(f"{given} is not a directory")
        name = path.name
        if not name or name.startswith((".", "_")):
            parser.error(f"cannot serve {path}: its name must not be empty or start with . or _")
        if name in roots:
            parser.error(f"{roots[name]} and {path} are both named {name}; serve one of them")
        roots[name] = path
    return roots


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _summary(roots: dict[str, Path], port: int) -> str:
    serving = []
    for name, path in roots.items():
        notebooks, pages = library.count(path)
        serving.append(
            f"{name} ({_plural(notebooks, 'notebook')}, {_plural(pages, 'markdown file')})"
        )
    lines = [f"{APP_NAME}  serving {', '.join(serving)}"]
    lines.append(f"  http://{netinfo.local_hostname()}.local:{port}/")
    if ip := netinfo.lan_ip():
        lines.append(f"  {f'http://{ip}:{port}/':<34}(fallback)")
    return "\n".join(lines)


def _serve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    from .server.app import make_server

    roots = _roots(args.paths, parser)
    try:
        server = make_server(roots, args.host, args.port, verbose=args.verbose)
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        print(
            f"{APP_NAME}: port {args.port} is already in use. Is lectern running in another "
            "terminal? Stop it, or pass --port.",
            file=sys.stderr,
        )
        return 1
    print(_summary(roots, args.port))
    print("  Ctrl-C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


def _build(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    from .build import BuildError, build, load_options

    src = Path(args.src).expanduser().resolve()
    flags = {
        name: getattr(args, name)
        for name in (
            "title",
            "description",
            "repo_url",
            "branch",
            "theme",
            "markdown",
            "include",
            "exclude",
        )
    }
    try:
        options = load_options(src, flags)
        built = build(src, Path(args.output).expanduser(), options, clean=args.clean)
    except BuildError as error:
        print(f"{APP_NAME}: {error}", file=sys.stderr)
        return 1
    for line in built.skipped:
        print(f"{APP_NAME}: skipped {line}", file=sys.stderr)
    print(
        f"{APP_NAME}  built {_plural(built.notebooks, 'notebook')} and "
        f"{_plural(built.pages, 'markdown file')} into {args.output} ({built.size // 1024} KB)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    from .server.app import DEFAULT_PORT

    parser = argparse.ArgumentParser(
        prog=APP_NAME, description="Read notebooks and markdown on a tablet."
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser(
        "serve",
        help="serve directories to read from another device",
        description="Serve the notebooks and markdown files under each PATH, read-only.",
    )
    serve.add_argument("paths", nargs="*", metavar="PATH", help="default: the current directory")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT, help="default: %(default)s")
    serve.add_argument("--host", default="0.0.0.0", help="address to listen on")
    serve.add_argument("--verbose", action="store_true", help="print each request")
    serve.set_defaults(run=_serve)

    build = commands.add_parser(
        "build",
        help="write the pages to a directory, to publish as a static site",
        description="Render the notebooks and markdown files under SRC into a directory "
        "that any static host can serve. Settings not given here are read from "
        "lectern.toml in SRC, then from the GitHub Actions environment.",
    )
    build.add_argument("src", nargs="?", default=".", metavar="SRC", help="default: .")
    build.add_argument("-o", "--output", default="_site", help="default: %(default)s")
    build.add_argument("--title", help="site title; default: the directory's name")
    build.add_argument("--description", help="a sentence or two under the title")
    build.add_argument("--repo-url", help="repository to link each notebook's source in")
    build.add_argument("--branch", help="branch those links point at; default: main")
    build.add_argument("--theme", choices=["solarized", "plain", "eink"], help="opening colours")
    build.add_argument(
        "--markdown",
        choices=["linked", "all", "none"],
        help="which markdown files become pages; default: those a notebook links to",
    )
    build.add_argument("--include", action="append", metavar="GLOB", help="only these paths")
    build.add_argument("--exclude", action="append", metavar="GLOB", help="leave these out")
    build.add_argument("--clean", action="store_true", help="empty the output directory first")
    build.set_defaults(run=_build)

    args = parser.parse_args(argv)
    return args.run(args, parser)
