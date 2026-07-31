"""Настройки между сессиями (app/ui/persistence.py).

Модуль намеренно молчит при любых сбоях диска, поэтому его ошибки не видны:
битый файл читается как «настроек нет», и пользователь просто теряет пути.
Проверяется как раз это — что порча файла не роняет приложение и не выдаёт
мусор за настройки.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ui import persistence


@pytest.fixture(autouse=True)
def settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Уводит настройки в tmp_path, чтобы не трогать ~/.educonvert."""
    path = tmp_path / ".educonvert" / "settings.json"
    monkeypatch.setattr(persistence, "_SETTINGS_PATH", path)
    return path


def test_load_without_file_returns_empty(settings_file: Path) -> None:
    assert not settings_file.exists()
    assert persistence.load() == {}


def test_paths_survive_round_trip(settings_file: Path) -> None:
    persistence.save_paths("/дом/база.xlsx", "/дом/рпд.docx", "/дом/фос.docx")

    data = persistence.load()
    assert data["db_path"] == "/дом/база.xlsx"
    assert data["rpd_path"] == "/дом/рпд.docx"
    assert data["fos_path"] == "/дом/фос.docx"


def test_dark_mode_survives_round_trip(settings_file: Path) -> None:
    assert persistence.get_dark_mode() is False

    persistence.save_dark_mode(True)
    assert persistence.get_dark_mode() is True


def test_saving_theme_keeps_paths(settings_file: Path) -> None:
    """Разные ключи не затирают друг друга: пишется весь словарь целиком."""
    persistence.save_paths("/дом/база.xlsx", "/дом/рпд.docx", "/дом/фос.docx")
    persistence.save_dark_mode(True)

    assert persistence.load()["db_path"] == "/дом/база.xlsx"
    assert persistence.get_dark_mode() is True


def test_broken_json_reads_as_empty(settings_file: Path) -> None:
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text("{не json", encoding="utf-8")

    assert persistence.load() == {}
    assert persistence.get_recent_dbs() == []
    assert persistence.get_dark_mode() is False


def test_json_list_instead_of_object_reads_as_empty(settings_file: Path) -> None:
    """Файл правят руками, и вместо словаря там может оказаться что угодно.

    Без проверки типа вызывающий код падал бы уже на ``data["db_path"]``,
    за пределами try/except внутри модуля.
    """
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text('["/дом/база.xlsx"]', encoding="utf-8")

    assert persistence.load() == {}
    assert persistence.get_recent_dbs() == []


def test_recent_dbs_keep_last_three_unique(settings_file: Path, tmp_path: Path) -> None:
    bases = []
    for i in range(4):
        base = tmp_path / f"база{i}.xlsx"
        base.touch()
        bases.append(str(base))
        persistence.add_recent_db(str(base))

    # Свежие впереди, самая старая вытеснена.
    assert persistence.get_recent_dbs() == [bases[3], bases[2], bases[1]]


def test_recent_db_repeat_moves_to_front(settings_file: Path, tmp_path: Path) -> None:
    first, second = tmp_path / "1.xlsx", tmp_path / "2.xlsx"
    first.touch()
    second.touch()
    persistence.add_recent_db(str(first))
    persistence.add_recent_db(str(second))
    persistence.add_recent_db(str(first))

    assert persistence.get_recent_dbs() == [str(first), str(second)]


def test_recent_dbs_hide_deleted_files(settings_file: Path, tmp_path: Path) -> None:
    base = tmp_path / "база.xlsx"
    base.touch()
    persistence.add_recent_db(str(base))
    base.unlink()

    assert persistence.get_recent_dbs() == []


def test_write_leaves_no_temp_files(settings_file: Path) -> None:
    """Запись атомарна: временный файл подменяет настоящий и не остаётся рядом."""
    persistence.save_paths(None, "/дом/рпд.docx", "/дом/фос.docx")

    assert json.loads(settings_file.read_text(encoding="utf-8"))["db_path"] is None
    assert [p.name for p in settings_file.parent.iterdir()] == ["settings.json"]
