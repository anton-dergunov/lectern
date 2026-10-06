"""A lectern server on this machine only, for the browser scripts in this directory."""

import threading
from pathlib import Path

from lectern.server.app import ReaderServer, make_server

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures"


class LocalServer:
    """Serves `root` on 127.0.0.1. `stop()` and `start()` keep the same port, so a page
    that was open before a stop finds the server again after a start."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.name = self.root.name
        self.port = 0
        self._server: ReaderServer | None = None

    def start(self) -> None:
        self._server = make_server({self.name: self.root}, host="127.0.0.1", port=self.port)
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def url(self, rel: str = "") -> str:
        return f"{self.origin}/{self.name}/{rel}"

    def __enter__(self) -> "LocalServer":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
