"""The names this Mac answers to on the local network."""

import socket
import subprocess


def _run(*argv: str) -> str | None:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() or None if done.returncode == 0 else None


def local_hostname() -> str:
    """The Bonjour name without `.local`, e.g. `Antons-MacBook-Air-13`."""
    return _run("scutil", "--get", "LocalHostName") or socket.gethostname().removesuffix(".local")


def lan_ip() -> str | None:
    # en0 is Wi-Fi on a laptop; en1 covers Macs where Ethernet took en0.
    for interface in ("en0", "en1"):
        if ip := _run("ipconfig", "getifaddr", interface):
            return ip
    return None
