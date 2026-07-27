"""Хранение настроек EduConvert между сессиями.

Файл настроек: ``~/.educonvert/settings.json`` — пути файлов и история баз.
Все операции защищены try/except: отсутствие файла или ошибка диска
не прерывает работу приложения.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_SETTINGS_PATH = Path.home() / ".educonvert" / "settings.json"
_MAX_RECENT = 3


def _read() -> dict:
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    # Файл правят руками: если внутри оказался список или строка, вызывающий
    # код упал бы на data["ключ"] уже за пределами этого try.
    return data if isinstance(data, dict) else {}


def _write(data: dict) -> None:
    """Атомарно перезаписывает файл настроек.

    Запись идёт во временный файл рядом, затем ``os.replace`` подменяет
    настоящий одним неделимым шагом. Прямая запись сначала обрезала файл:
    сбой посреди неё оставлял битый JSON, а он молча читается как пустой —
    пользователь терял все пути, историю баз и выбранную тему разом.
    """
    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _SETTINGS_PATH.with_name(f"{_SETTINGS_PATH.name}.{os.getpid()}.tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, _SETTINGS_PATH)
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
