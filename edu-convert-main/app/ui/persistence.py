"""Хранение настроек EduConvert между сессиями.

Файл настроек: ``~/.educonvert/settings.json`` — пути файлов и история баз.
Все операции защищены try/except: отсутствие файла или ошибка диска
не прерывает работу приложения.
"""

from __future__ import annotations

import json
from pathlib import Path

_SETTINGS_PATH = Path.home() / ".educonvert" / "settings.json"
_MAX_RECENT = 3


def _read() -> dict:
    try:
        return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(data: dict) -> None:
    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def load() -> dict:
    """Возвращает сохранённые настройки (пустой словарь при отсутствии файла)."""
    return _read()


def save_paths(db_path: str | None, rpd_path: str, fos_path: str) -> None:
    """Сохраняет актуальные пути файлов."""
    data = _read()
    data["db_path"] = db_path
    data["rpd_path"] = rpd_path
    data["fos_path"] = fos_path
    _write(data)


def add_recent_db(path: str) -> None:
    """Добавляет путь к базе в историю; хранит последние _MAX_RECENT уникальных."""
    data = _read()
    recent: list[str] = data.get("recent_dbs", [])
    recent = [p for p in recent if p != path]
    recent.insert(0, path)
    data["recent_dbs"] = recent[:_MAX_RECENT]
    _write(data)


def get_recent_dbs() -> list[str]:
    """Возвращает список недавних баз (только существующие файлы)."""
    return [p for p in _read().get("recent_dbs", []) if Path(p).exists()]


def save_dark_mode(dark: bool) -> None:
    """Запоминает выбранный режим оформления."""
    _write({**_read(), "dark_mode": dark})


def get_dark_mode() -> bool:
    """Была ли в прошлый раз включена тёмная тема."""
    return bool(_read().get("dark_mode", False))
