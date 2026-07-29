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
        controls.append(ft.Icon(icon, size=16 if compact else 18, color=fg))
    controls.append(
        ft.Text(label, size=14 if compact else 15, weight=ft.FontWeight.W_600, color=fg)
    )
    return ft.Container(
        bgcolor=bg or ft.Colors.SURFACE_CONTAINER_HIGH,
        border_radius=theme.RADIUS_PILL,
        padding=ft.Padding.symmetric(
            horizontal=12 if compact else 16, vertical=5 if compact else 8
        ),
        content=ft.Row(controls, spacing=6, tight=True),
    )


@ft.component
def StatCard(label: str, value: int, total: int, fg: str, bg: str, icon: str,
             compact: bool = False) -> ft.Control:
    """Плитка сводки: число, подпись и доля от общего количества файлов.

    ``compact`` — узкое окно: плитки стоят друг под другом, и три штуки с
    числом в 38 px занимали весь экран, вытесняя всё остальное за нижний край.
    Поэтому число переезжает на одну строку с подписью и уменьшается.
    """
    share = value / total if total else 0.0
    head = ft.Row(
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(icon, size=20, color=fg),
            ft.Text(
                label, size=15, color=fg, weight=ft.FontWeight.W_600,
                expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
            ),
            *([ft.Text(str(value), size=26, weight=ft.FontWeight.BOLD, color=fg)]
              if compact else []),
        ],
    )
    return ft.Container(
        expand=True,
        bgcolor=bg,
        border_radius=theme.RADIUS_CONTROL,
        padding=ft.Padding.symmetric(
            horizontal=20, vertical=14 if compact else 18
        ),
        content=ft.Column(
            spacing=8 if compact else 10,
            tight=True,
            controls=[
                head,
                *([] if compact
                  else [ft.Text(str(value), size=38, weight=ft.FontWeight.BOLD,
                                color=fg)]),
                ft.ProgressBar(
                    value=share,
                    bar_height=6,
                    color=fg,
                    bgcolor=ft.Colors.with_opacity(0.20, fg),
                    border_radius=theme.RADIUS_PILL,
                ),
            ],
        ),
    )
