"""The HTTP server: listings, rendered documents, images and assets.

GET and HEAD only, but for one thing: a PUT that replaces the notes kept on a document.
"""

import ipaddress
import json
import mimetypes
import sys
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from .. import APP_NAME, __version__, config, library, netinfo, notes
from ..cache import RenderCache, RenderError
from ..config import DEFAULT_PORT
from ..paths import DOC_SUFFIXES, resolve
from ..render import render_document
from ..render.page import (
    CSP,
    STATIC,
    THEME_COLOR,
    Crumb,
    asset_hash,
    render_page,
    static_url,
)

CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
HTML = "text/html; charset=utf-8"
JSON = "application/json"
# The notes of one document, as sent: far more than a reader's remarks come to.
LARGEST_NOTES = 1024 * 1024

# What the "not running" page loads, for the service worker to keep with it.
OFFLINE_ASSETS = [
    "themes.css",
    "reader.css",
    "pygments.css",
    "boot.js",
    "reader.js",
    "icons/icon.svg",
    "fonts/charis-sil-400-normal.woff2",
    "fonts/charis-sil-700-normal.woff2",
    "fonts/inter-400-normal.woff2",
    "fonts/inter-600-normal.woff2",
]


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
        settings: Path | None = None,
        notes: bool = True,
    ) -> None:
        super().__init__(address, ReaderHandler)
        self.cache = RenderCache(render_document)
        self.verbose = verbose
        self._own_hosts = {"localhost", f"{netinfo.local_hostname()}.local".lower()}
        self._roots = roots
        # Whether marks may be kept at all, and whether they are now: with a settings
        # file, its `notes` is followed like the folders.
        self._notes_allowed = notes
        self._notes = notes
        self.hosts = self._own_hosts | {host.lower() for host in extra_hosts}
        # With a settings file, the saved folders are what is served, and the file is
        # read again whenever it changes: `lectern add` reaches a running server that way,
        # without the server accepting any request that changes something.
        self.settings = settings
        self._settings_stamp: float | None = None
        self._settings_checked = 0.0
        self._settings_lock = threading.Lock()

    @property
    def roots(self) -> dict[str, Path]:
        if self.settings is not None:
            self._follow_settings()
        return self._roots

    @property
    def notes(self) -> bool:
        if self.settings is not None:
            self._follow_settings()
        return self._notes

    def _follow_settings(self) -> None:
        with self._settings_lock:
            now = time.monotonic()
            if now - self._settings_checked < 1:
                return
            self._settings_checked = now
            try:
                stamp = self.settings.stat().st_mtime
            except OSError:
                stamp = 0.0
            if stamp == self._settings_stamp:
                return
            self._settings_stamp = stamp
            try:
                saved = config.load(self.settings)
            except config.ConfigError as error:
                # A half-edited file: keep serving what was being served.
                print(f"{APP_NAME}: {error}", file=sys.stderr, flush=True)
                return
            self._roots = {name: path for name, path in saved.roots.items() if path.is_dir()}
            self.hosts = self._own_hosts | {host.lower() for host in saved.extra_hosts}
            self._notes = self._notes_allowed and saved.notes


