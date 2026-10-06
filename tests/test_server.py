import http.client
import json
from pathlib import Path

import pytest

from lectern import cache
from lectern.server.app import make_server


def request(server, path: str, method: str = "GET", headers: dict | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response, response.read().decode("utf-8", "replace")
    finally:
        connection.close()


def test_start_page_can_be_shown_without_the_server(server):
    response, body = request(server, "/")

    assert response.status == 200
    # Cached for long enough to still be there when the server is not.
    assert "max-age=31536000" in response.getheader("Cache-Control")
    assert 'id="offline"' in body and "Lectern is not running" in body
    # It must not depend on what is being served: it may be shown months later.
    assert "proj" not in body


def test_single_root_opens_on_its_listing(server):
    response, _ = request(server, "/_home")
    assert response.status == 302 and response.getheader("Location") == "/proj/"

    response, body = request(server, "/proj/")
    assert response.status == 200
    assert 'href="notebooks/sample.ipynb"' in body and "Sample notebook" in body
    assert 'href="docs/note.md"' in body
    # Hidden and build directories are not listed.
    assert "hidden.md" not in body and "dep.md" not in body


def test_notebook_page(server):
    response, body = request(server, "/proj/notebooks/sample.ipynb")

    assert response.status == 200
    assert "<title>Sample notebook</title>" in body
    assert "In [" not in body
    # Scripts are the reader's own files; nothing inline, nothing from the notebook.
    assert "<script>" not in body and body.count("<script") == body.count('<script src="/_static/')
    assert 'data-open="settings"' in body and 'id="toc"' in body
    assert '<a class="toc-2" href="#Part-2">Part</a>' in body
    assert 'name="apple-mobile-web-app-capable"' in body and 'rel="apple-touch-icon"' in body
    assert 'href="/proj/notebooks/"' in body
    assert "script-src 'self'" in response.getheader("Content-Security-Policy")


def test_math_typesetting_is_loaded_only_where_there_is_math(server, root: Path):
    _, with_math = request(server, "/proj/notebooks/sample.ipynb")
    _, without = request(server, "/proj/docs/note.md")

    assert "vendor/katex/katex.min.js" in with_math and "katex" not in without
    script = with_math.split('<script src="')[1].split('"')[0]
    assert request(server, script)[0].status == 200
    font = script.rsplit("/", 1)[0] + "/fonts/KaTeX_Main-Regular.woff2"
    response, _ = request(server, font)
    assert response.status == 200 and response.getheader("Content-Type") == "font/woff2"


def test_every_bundled_font_the_stylesheet_names_is_served(server):
    import re

    _, body = request(server, "/proj/")
    stylesheet = next(u for u in re.findall(r'href="([^"]+)"', body) if u.endswith("reader.css"))
    _, css = request(server, stylesheet)
    fonts = re.findall(r'url\("(fonts/[^"]+)"\)', css)
    assert len(fonts) == 9
    for font in fonts:
        assert request(server, stylesheet.rsplit("/", 1)[0] + "/" + font)[0].status == 200, font


def test_markdown_page_and_image(server):
    response, body = request(server, "/proj/docs/note.md")
    assert response.status == 200 and "<title>A note</title>" in body

    response, _ = request(server, "/proj/docs/pixel.png")
    assert response.status == 200 and response.getheader("Content-Type") == "image/png"


def test_directory_without_slash_redirects(server):
    response, _ = request(server, "/proj/docs")
    assert response.status == 302 and response.getheader("Location") == "/proj/docs/"


@pytest.mark.parametrize(
    "path",
    [
        "/proj/notebooks/sample.py",
        "/proj/.env",
        "/proj/data.csv",
        "/proj/.venv/hidden.md",
        "/proj/../outside.md",
        "/proj/%2e%2e/outside.md",
        "/proj/docs/%2e%2e%2f%2e%2e%2foutside.md",
        "/proj/escape.md",
        "/proj/missing.ipynb",
        "/other/",
        "/_static/x/../../cli.py",
    ],
)
def test_not_served(server, path: str):
    response, body = request(server, path)
    assert response.status == 404
    assert "SECRET" not in body and "outside" not in body


def test_unknown_host_is_refused(server):
    response, _ = request(server, "/proj/", headers={"Host": "evil.example"})
    assert response.status == 421

    for host in ("localhost:8642", "192.168.1.50:8642", "[::1]:8642"):
        response, _ = request(server, "/proj/", headers={"Host": host})
        assert response.status == 200, host


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_only_reading_is_allowed(server, method: str):
    response, _ = request(server, "/proj/notebooks/sample.ipynb", method=method)
    assert response.status == 405 and response.getheader("Allow") == "GET, HEAD"


def test_head_has_headers_and_no_body(server):
    response, body = request(server, "/proj/notebooks/sample.ipynb", method="HEAD")
    assert response.status == 200 and body == ""
    assert int(response.getheader("Content-Length")) > 0


def test_etag_gives_not_modified_until_the_file_changes(server, root: Path):
    path = "/proj/docs/note.md"
    response, _ = request(server, path)
    etag = response.getheader("ETag")
    assert etag

    response, body = request(server, path, headers={"If-None-Match": etag})
    assert response.status == 304 and body == ""

    (root / "docs" / "note.md").write_text("# A note, much revised\n")
    response, body = request(server, path, headers={"If-None-Match": etag})
    assert response.status == 200 and "much revised" in body


def test_half_saved_notebook(server, root: Path, monkeypatch):
    monkeypatch.setattr(cache, "RETRY_DELAY", 0)
    notebook = root / "notebooks" / "sample.ipynb"
    whole = notebook.read_text()
    path = "/proj/notebooks/sample.ipynb"

    # Never rendered: nothing to fall back on, so the page asks to be retried.
    notebook.write_text(whole[: len(whole) // 2])
    response, body = request(server, path)
    assert response.status == 503 and response.getheader("Retry-After") == "2"
    assert 'http-equiv="refresh"' in body

    notebook.write_text(whole)
    assert request(server, path)[0].status == 200

    # Rendered before: the last good version is shown, marked as such.
    notebook.write_text(whole[: len(whole) // 2])
    response, body = request(server, path)
    assert response.status == 200 and response.getheader("ETag") is None
    assert "Showing the last version" in body and "Sample notebook" in body


def test_static_assets_and_manifest(server):
    _, body = request(server, "/proj/")
    stylesheet = body.split('rel="stylesheet" href="')[1].split('"')[0]
    response, css = request(server, stylesheet)
    assert response.status == 200 and "--bg" in css
    assert "immutable" in response.getheader("Cache-Control")

    response, body = request(server, "/manifest.webmanifest")
    manifest = json.loads(body)
    assert manifest["display"] == "standalone"
    for icon in manifest["icons"]:
        assert request(server, icon["src"])[0].status == 200


def test_ping(server):
    _, body = request(server, "/_ping")
    ping = json.loads(body)
    assert ping["app"] == "lectern" and ping["roots"] == ["proj"] and ping["assets"]


def test_several_roots_get_a_front_page(root: Path, tmp_path: Path):
    import threading

    other = tmp_path / "other"
    other.mkdir()
    (other / "readme.md").write_text("# Other\n")
    server = make_server({"proj": root, "other": other}, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        response, body = request(server, "/_home")
        assert response.status == 200
        assert 'href="/proj/"' in body and 'href="/other/"' in body
        assert request(server, "/other/readme.md")[0].status == 200
    finally:
        server.shutdown()
        server.server_close()


def test_dropped_connection_prints_nothing(server, capsys):
    import socket
    import struct
    import time

    connection = socket.create_connection(("127.0.0.1", server.server_address[1]))
    connection.sendall(b"GET /proj/ HT")
    # Closing with a zero linger sends a reset, as a device does when it drops off Wi-Fi.
    connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    connection.close()
    time.sleep(0.3)

    assert request(server, "/_ping")[0].status == 200
    assert capsys.readouterr().err == ""


def test_saved_folders_are_followed_while_running(root: Path, tmp_path: Path):
    import threading
    import time

    from lectern import config

    settings = tmp_path / "settings" / "config.toml"
    server = make_server({}, host="127.0.0.1", port=0, settings=settings)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        # Nothing saved: the front page says so instead of failing.
        response, body = request(server, "/_home")
        assert response.status == 200 and "lectern add" in body
        assert request(server, "/proj/")[0].status == 404

        config.save(
            config.Config(roots={"proj": root}, extra_hosts=["mac.example.ts.net"]), settings
        )
        time.sleep(1.1)
        assert request(server, "/proj/notebooks/sample.ipynb")[0].status == 200
        assert request(server, "/proj/", headers={"Host": "mac.example.ts.net"})[0].status == 200

        # A file caught half-edited leaves things as they were.
        settings.write_text("[roots\n")
        time.sleep(1.1)
        assert request(server, "/proj/")[0].status == 200

        config.save(config.Config(), settings)
        time.sleep(1.1)
        assert request(server, "/proj/")[0].status == 404
    finally:
        server.shutdown()
        server.server_close()


def test_ping_tells_only_this_machine_where_folders_are(server, root: Path):
    _, body = request(server, "/_ping")
    ping = json.loads(body)
    assert ping["paths"] == {"proj": str(root)} and ping["saved"] is False

    # The same request as it looks arriving from another device.
    from lectern.server.app import ReaderHandler

    seen = {}
    original = ReaderHandler._send

    def as_remote(self, status, body, content_type, headers=None):
        seen["body"] = body
        original(self, status, body, content_type, headers)

    handler_address = (
        ReaderHandler.client_address if hasattr(ReaderHandler, "client_address") else None
    )
    try:
        ReaderHandler._send = as_remote
        ReaderHandler.client_address = property(
            lambda self: ("192.168.1.50", 50000), lambda self, v: None
        )
        request(server, "/_ping")
    finally:
        ReaderHandler._send = original
        del ReaderHandler.client_address
        if handler_address is not None:
            ReaderHandler.client_address = handler_address
    remote = json.loads(seen["body"])
    assert "paths" not in remote and remote["roots"] == ["proj"]
