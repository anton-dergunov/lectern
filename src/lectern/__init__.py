"""A read-only reader for Jupyter notebooks and markdown, built for tablets."""

from importlib.metadata import PackageNotFoundError, version

APP_NAME = "lectern"

try:
    __version__ = version(APP_NAME)
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"
