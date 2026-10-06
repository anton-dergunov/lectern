"""The HTTP server: listings, rendered documents, images and assets. GET and HEAD only."""

import ipaddress
import json
import mimetypes
import sys
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from .. import APP_NAME, __version__, library, netinfo
from ..cache import RenderCache, RenderError
from ..paths import DOC_SUFFIXES, resolve
from ..render import render_document
from ..render.page import STATIC, THEME_COLOR, Crumb, asset_hash, render_page, static_url

DEFAULT_PORT = 8642

# No inline or third-party scripts, whatever a notebook's HTML output or markdown contains.
CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'"
)

CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
HTML = "text/html; charset=utf-8"


class ReaderServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        # A device that drops its connection (a tab closed, Wi-Fi asleep) is not news;
        # the default prints a traceback for it over the launch summary.
        if isinstance(sys.exception(), ConnectionError | TimeoutError) and not self.verbose:
            return
        super().handle_error(request, client_address)

    def __init__(
        self,
        address: tuple[str, int],
        roots: dict[str, Path],
        extra_hosts: tuple[str, ...] = (),
        verbose: bool = False,
    ) -> None:
        super().__init__(address, ReaderHandler)
        self.roots = roots
        self.cache = RenderCache(render_document)
        self.verbose = verbose
        self.hosts = {
            "localhost",
            f"{netinfo.local_hostname()}.local".lower(),
            *(host.lower() for host in extra_hosts),
        }


