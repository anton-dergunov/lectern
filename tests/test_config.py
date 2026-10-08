from pathlib import Path

import pytest

from lectern import config
from lectern.cli import main


@pytest.fixture(autouse=True)
def settings_dir(tmp_path: Path, monkeypatch) -> Path:
    directory = tmp_path / "settings"
    monkeypatch.setenv("LECTERN_CONFIG_DIR", str(directory))
    # No lectern is running as far as these tests are concerned.
    monkeypatch.setattr("lectern.cli._running", lambda port: None)
    return directory


def test_no_file_means_defaults():
    loaded = config.load()
    assert (loaded.port, loaded.lab_port, loaded.roots, loaded.extra_hosts) == (8642, 8888, {}, [])


def test_what_is_saved_is_what_is_loaded(tmp_path: Path):
    folder = tmp_path / 'odd "name" here'
    folder.mkdir()
    saved = config.Config(port=9000, extra_hosts=["mac.tail1234.ts.net"], lab_command="~/bin/lab")
    saved.roots = {"odd": folder, "home-project": Path.home() / "some" / "project"}
    config.save(saved)

    loaded = config.load()
    assert loaded == saved
    # Folders under the home directory are written with ~, so the file suits any Mac.
    assert '"home-project" = "~/some/project"' in config.config_path().read_text()


def test_notes_are_on_unless_switched_off():
    assert config.load().notes is True
    config.save(config.Config())
    assert "notes" not in config.config_path().read_text()

    config.save(config.Config(notes=False))
    assert "notes = false" in config.config_path().read_text()
    assert config.load().notes is False


def test_add_and_remove(tmp_path: Path):
    first, second = tmp_path / "notes", tmp_path / "elsewhere" / "notes"
    first.mkdir()
    second.mkdir(parents=True)

    _, name = config.add_root(first)
    assert name == "notes" and config.load().roots == {"notes": first.resolve()}
    # Adding the same folder again changes nothing.
    config.add_root(first)
    with pytest.raises(config.ConfigError, match="already"):
        config.add_root(second)
    config.add_root(second, name="other-notes")
    assert set(config.load().roots) == {"notes", "other-notes"}

    config.remove_root("notes")
    assert set(config.load().roots) == {"other-notes"}
    with pytest.raises(config.ConfigError, match="no saved folder is named notes"):
        config.remove_root("notes")


@pytest.mark.parametrize("name", ["", ".hidden", "_static", "a/b"])
def test_names_that_cannot_be_addresses(tmp_path: Path, name: str):
    with pytest.raises(config.ConfigError):
        config.add_root(tmp_path, name=name)


def test_a_broken_file_is_reported_not_overwritten(settings_dir: Path):
    settings_dir.mkdir()
    (settings_dir / "config.toml").write_text("port = \n")
    with pytest.raises(config.ConfigError, match="config.toml"):
        config.load()
    assert main(["list"]) == 1


def test_commands(tmp_path: Path, capsys):
    folder = tmp_path / "reading"
    folder.mkdir()

    assert main(["add", str(folder)]) == 0
    assert "saved reading" in capsys.readouterr().out
    assert main(["list"]) == 0
    assert str(folder.resolve()) in capsys.readouterr().out
    assert main(["remove", "reading"]) == 0
    assert main(["remove", "reading"]) == 1
    assert "no saved folder" in capsys.readouterr().err
    assert main(["add", str(tmp_path / "missing")]) == 1
