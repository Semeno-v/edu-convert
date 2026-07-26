"""Получение путей к файлам, скопированным в файловом менеджере.

Кроссплатформенно, без Windows-only зависимостей: основной источник — сервис
``ft.Clipboard`` (Проводник, Finder, Nautilus/Nemo кладут туда список файлов).
Там, где Flutter не отдаёт список файлов (актуально для Linux), выручают два
запасных пути: текстовое содержимое буфера в формате ``text/uri-list`` и
внешние утилиты ``wl-paste``/``xclip``, если они установлены.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import flet as ft

_LINUX_TOOLS: tuple[tuple[str, ...], ...] = (
    ("wl-paste", "--no-newline", "--type", "text/uri-list"),
    ("xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"),
)


async def clipboard_paths(clipboard: ft.Clipboard) -> list[str]:
    """Пути к файлам в буфере обмена (пустой список, если их там нет)."""
    for source in (
        lambda: _from_service(clipboard),
        lambda: _from_text(clipboard),
    ):
        try:
            paths = await source()
        except Exception:  # noqa: BLE001 — буфер недоступен: пробуем следующий способ
            paths = []
        if paths:
            return paths
    return _from_external_tool()


def hint() -> str:
    """Подсказка, как скопировать файлы в текущей системе."""
    if sys.platform == "win32":
        return "Скопируйте файлы в Проводнике (Ctrl+C), затем нажмите Ctrl+V здесь"
    if sys.platform == "darwin":
        return "Скопируйте файлы в Finder (⌘C), затем нажмите ⌘V здесь"
    return "Скопируйте файлы в файловом менеджере (Ctrl+C), затем нажмите Ctrl+V здесь"


def unavailable_reason() -> str | None:
    """Почему вставка может не сработать, или ``None``, если всё в порядке.

    На Linux Flutter не всегда отдаёт список файлов, и тогда нужен
    ``wl-paste`` (Wayland) или ``xclip`` (X11).
    """
    if sys.platform in ("win32", "darwin"):
        return None
    if any(shutil.which(tool[0]) for tool in _LINUX_TOOLS):
        return None
    return (
        "Если вставка не сработает, установите xclip: sudo apt install xclip "
        "(для Wayland — wl-clipboard)"
    )


async def _from_service(clipboard: ft.Clipboard) -> list[str]:
    return _existing(await clipboard.get_files())


async def _from_text(clipboard: ft.Clipboard) -> list[str]:
    return _existing(_parse(await clipboard.get() or ""))


def _from_external_tool() -> list[str]:
    for tool in _LINUX_TOOLS:
        if not shutil.which(tool[0]):
            continue
        try:
            completed = subprocess.run(  # noqa: S603 — команда из констант модуля
                list(tool), capture_output=True, text=True, timeout=5, check=False
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if paths := _existing(_parse(completed.stdout)):
            return paths
    return []


def _parse(text: str) -> list[str]:
    """Разбирает содержимое буфера: ``file://``-ссылки или обычные пути."""
    paths: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        # Nautilus/Nemo добавляют служебные строки «x-special/…», «copy»
        if not line or line.startswith(("#", "x-special/")) or line in ("copy", "cut"):
            continue
        if line.startswith("file://"):
            paths.append(unquote(urlparse(line).path))
        else:
            paths.append(line)
    return paths


def _existing(paths: list[str]) -> list[str]:
    return [p for p in paths if p and Path(p).is_file()]