class ReaderHandler(BaseHTTPRequestHandler):
    server: ReaderServer
    server_version = f"{APP_NAME}/{__version__}"

    def do_GET(self) -> None:
        self._respond()

    def do_HEAD(self) -> None:
        self._respond()

    def _refuse(self) -> None:
        self._send(HTTPStatus.METHOD_NOT_ALLOWED, b"", "text/plain", {"Allow": "GET, HEAD"})

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _refuse

    def log_message(self, format: str, *args) -> None:
        if self.server.verbose:
            super().log_message(format, *args)

    # ---- Routing ----

    def _respond(self) -> None:
        try:
            self._route()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc(file=sys.stderr)
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Something went wrong rendering this.")

    def _route(self) -> None:
        if not self._host_allowed():
            self._send(HTTPStatus.MISDIRECTED_REQUEST, b"Unknown host\n", "text/plain")
            return
        raw = urlsplit(self.path).path
        path = unquote(raw)
        if path == "/_ping":
            ping = {
                "app": APP_NAME,
                "version": __version__,
                "roots": sorted(self.server.roots),
                "assets": asset_hash(),
            }
            headers = {"Cache-Control": "no-store"}
            self._send(HTTPStatus.OK, json.dumps(ping).encode(), "application/json", headers)
        elif path == "/manifest.webmanifest":
            self._send(HTTPStatus.OK, _manifest(), "application/manifest+json")
        elif path.startswith("/_static/"):
            self._static(path)
        elif path == "/":
            self._shell()
        elif path == "/_home":
            self._home()
        else:
            self._under_root(raw, path)

    def _host_allowed(self) -> bool:
        """Refuse requests addressed to a name that is not ours.

        A hostile web page can point its own domain at this machine and have the browser
        fetch from it (DNS rebinding); the Host header then carries that domain. An IP
        literal cannot be such a name, so any is accepted and DHCP changes need no handling.
        """
        host = self.headers.get("Host")
        if host is None:
            return True
        host = host.strip().lower()
        if host.startswith("["):
            host = host[1:].partition("]")[0]
        else:
            host = host.rsplit(":", 1)[0] if ":" in host else host
        if host in self.server.hosts:
            return True
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return False
        return True

    def _shell(self) -> None:
        """The start page, cacheable for a year so it opens even with the server stopped.

        It decides in the browser between going on to `/_home` and saying that lectern is
        not running, and refreshes its own cached copy when the assets have changed.
        """
        html = render_page("shell.html.j2", title="Lectern", assets=asset_hash())
        caching = {"Cache-Control": "public, max-age=31536000, immutable"}
        self._send(HTTPStatus.OK, html.encode(), HTML, caching)

    def _home(self) -> None:
        roots = self.server.roots
        if len(roots) == 1:
            self._redirect(f"/{quote(next(iter(roots)))}/")
            return
        links = [Crumb(name, f"/{quote(name)}/") for name in sorted(roots, key=str.lower)]
        html = render_page("listing.html.j2", title="Lectern", heading="Lectern", roots=links)
        self._send(HTTPStatus.OK, html.encode(), HTML)

    def _under_root(self, raw: str, path: str) -> None:
        root_name, _, rel = path.lstrip("/").partition("/")
        root = self.server.roots.get(root_name)
        target = resolve(root, rel) if root else None
        if target is None or not target.exists():
            self._not_found()
        elif target.is_dir():
            if not path.endswith("/"):
                self._redirect(raw + "/")
            else:
                self._listing(root_name, rel, target)
        elif path.endswith("/"):
            self._not_found()
        elif target.suffix.lower() in DOC_SUFFIXES:
            self._document(root_name, rel, target)
        else:
            self._image(target)

    # ---- Pages ----

    def _crumbs(self, root_name: str, parts: list[str]) -> list[Crumb]:
        """The root and each directory in `parts`, each linking to its listing."""
        crumbs = [Crumb("Lectern", "/_home")] if len(self.server.roots) > 1 else []
        href = f"/{quote(root_name)}/"
        crumbs.append(Crumb(root_name, href))
        for part in parts:
            href += quote(part) + "/"
            crumbs.append(Crumb(part, href))
        return crumbs

    def _listing(self, root_name: str, rel: str, target: Path) -> None:
        crumbs = self._crumbs(root_name, [p for p in rel.split("/") if p])
        html = render_page(
            "listing.html.j2",
            title=crumbs[-1].name,
            heading=crumbs[-1].name,
            crumbs=crumbs,
            back=crumbs[-2].href if len(crumbs) > 1 else None,
            listing=library.listing(target),
        )
        self._send(HTTPStatus.OK, html.encode(), HTML)

    def _document(self, root_name: str, rel: str, target: Path) -> None:
        try:
            hit = self.server.cache.get(target)
        except FileNotFoundError:
            self._not_found()
            return
        except RenderError as error:
            self._error(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "This file could not be read. If it is being saved, the page will retry by itself.",
                detail=str(error),
                retry=2,
            )
            return
        # The shell is part of the page, so a new stylesheet or template is a new version.
        etag = f'"{hit.etag}-{asset_hash()}"'
        headers = {"Cache-Control": "no-cache"}
        if not hit.stale:
            headers["ETag"] = etag
            if self.headers.get("If-None-Match") == etag:
                self._send(HTTPStatus.NOT_MODIFIED, b"", HTML, headers)
                return
        crumbs = self._crumbs(root_name, [p for p in rel.split("/") if p][:-1])
        html = render_page(
            "page.html.j2",
            title=hit.rendered.title,
            crumbs=crumbs,
            back=crumbs[-1].href,
            fragment=hit.rendered.fragment,
            toc=hit.rendered.toc,
            stale=hit.stale,
            path=f"{root_name}/{rel}",
            mtime=target.stat().st_mtime_ns,
        )
        self._send(HTTPStatus.OK, html.encode(), HTML, headers)

    def _image(self, target: Path) -> None:
        content_type = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(HTTPStatus.OK, target.read_bytes(), content_type, {"Cache-Control": "no-cache"})

    def _static(self, path: str) -> None:
        # /_static/<hash>/<file>: the hash only makes the URL change when the assets do.
        version, _, name = path.removeprefix("/_static/").partition("/")
        target = (STATIC / name).resolve()
        if not name or not target.is_relative_to(STATIC) or not target.is_file():
            self._not_found()
            return
        content_type = CONTENT_TYPES.get(
            target.suffix.lower(),
            mimetypes.guess_type(target.name)[0] or "application/octet-stream",
        )
        fresh = version == asset_hash()
        caching = "public, max-age=31536000, immutable" if fresh else "no-cache"
        self._send(HTTPStatus.OK, target.read_bytes(), content_type, {"Cache-Control": caching})

    def _not_found(self) -> None:
        self._error(HTTPStatus.NOT_FOUND, "There is nothing to read at this address.")

    def _error(self, status: HTTPStatus, message: str, detail: str = "", retry: int = 0) -> None:
        roots = self.server.roots
        html = render_page(
            "error.html.j2",
            title=status.phrase,
            heading=status.phrase,
            message=message,
            detail=detail,
            retry=retry,
            crumbs=[Crumb("Lectern", "/_home")]
            if len(roots) > 1
            else self._crumbs(next(iter(roots)), []),
        )
        headers = {"Retry-After": str(retry)} if retry else {}
        self._send(status, html.encode(), HTML, headers)

    # ---- Responses ----

    def _redirect(self, location: str) -> None:
        self._send(HTTPStatus.FOUND, b"", "text/plain", {"Location": location})

    def _send(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def _manifest() -> bytes:
    icons = f"{static_url()}/icons"
    manifest = {
        "name": "Lectern",
        "short_name": "Lectern",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": THEME_COLOR,
        "theme_color": THEME_COLOR,
        "icons": [
            {"src": f"{icons}/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": f"{icons}/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {
                "src": f"{icons}/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return json.dumps(manifest).encode()


def make_server(
    roots: dict[str, Path],
    host: str = "0.0.0.0",
    port: int = DEFAULT_PORT,
    extra_hosts: tuple[str, ...] = (),
    verbose: bool = False,
) -> ReaderServer:
    return ReaderServer((host, port), roots, extra_hosts, verbose)
