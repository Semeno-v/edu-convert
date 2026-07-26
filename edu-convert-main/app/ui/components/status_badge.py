"""Мелкие индикаторы: бейдж статуса файла, «пилюли» и плитки сводки.

``ft.Badge`` не подходит — это оверлей-значок поверх контрола, а не
самостоятельный элемент строки, поэтому индикаторы собраны на
:class:`ft.Container`. Цвета статусов берутся из :func:`app.ui.theme.palette`,
поэтому одинаково читаются в светлой и тёмной теме.
"""

from __future__ import annotations

import flet as ft

from app.core.models import FileStatus
from app.ui import theme


def status_colors(status: FileStatus, dark: bool = False) -> tuple[str, str, str]:
    """Иконка и пара цветов (текст, подложка) для статуса файла."""
    p = theme.palette(dark)
    return {
        FileStatus.SUCCESS: (ft.Icons.CHECK_CIRCLE_ROUNDED, p.ok, p.ok_bg),
        FileStatus.DISCREPANCY: (ft.Icons.CHANGE_CIRCLE_ROUNDED, p.warn, p.warn_bg),
        FileStatus.ERROR: (ft.Icons.ERROR_ROUNDED, p.danger, p.danger_bg),
    }[status]


@ft.component
def StatusBadge(status: FileStatus, dark: bool = False) -> ft.Control:
    """Пилюля статуса: «Успешно» / «Расхождение» / «Ошибка»."""
    icon, fg, bg = status_colors(status, dark)
    return Pill(status.value, icon=icon, fg=fg, bg=bg)


@ft.component
def Pill(
    label: str,
    icon: str | None = None,
    fg: str | None = None,
    bg: str | None = None,
    compact: bool = False,
) -> ft.Control:
    """Компактная «пилюля» с необязательной иконкой."""
    fg = fg or ft.Colors.ON_SURFACE_VARIANT
    controls: list[ft.Control] = []
    if icon:
        controls.append(ft.Icon(icon, size=13, color=fg))
    controls.append(
        ft.Text(label, size=11 if compact else 12, weight=ft.FontWeight.W_600, color=fg)
    )
    return ft.Container(
        bgcolor=bg or ft.Colors.SURFACE_CONTAINER_HIGH,
        border_radius=theme.RADIUS_PILL,
        padding=ft.Padding.symmetric(
            horizontal=8 if compact else 11, vertical=2 if compact else 4
        ),
        content=ft.Row(controls, spacing=5, tight=True),
    )


@ft.component
def StatCard(label: str, value: int, total: int, fg: str, bg: str, icon: str) -> ft.Control:
    """Плитка сводки: число, подпись и доля от общего количества файлов."""
    share = value / total if total else 0.0
    return ft.Container(
        expand=True,
        bgcolor=bg,
        border_radius=theme.RADIUS_CONTROL,
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        content=ft.Column(
            spacing=8,
            tight=True,
            controls=[
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(icon, size=15, color=fg),
                        ft.Text(
                            label, size=12, color=fg, weight=ft.FontWeight.W_600,
                            expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
                ft.Text(str(value), size=26, weight=ft.FontWeight.BOLD, color=fg),
                ft.ProgressBar(
                    value=share,
                    bar_height=4,
                    color=fg,
                    bgcolor=ft.Colors.with_opacity(0.20, fg),
                    border_radius=theme.RADIUS_PILL,
                ),
            ],
        ),
    )
