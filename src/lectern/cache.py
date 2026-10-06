"""Rendered documents kept in memory, re-rendered when the file on disk changes."""

import hashlib
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .render import RENDER_VERSION, Rendered

# Jupyter rewrites a notebook in place, so a read can land on half a file.
RETRY_DELAY = 0.15

Stamp = tuple[int, int, int]


class RenderError(Exception):
    """The file could not be rendered and there is no earlier render to fall back on."""


@dataclass(frozen=True)
class Hit:
    rendered: Rendered
    etag: str
    # True when the file no longer renders and this is the last version that did.
    stale: bool = False


class RenderCache:
    def __init__(self, render: Callable[[Path], Rendered], size: int = 64) -> None:
        self._render = render
        self._size = size
        self._entries: OrderedDict[str, tuple[Stamp, Rendered]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, path: Path) -> Hit:
        """The render of `path`. Raises FileNotFoundError, or RenderError with no fallback."""
        real = os.path.realpath(path)
        error: Exception | None = None
        for attempt in range(2):
            stat = os.stat(real)
            stamp = (stat.st_mtime_ns, stat.st_size, RENDER_VERSION)
            with self._lock:
                entry = self._entries.get(real)
                if entry and entry[0] == stamp:
                    self._entries.move_to_end(real)
                    return Hit(entry[1], _etag(real, stamp))
            try:
                rendered = self._render(Path(real))
            except Exception as exc:  # anything a half-written or malformed file can raise
                error = exc
                if attempt == 0:
                    time.sleep(RETRY_DELAY)
                continue
            with self._lock:
                self._entries[real] = (stamp, rendered)
                self._entries.move_to_end(real)
                while len(self._entries) > self._size:
                    self._entries.popitem(last=False)
            return Hit(rendered, _etag(real, stamp))

        if entry:
            return Hit(entry[1], _etag(real, entry[0]), stale=True)
        raise RenderError(f"{type(error).__name__}: {error}") from error


def _etag(real: str, stamp: Stamp) -> str:
    return hashlib.sha1(repr((real, stamp)).encode()).hexdigest()[:16]
