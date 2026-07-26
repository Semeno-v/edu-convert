"""Список выбранных исходников с построчным удалением (зона 2).

Виртуализированный :class:`ft.ListView` с фиксированной высотой строки
(``item_extent``) — партии в 80+ файлов скроллятся без потери FPS.
Hover-подсветка строки — локальное состояние ``FileRow``: при наведении
перерисовывается только одна строка, не весь список.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import flet as ft

_ROW_HEIGHT = 40
_MAX_LIST_HEIGHT = 240  # ~6 строк, дальше — внутренний скролл


@ft.component
def FileRow(path: Path, on_remove: Callable[[Path], None]) -> ft.Control:
    """Строка одного файла: иконка, имя с эллипсисом, кнопка удаления."""
    hovered, set_hovered = ft.use_state(False)
    return ft.Container(
        height=_ROW_HEIGHT,
        padding=ft.Padding.symmetric(horizontal=10),
        border_radius=6,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW if hovered else None,
        on_hover=lambda e: set_hovered(e.data),  # e.data: bool — вход/выход курсора
        content=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=18, color=ft.Colors.PRIMARY),
                ft.Text(
                    path.name,
                    size=13,
                    expand=True,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=str(path),  # полный путь — по наведению
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=16,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    tooltip="Убрать файл",
                    # p=path фиксирует значение: лямбда в цикле без этого
                    # захватила бы последний элемент списка
                    on_click=lambda e, p=path: on_remove(p),
                ),
            ],
        ),
    )


@ft.component
def FileList(files: list[Path], on_remove: Callable[[Path], None]) -> ft.Control:
    """Список выбранных файлов; пустой список — курсивная заглушка."""
    if not files:
        return ft.Container(
            padding=12,
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                "Файлы ещё не выбраны",
                size=12,
                italic=True,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        )
    return ft.Container(
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=8,
        padding=ft.Padding.symmetric(vertical=4),
        content=ft.ListView(
            height=min(_ROW_HEIGHT * len(files), _MAX_LIST_HEIGHT),
            item_extent=_ROW_HEIGHT,
            controls=[FileRow(p, on_remove) for p in files],
        ),
    )
