"""The `lectern` command."""

import argparse
import errno
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from . import APP_NAME, __version__, config, library, netinfo


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _fail(message: object) -> int:
    print(f"{APP_NAME}: {message}", file=sys.stderr)
    return 1


def _address(port: int) -> str:
    return f"http://{netinfo.local_hostname()}.local:{port}/"


# ---- serve ----


def _roots(paths: list[str]) -> dict[str, Path]:
    """Each directory under its own name, which is the first segment of its URLs."""
    roots: dict[str, Path] = {}
    for given in paths or ["."]:
        path = Path(given).expanduser().resolve()
        if not path.is_dir():
            raise config.ConfigError(f"{given} is not a directory")
        name = config.root_name(path)
        if name in roots:
            raise config.ConfigError(
                f"{roots[name]} and {path} are both named {name}; serve one of them"
            )
        roots[name] = path
    return roots


def _summary(roots: dict[str, Path], port: int) -> str:
    serving = []
    for name, path in roots.items():
        notebooks, pages = library.count(path)
        serving.append(
            f"{name} ({_plural(notebooks, 'notebook')}, {_plural(pages, 'markdown file')})"
        )
    if not serving:
        lines = [f"{APP_NAME}  no folders saved yet: add one with `{APP_NAME} add PATH`"]
    elif len(serving) == 1:
        lines = [f"{APP_NAME}  serving {serving[0]}"]
    else:
        lines = [f"{APP_NAME}  serving", *(f"    {line}" for line in serving)]
    lines.append(f"  {_address(port)}")
    if ip := netinfo.lan_ip():
        lines.append(f"  {f'http://{ip}:{port}/':<34}(fallback)")
    return "\n".join(lines)


def _qr(url: str) -> None:
    """The address as a QR code in the terminal, for a device with a camera."""
    qrencode = shutil.which("qrencode")
    if not qrencode:
        print("  (no QR code: `qrencode` is not installed; `brew install qrencode`)")
        return
    sys.stdout.flush()
    subprocess.run([qrencode, "-t", "ANSIUTF8", "-m", "2", url], check=False)


