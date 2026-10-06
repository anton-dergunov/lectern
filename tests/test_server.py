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


def test_single_root_opens_on_its_listing(server):
    response, _ = request(server, "/")
    assert response.status == 302 and response.getheader("Location") == "/proj/"

    response, body = request(server, "/proj/")
    assert response.status == 200
    assert 'href="notebooks/sample.ipynb"' in body and "Sample notebook" in body
    assert 'href="docs/note.md"' in body
    # Hidden and build directories are not listed.
    assert "hidden" not in body and "dep.md" not in body


def test_notebook_page(server):
    response, body = request(server, "/proj/notebooks/sample.ipynb")

    assert response.status == 200
    assert "<title>Sample notebook</title>" in body
    assert "In [" not in body and "<script" not in body
    assert 'name="apple-mobile-web-app-capable"' in body and 'rel="apple-touch-icon"' in body
    assert 'href="/proj/notebooks/"' in body
    assert "script-src 'self'" in response.getheader("Content-Security-Policy")


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
    assert json.loads(body)["app"] == "lectern" and json.loads(body)["roots"] == ["proj"]


def test_several_roots_get_a_front_page(root: Path, tmp_path: Path):
    import threading

    other = tmp_path / "other"
    other.mkdir()
    (other / "readme.md").write_text("# Other\n")
    server = make_server({"proj": root, "other": other}, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        response, body = request(server, "/")
        assert response.status == 200
        assert 'href="/proj/"' in body and 'href="/other/"' in body
        assert request(server, "/other/readme.md")[0].status == 200
    finally:
        server.shutdown()
        server.server_close()
