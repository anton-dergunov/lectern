"""JupyterLab for the rare time a cell has to be run from the tablet.

Unlike the reader, Lab runs code, so it is never started open: it keeps the password
already set for Jupyter on this Mac, typed once per device.
"""

import json
import shutil
from pathlib import Path

from . import netinfo
from .config import Config

JUPYTER_CONFIG = Path.home() / ".jupyter" / "jupyter_server_config.json"


class LabError(Exception):
    pass


def has_password(config_file: Path = JUPYTER_CONFIG) -> bool:
    try:
        settings = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for section in ("IdentityProvider", "PasswordIdentityProvider", "ServerApp"):
        values = settings.get(section, {})
        if values.get("hashed_password") or values.get("password"):
            return True
    return False


def find_jupyter_lab(directory: Path, config: Config) -> str:
    """The folder's own environment first: that is where its kernel and packages are."""
    candidates = [
        directory / ".venv" / "bin" / "jupyter-lab",
        directory / "notebooks" / ".venv" / "bin" / "jupyter-lab",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    if config.lab_command:
        return str(Path(config.lab_command).expanduser())
    if found := shutil.which("jupyter-lab"):
        return found
    raise LabError(
        "cannot find jupyter-lab: install JupyterLab in this folder's .venv, or set "
        "lab_command in the lectern settings"
    )


def command(
    directory: Path,
    config: Config,
    port: int | None = None,
    host: str = "0.0.0.0",
    config_file: Path = JUPYTER_CONFIG,
) -> list[str]:
    if not directory.is_dir():
        raise LabError(f"{directory} is not a directory")
    if not has_password(config_file):
        raise LabError(
            "Jupyter has no password on this Mac, and Lab must not run without one where "
            "other devices can reach it. Run `jupyter server password` first."
        )
    return [
        find_jupyter_lab(directory, config),
        "--no-browser",
        f"--ServerApp.ip={host}",
        f"--ServerApp.port={port or config.lab_port}",
        # A fixed port or nothing: the bookmark on the tablet names it.
        "--ServerApp.port_retries=0",
        f"--ServerApp.root_dir={directory}",
        # No token in any case, and no way in without the password.
        "--IdentityProvider.token=",
        "--PasswordIdentityProvider.password_required=True",
        # Lets the .local name through Jupyter's Host check without switching the check off.
        f"--ServerApp.local_hostnames={netinfo.local_hostname()}.local",
        f"--ServerApp.local_hostnames={netinfo.local_hostname().lower()}.local",
        "--ServerApp.local_hostnames=localhost",
        "--custom-css",
    ]
