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

    args = parser.parse_args(argv)
    return args.run(args, parser)