class ReaderHandler(BaseHTTPRequestHandler):
    server: ReaderServer
    server_version = f"{APP_NAME}/{__version__}"

    def do_GET(self) -> None:
        self._respond()

    def do_HEAD(self) -> None:
        self._respond()

    def do_PUT(self) -> None:
        # The one address that takes a write. Everywhere else PUT is refused like the rest.
        if urlsplit(self.path).path.startswith("/_notes/"):
            self._respond(self._put_notes)
        else:
            self._refuse()

    def _refuse(self) -> None:
        self._send(HTTPStatus.METHOD_NOT_ALLOWED, b"", "text/plain", {"Allow": "GET, HEAD"})

    do_POST = do_PATCH = do_DELETE = do_OPTIONS = _refuse

    def log_message(self, format: str, *args) -> None:
        if self.server.verbose:
            super().log_message(format, *args)

    # ---- Routing ----

    def _respond(self, route=None) -> None:
        try:
            (route or self._route)()
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
            # For `lectern serve` on this Mac, to say where a folder is already being
            # served. Other devices are not told where things are on the disk.
            if ipaddress.ip_address(self.client_address[0]).is_loopback:
                ping["paths"] = {name: str(path) for name, path in self.server.roots.items()}
                ping["saved"] = self.server.settings is not None
            self._json(HTTPStatus.OK, ping)
        elif path == "/manifest.webmanifest":
            self._send(HTTPStatus.OK, _manifest(), "application/manifest+json")
        elif path.startswith("/_static/"):
            self._static(path)
        elif path == "/":
            self._shell()
        elif path == "/_offline":
            self._shell(home="")
        elif path == "/_sw.js":
            self._service_worker()
        elif path == "/_home":
            self._home()
        elif path.startswith("/_notes/"):
            self._get_notes(path)
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

    def _shell(self, home: str = "/_home") -> None:
        """The start page, cacheable for a year so it opens even with the server stopped.

        It decides in the browser between going on to `/_home` and saying that lectern is
        not running, and refreshes its own cached copy when the assets have changed. With
        `home` empty it is the page the service worker keeps to show in place of any page
        that could not be loaded.
        """
        html = render_page("shell.html.j2", title="Lectern", assets=asset_hash(), home=home)
        caching = "public, max-age=31536000, immutable" if home else "no-cache"
        self._send(HTTPStatus.OK, html.encode(), HTML, {"Cache-Control": caching})

    def _service_worker(self) -> None:
        """`static/sw.js`, told which version it is and what the "not running" page needs."""
        needed = [f"{static_url()}/{name}" for name in OFFLINE_ASSETS]
        script = (STATIC / "sw.js").read_text(encoding="utf-8")
        script = script.replace("__VERSION__", asset_hash())
        script = script.replace("__ASSETS__", json.dumps(needed))
        # Always asked for afresh: this is how a browser learns that there is a new one.
        self._send(
            HTTPStatus.OK, script.encode(), CONTENT_TYPES[".js"], {"Cache-Control": "no-cache"}
        )

    def _home(self) -> None:
        roots = self.server.roots
        if len(roots) == 1:
            self._redirect(f"/{quote(next(iter(roots)))}/")
            return
        links = [Crumb(name, f"/{quote(name)}/") for name in sorted(roots, key=str.lower)]
        html = render_page(
            "listing.html.j2",
            title="Lectern",
            heading="Lectern",
            roots=links,
            crumbs=[Crumb("Lectern", "/_home")],
        )
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

    # ---- Notes ----

    def _noted(self, path: str) -> Path | None:
        """The served document that `/_notes/<root>/<path>` is about, if notes are kept."""
        if not self.server.notes:
            return None
        root_name, _, rel = path.removeprefix("/_notes/").partition("/")
        root = self.server.roots.get(root_name)
        target = resolve(root, rel) if root else None
        if target is None or not target.is_file() or target.suffix.lower() not in DOC_SUFFIXES:
            return None
        return target

    def _json(self, status: HTTPStatus, data: dict) -> None:
        self._send(status, json.dumps(data).encode(), JSON, {"Cache-Control": "no-store"})

    def _get_notes(self, path: str) -> None:
        doc = self._noted(path)
        if doc is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "no notes are kept here"})
            return
        try:
            self._json(HTTPStatus.OK, notes.load(doc))
        except notes.NotesError as error:
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})

    def _put_notes(self) -> None:
        """Replace one document's notes. The request says which document, never which file.

        There is no token, so what is asked of the sender is what a browser on one of
        lectern's own pages does and a page from elsewhere cannot: an Origin that is this
        server, and a JSON body, which a foreign page may not send without asking first
        (and the asking, OPTIONS, is refused).
        """
        # What was sent is taken off the wire before anything is said about it: an answer
        # given with the body unread can be lost to the sender.
        self.close_connection = True
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._json(HTTPStatus.LENGTH_REQUIRED, {"error": "no Content-Length"})
            return
        if not 0 <= length <= LARGEST_NOTES:
            unread = min(max(length, 0), 16 * LARGEST_NOTES)
            while unread > 0:
                unread -= len(self.rfile.read(min(unread, 65536))) or unread
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too many notes"})
            return
        body = self.rfile.read(length)
        if not self._host_allowed():
            self._send(HTTPStatus.MISDIRECTED_REQUEST, b"Unknown host\n", "text/plain")
            return
        doc = self._noted(unquote(urlsplit(self.path).path))
        if doc is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "no notes are kept here"})
            return
        origin = urlsplit(self.headers.get("Origin", "")).netloc.lower()
        if not origin or origin != self.headers.get("Host", "").strip().lower():
            self._json(HTTPStatus.FORBIDDEN, {"error": "not from one of lectern's own pages"})
            return
        if self.headers.get_content_type() != JSON:
            self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "notes are sent as JSON"})
            return
        try:
            sent = json.loads(body)
            kept = notes.save(doc, sent["notes"], sent["rev"])
        except notes.Stale as stale:
            self._json(HTTPStatus.CONFLICT, stale.current)
        except (ValueError, KeyError, TypeError, notes.NotesError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        else:
            self._json(HTTPStatus.OK, kept)

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
            listing=library.listing(target, root=self.server.roots.get(root_name)),
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
            here=target.name,
            back=crumbs[-1].href,
            fragment=hit.rendered.fragment,
            toc=hit.rendered.toc,
            math=hit.rendered.has_math,
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
            crumbs=self._crumbs(next(iter(roots)), [])
            if len(roots) == 1
            else [Crumb("Lectern", "/_home")],
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
        # How the service worker tells lectern's own error pages from a proxy's.
        self.send_header("X-Lectern", __version__)
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
    settings: Path | None = None,
    notes: bool = True,
) -> ReaderServer:
    """`settings` is the file of saved folders to serve and keep following; `roots` is
    then only what is served until it has been read. `notes` false keeps the server to
    reading: no marks are handed out or taken."""
    return ReaderServer((host, port), roots, extra_hosts, verbose, settings, notes)
