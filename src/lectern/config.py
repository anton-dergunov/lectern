"""The saved settings: which folders to serve, and on which ports.

~/.config/lectern/config.toml

port = 8642
lab_port = 8888
extra_hosts = []            # other names this Mac is reached by, e.g. its ts.net name
notes = false               # only to switch highlights and notes off; they are on without it

[roots]
"agent-memory-eval" = "~/projects/writing/agent-memory-eval"
"""

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import APP_NAME

DEFAULT_PORT = 8642
DEFAULT_LAB_PORT = 8888


class ConfigError(Exception):
    """The settings file, or a change asked of it, that the person has to put right."""


@dataclass
class Config:
    port: int = DEFAULT_PORT
    lab_port: int = DEFAULT_LAB_PORT
    extra_hosts: list[str] = field(default_factory=list)
    # The JupyterLab to run for `lectern lab` when the folder has no environment of its own.
    lab_command: str = ""
    # Whether text can be marked and remarked on, which has the server write a file.
    notes: bool = True
    roots: dict[str, Path] = field(default_factory=dict)


def config_path() -> Path:
    directory = os.environ.get("LECTERN_CONFIG_DIR") or f"~/.config/{APP_NAME}"
    return Path(directory).expanduser() / "config.toml"


def root_name(path: Path) -> str:
    """The name a folder is served under: the first segment of its URLs."""
    name = path.name
    if not name or name.startswith((".", "_")):
        raise ConfigError(f"cannot serve {path}: its name must not be empty or start with . or _")
    return name


def load(path: Path | None = None) -> Config:
    path = path or config_path()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Config()
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"{path}: {error}") from error
    config = Config()
    try:
        config.port = int(data.get("port", config.port))
        config.lab_port = int(data.get("lab_port", config.lab_port))
        config.extra_hosts = [str(host) for host in data.get("extra_hosts", [])]
        config.lab_command = str(data.get("lab_command", ""))
        config.notes = data.get("notes", True) is not False
        roots = data.get("roots", {})
        config.roots = {str(name): Path(str(where)).expanduser() for name, where in roots.items()}
    except (TypeError, ValueError, AttributeError) as error:
        raise ConfigError(f"{path}: {error}") from error
    return config


def _short(path: Path) -> str:
    """With the home directory as `~`, so the file reads the same on every Mac."""
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(path)


def save(config: Config, path: Path | None = None) -> None:
    # TOML's basic strings and JSON's agree for everything a path or host name contains.
    lines = [
        f"port = {config.port}",
        f"lab_port = {config.lab_port}",
        f"extra_hosts = [{', '.join(json.dumps(host) for host in config.extra_hosts)}]",
    ]
    if config.lab_command:
        lines.append(f"lab_command = {json.dumps(config.lab_command)}")
    if not config.notes:
        lines.append("notes = false")
    lines += ["", "[roots]"]
    lines += [
        f"{json.dumps(name)} = {json.dumps(_short(where))}"
        for name, where in sorted(config.roots.items())
    ]
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_root(where: Path, name: str | None = None) -> tuple[Config, str]:
    where = where.expanduser().resolve()
    if not where.is_dir():
        raise ConfigError(f"{where} is not a directory")
    config = load()
    if name is None:
        name = root_name(where)
    elif not name or name.startswith((".", "_")) or "/" in name:
        raise ConfigError(f"the name {name!r} must not be empty, contain / or start with . or _")
    taken = config.roots.get(name)
    if taken and taken.resolve() != where:
        raise ConfigError(f"{name} is already {taken}; give this one another name with --name")
    config.roots[name] = where
    save(config)
    return config, name


def remove_root(name: str) -> Config:
    config = load()
    if name not in config.roots:
        known = ", ".join(sorted(config.roots)) or "none"
        raise ConfigError(f"no saved folder is named {name} (saved: {known})")
    del config.roots[name]
    save(config)
    return config
