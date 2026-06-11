"""Бейдж статуса файла: цветная «пилюля» с иконкой и подписью.

Используется в таблице результатов вместо цветного кружка. ``ft.Badge``
не подходит — это оверлей-значок поверх контрола, а не самостоятельная
пилюля, поэтому компонент собран на :class:`ft.Container`.
"""

from __future__ import annotations

import flet as ft

from app.core.models import FileStatus
from app.ui import theme

# статус → (иконка, цвет текста/иконки, цвет подложки)
_STYLES: dict[FileStatus, tuple[ft.Icons, str, str]] = {
    FileStatus.SUCCESS: (ft.Icons.CHECK_CIRCLE_ROUNDED, theme.OK_GREEN, theme.OK_GREEN_BG),
    FileStatus.DISCREPANCY: (ft.Icons.WARNING_AMBER_ROUNDED, theme.WARN_ORANGE, theme.WARN_ORANGE_BG),
    FileStatus.ERROR: (ft.Icons.ERROR_ROUNDED, theme.GUU_RED, theme.ERROR_RED_BG),
}


@ft.component
def StatusBadge(status: FileStatus) -> ft.Control:
    """Пилюля статуса: «Успешно» / «Расхождение» / «Ошибка»."""
    icon, fg, bg = _STYLES[status]
    return ft.Container(
        bgcolor=bg,
        border_radius=999,
        padding=ft.Padding.symmetric(horizontal=10, vertical=3),
        content=ft.Row(
            tight=True,
            spacing=4,
            controls=[
                ft.Icon(icon, size=14, color=fg),
                ft.Text(status.value, size=12, weight=ft.FontWeight.W_600, color=fg),
            ],
        ),
    )


@ft.component
def CountPill(label: str, value: int, fg: str, bg: str) -> ft.Control:
    """Счётчик-пилюля для сводки над таблицей («Успешно: N» и т.п.)."""
    return ft.Container(
        bgcolor=bg,
        border_radius=999,
        padding=ft.Padding.symmetric(horizontal=12, vertical=4),
        content=ft.Text(
            f"{label}: {value}", size=12, weight=ft.FontWeight.W_600, color=fg
        ),
    )
