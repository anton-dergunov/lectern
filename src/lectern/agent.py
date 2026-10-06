"""Running lectern from login onwards, as a launchd agent serving the saved folders."""

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from . import APP_NAME

LABEL = f"com.anton.{APP_NAME}"


class AgentError(Exception):
    pass


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def log_path() -> Path:
    return Path.home() / "Library" / "Logs" / f"{APP_NAME}.log"


def _domain() -> str:
    return f"gui/{os.getuid()}"


def program() -> str:
    """The installed `lectern` command, by absolute path: launchd has no shell PATH."""
    found = shutil.which(APP_NAME) or sys.argv[0]
    path = Path(found).expanduser()
    if not path.is_file():
        raise AgentError(f"cannot find the {APP_NAME} command to run at login")
    return str(path.absolute())


def plist(executable: str, host: str | None = None) -> dict:
    arguments = [executable, "serve", "--all"]
    if host:
        arguments += ["--host", host]
    return {
        "Label": LABEL,
        "ProgramArguments": arguments,
        "RunAtLoad": True,
        # Restarted if it crashes, left alone if it stops by itself: it does that when it
        # finds a lectern already answering on the port.
        "KeepAlive": {"SuccessfulExit": False},
        "ProcessType": "Background",
        "StandardOutPath": str(log_path()),
        "StandardErrorPath": str(log_path()),
    }


def _launchctl(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *arguments], capture_output=True, text=True)


def install(host: str | None = None) -> Path:
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    log_path().parent.mkdir(parents=True, exist_ok=True)
    # Replacing a loaded agent needs it unloaded first; not being loaded is not an error.
    _launchctl("bootout", f"{_domain()}/{LABEL}")
    with path.open("wb") as file:
        plistlib.dump(plist(program(), host), file)
    done = _launchctl("bootstrap", _domain(), str(path))
    if done.returncode != 0:
        raise AgentError(f"launchctl could not load {path}: {done.stderr.strip()}")
    return path


def uninstall() -> bool:
    """True if there was an agent to remove."""
    path = plist_path()
    loaded = _launchctl("bootout", f"{_domain()}/{LABEL}").returncode == 0
    existed = path.exists()
    path.unlink(missing_ok=True)
    return loaded or existed


def describe(printed: str) -> str:
    """What `launchctl print` says about the agent, in a few words."""
    fields: dict[str, str] = {}
    for line in printed.splitlines():
        key, separator, value = line.strip().partition(" = ")
        # The service's own fields come first; nested sections repeat names like `state`.
        if separator:
            fields.setdefault(key, value)
    if fields.get("state") == "running" and "pid" in fields:
        return f"running (pid {fields['pid']})"
    return f"loaded, not running (last exit code {fields.get('last exit code', 'unknown')})"


def status() -> str:
    """One of: not installed, installed but not loaded, running (pid N), loaded, not running."""
    if not plist_path().exists():
        return "not installed"
    done = _launchctl("print", f"{_domain()}/{LABEL}")
    if done.returncode != 0:
        return "installed but not loaded"
    return describe(done.stdout)