def _running(port: int) -> dict | None:
    """What a lectern already answering on this Mac's port says about itself."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_ping", timeout=1) as response:
            ping = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return ping if isinstance(ping, dict) and ping.get("app") == APP_NAME else None


def _already_running(ping: dict, wanted: dict[str, Path] | None, port: int) -> int:
    """Instead of a second server: say where to read, or how to get a folder served."""
    served = {name: Path(path) for name, path in ping.get("paths", {}).items()}
    print(f"{APP_NAME}  already running on port {port}", end="")
    print(f", serving {', '.join(sorted(served))}" if served else ", serving nothing yet")
    missing = []
    for path in (wanted or {}).values():
        inside = next((n for n, root in served.items() if path.is_relative_to(root)), None)
        if inside is None:
            missing.append(path)
            continue
        rel = path.relative_to(served[inside]).as_posix()
        tail = "" if rel == "." else quote(rel) + "/"
        print(f"  {_address(port)}{quote(inside)}/{tail}")
    for path in missing:
        if ping.get("saved"):
            print(f"  {path} is not served. To add it: {APP_NAME} add {path}")
        else:
            print(f"  {path} is not served. Stop the running {APP_NAME}, or pass --port.")
    if wanted is None:
        print(f"  {_address(port)}")
    return 0


def _serve(args: argparse.Namespace) -> int:
    from .server.app import make_server

    saved = config.load()
    port = args.port or saved.port
    if args.all and args.paths:
        return _fail("give folders or --all, not both")
    roots = saved.roots if args.all else _roots(args.paths)

    if ping := _running(port):
        return _already_running(ping, None if args.all else roots, port)
    try:
        server = make_server(
            roots,
            args.host,
            port,
            tuple(saved.extra_hosts),
            verbose=args.verbose,
            settings=config.config_path() if args.all else None,
            # With --all the saved setting is followed while running; --no-notes overrules it.
            notes=not args.no_notes and (args.all or saved.notes),
        )
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        return _fail(f"port {port} is in use by something else. Stop it, or pass --port.")
    # The code first and the addresses after it, so they are what is left on the screen.
    if args.qr:
        _qr(_address(port))
    print(_summary(server.roots, port))
    print("  Ctrl-C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


def _notes(args: argparse.Namespace) -> int:
    from . import notes
    from .paths import DOC_SUFFIXES

    path = Path(args.path).expanduser()
    if path.is_dir():
        documents = [doc for doc in library.discover(path) if notes.notes_path(doc).exists()]
        if not documents:
            print(f"Nothing is marked under {path}.", file=sys.stderr)
            return 0
    elif path.is_file() and path.suffix.lower() in DOC_SUFFIXES:
        documents = [path]
    else:
        return _fail(f"{path} is not a notebook, a markdown file or a folder")
    print("\n".join(notes.to_markdown(doc) for doc in documents), end="")
    return 0


# ---- saved folders ----


def _print_roots(saved: config.Config) -> None:
    if not saved.roots:
        print("  no folders saved")
    width = max((len(name) for name in saved.roots), default=0)
    for name, path in sorted(saved.roots.items()):
        note = "" if path.is_dir() else "   (missing)"
        print(f"  {name:<{width}}  {path}{note}")


def _add(args: argparse.Namespace) -> int:
    saved, name = config.add_root(Path(args.path), args.name)
    print(f"{APP_NAME}  saved {name}. `{APP_NAME} serve --all` serves:")
    _print_roots(saved)
    ping = _running(saved.port)
    if ping and ping.get("saved"):
        print(f"  The running {APP_NAME} picks this up within a second:")
        print(f"  {_address(saved.port)}{quote(name)}/")
    return 0


def _remove(args: argparse.Namespace) -> int:
    saved = config.remove_root(args.name)
    print(f"{APP_NAME}  removed {args.name}. Still saved:")
    _print_roots(saved)
    return 0


def _list(args: argparse.Namespace) -> int:
    saved = config.load()
    print(f"{APP_NAME}  saved folders ({config.config_path()}):")
    _print_roots(saved)
    return 0


# ---- the login agent ----


def _agent(args: argparse.Namespace) -> int:
    from . import agent

    if args.action == "install":
        saved = config.load()
        path = agent.install(args.host)
        print(f"{APP_NAME}  starts at login from now on, serving the saved folders:")
        _print_roots(saved)
        print(f"  {_address(saved.port)}")
        print(f"  agent: {path}")
        print(f"  log:   {agent.log_path()}")
    elif args.action == "uninstall":
        removed = agent.uninstall()
        print(f"{APP_NAME}  " + ("no longer starts at login" if removed else "was not installed"))
    else:
        state = agent.status()
        saved = config.load()
        ping = _running(saved.port)
        print(f"{APP_NAME}  agent: {state}")
        answering = (
            f"answering, serving {', '.join(ping['roots']) or 'nothing yet'}" if ping else ""
        )
        print(f"  port {saved.port}: {answering or 'nothing answering'}")
    return 0


# ---- JupyterLab ----


def _lab(args: argparse.Namespace) -> int:
    from . import lab

    saved = config.load()
    directory = Path(args.dir).expanduser().resolve()
    argv = lab.command(directory, saved, args.port, args.host)
    port = args.port or saved.lab_port
    print(f"{APP_NAME}  JupyterLab for {directory.name}, behind Jupyter's password")
    print(f"  http://{netinfo.local_hostname()}.local:{port}/lab", flush=True)
    os.execv(argv[0], argv)


# ---- build ----


def _build(args: argparse.Namespace) -> int:
    from .build import build, load_options

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
    options = load_options(src, flags)
    built = build(src, Path(args.output).expanduser(), options, clean=args.clean)
    for line in built.skipped:
        print(f"{APP_NAME}: skipped {line}", file=sys.stderr)
    print(
        f"{APP_NAME}  built {_plural(built.notebooks, 'notebook')} and "
        f"{_plural(built.pages, 'markdown file')} into {args.output} ({built.size // 1024} KB)"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME, description="Read notebooks and markdown on a tablet."
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser(
        "serve",
        help="serve folders to read from another device",
        description="Serve the notebooks and markdown files under each PATH, read-only. "
        "If lectern is already running, say where to read instead of starting again.",
    )
    serve.add_argument("paths", nargs="*", metavar="PATH", help="default: the current directory")
    serve.add_argument("--all", action="store_true", help="serve the saved folders instead")
    serve.add_argument("--port", type=int, help=f"default: {config.DEFAULT_PORT}, or as saved")
    serve.add_argument("--host", default="0.0.0.0", help="address to listen on")
    serve.add_argument("--qr", action="store_true", help="also show the address as a QR code")
    serve.add_argument("--verbose", action="store_true", help="print each request")
    serve.add_argument(
        "--no-notes",
        action="store_true",
        help="read only: no highlights or notes, and nothing is written",
    )
    serve.set_defaults(run=_serve)

    add = commands.add_parser(
        "add",
        help="save a folder, to serve with `serve --all` or the login agent",
        description="Save a folder. A lectern running with --all, or from login, starts "
        "serving it within a second.",
    )
    add.add_argument("path", nargs="?", default=".", metavar="PATH", help="default: .")
    add.add_argument("--name", help="the name in its address; default: the folder's name")
    add.set_defaults(run=_add)

    remove = commands.add_parser("remove", help="forget a saved folder")
    remove.add_argument("name", metavar="NAME")
    remove.set_defaults(run=_remove)

    commands.add_parser("list", help="show the saved folders").set_defaults(run=_list)

    noted = commands.add_parser(
        "notes",
        help="print the highlights and notes made on a document, as markdown",
        description="Print what was marked while reading PATH: each passage under its "
        "heading and cell number, with the remark made on it. For a folder, every "
        "document in it that has notes.",
    )
    noted.add_argument("path", nargs="?", default=".", metavar="PATH", help="default: .")
    noted.set_defaults(run=_notes)

    agent = commands.add_parser(
        "agent",
        help="start lectern at login, serving the saved folders",
        description="Install, remove or check the launchd agent that runs "
        "`lectern serve --all` from login onwards.",
    )
    agent.add_argument("action", choices=["install", "uninstall", "status"])
    agent.add_argument("--host", help="address the agent listens on; default: all")
    agent.set_defaults(run=_agent)

    lab = commands.add_parser(
        "lab",
        help="run JupyterLab for a folder, behind its password",
        description="Start JupyterLab for DIR so a cell can be run from another device. "
        "Refuses unless Jupyter has a password set on this Mac.",
    )
    lab.add_argument("dir", nargs="?", default=".", metavar="DIR", help="default: .")
    lab.add_argument("--port", type=int, help=f"default: {config.DEFAULT_LAB_PORT}, or as saved")
    lab.add_argument("--host", default="0.0.0.0", help="address to listen on")
    lab.set_defaults(run=_lab)

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
    return parser


def main(argv: list[str] | None = None) -> int:
    from .agent import AgentError
    from .build import BuildError
    from .lab import LabError
    from .notes import NotesError

    args = _parser().parse_args(argv)
    try:
        return args.run(args)
    except (config.ConfigError, BuildError, AgentError, LabError, NotesError) as error:
        return _fail(error)
