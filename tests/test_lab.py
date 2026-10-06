import json
from pathlib import Path

import pytest

from lectern import lab
from lectern.cli import main
from lectern.config import Config


@pytest.fixture
def with_password(tmp_path: Path) -> Path:
    path = tmp_path / "jupyter_server_config.json"
    path.write_text(json.dumps({"IdentityProvider": {"hashed_password": "argon2:..."}}))
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    binary = tmp_path / "project" / ".venv" / "bin" / "jupyter-lab"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n")
    return tmp_path / "project"


def test_refuses_without_a_password(project: Path, tmp_path: Path):
    for content in (None, "{}", '{"IdentityProvider": {"hashed_password": ""}}', "not json"):
        path = tmp_path / "config.json"
        if content is not None:
            path.write_text(content)
        with pytest.raises(lab.LabError, match="jupyter server password"):
            lab.command(project, Config(), config_file=path)


def test_command_line(project: Path, with_password: Path):
    argv = lab.command(project, Config(lab_port=8899), config_file=with_password)

    # The folder's own environment is the one with its kernel and packages.
    assert argv[0] == str(project / ".venv" / "bin" / "jupyter-lab")
    assert "--no-browser" in argv
    assert "--ServerApp.port=8899" in argv and "--ServerApp.port_retries=0" in argv
    assert f"--ServerApp.root_dir={project}" in argv
    # Never a token, never without the password, never with the Host check off.
    assert "--IdentityProvider.token=" in argv
    assert "--PasswordIdentityProvider.password_required=True" in argv
    assert not [a for a in argv if "allow_remote_access" in a or "allow_origin" in a]
    assert [a for a in argv if a.startswith("--ServerApp.local_hostnames=") and ".local" in a]


def test_port_and_host_can_be_given(project: Path, with_password: Path):
    argv = lab.command(project, Config(), port=9001, host="127.0.0.1", config_file=with_password)
    assert "--ServerApp.port=9001" in argv and "--ServerApp.ip=127.0.0.1" in argv


def test_where_jupyter_lab_is_looked_for(tmp_path: Path, with_password: Path, monkeypatch):
    bare = tmp_path / "bare"
    (bare / "notebooks" / ".venv" / "bin").mkdir(parents=True)
    nested = bare / "notebooks" / ".venv" / "bin" / "jupyter-lab"
    nested.write_text("")
    assert lab.find_jupyter_lab(bare, Config()) == str(nested)

    nested.unlink()
    assert lab.find_jupyter_lab(bare, Config(lab_command="/opt/lab")) == "/opt/lab"
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/jupyter-lab")
    assert lab.find_jupyter_lab(bare, Config()) == "/usr/local/bin/jupyter-lab"
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(lab.LabError, match="cannot find jupyter-lab"):
        lab.find_jupyter_lab(bare, Config())


def test_command_reports_instead_of_starting(project: Path, tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LECTERN_CONFIG_DIR", str(tmp_path / "settings"))
    monkeypatch.setattr(lab, "JUPYTER_CONFIG", tmp_path / "none.json")
    monkeypatch.setattr(lab.command, "__defaults__", (None, "0.0.0.0", tmp_path / "none.json"))

    assert main(["lab", str(project)]) == 1
    assert "jupyter server password" in capsys.readouterr().err
