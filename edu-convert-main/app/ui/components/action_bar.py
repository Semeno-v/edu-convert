"""Нижняя панель действий — единственная «главная кнопка» экрана.

Панель закреплена внизу окна и всегда на виду: слева — что готово, а чего не
хватает, справа — запуск конвертации. Во время работы она превращается в
индикатор прогресса с именем текущего файла, по завершении — в переход
к результатам.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.ui import theme
from app.ui.components.status_badge import Pill


@ft.component
def ActionBar(
    ready: bool,
    running: bool,
    done: bool,
    files_count: int,
    sources_ok: bool,
    progress: float,
    status: str,
    blocked_reason: str | None,
    on_start: Callable[[ft.Event[ft.Control]], None],
    on_show_results: Callable[[ft.Event[ft.Control]], None],
    dark: bool = False,
) -> ft.Control:
    """Строка состояния и запуска, закреплённая внизу окна."""
    p = theme.palette(dark)

    if running:
        left: ft.Control = ft.Column(
            spacing=6,
            expand=True,
            tight=True,
            controls=[
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(f"{int(progress * 100)} %", size=13,
                                weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                        ft.Text(status or "Конвертация…", size=12, expand=True,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                ),
                ft.ProgressBar(value=progress, bar_height=6,
                               border_radius=theme.RADIUS_PILL),
            ],
        )
    else:
        left = ft.Row(
            spacing=8,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                Pill(
                    "Источники готовы" if sources_ok else "Выберите базу и шаблоны",
                    icon=ft.Icons.CHECK_ROUNDED if sources_ok else ft.Icons.INFO_OUTLINE,
                    fg=p.ok if sources_ok else ft.Colors.ON_SURFACE_VARIANT,
                    bg=p.ok_bg if sources_ok else None,
                ),
                Pill(
                    f"Документов: {files_count}",
                    icon=ft.Icons.DESCRIPTION_OUTLINED,
                    fg=ft.Colors.PRIMARY if files_count else ft.Colors.ON_SURFACE_VARIANT,
                    bg=(
                        ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY)
                        if files_count else None
                    ),
                ),
            ],
        )

    actions: list[ft.Control] = []
    if done and not running:
        actions.append(
            ft.OutlinedButton(
                "Результаты",
                icon=ft.Icons.ASSESSMENT_OUTLINED,
                on_click=on_show_results,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=18),
                ),
            )
        )
    actions.append(
        ft.FilledButton(
            "Конвертация…" if running else (
                f"Конвертировать ({files_count})" if files_count else "Конвертировать"
            ),
            icon=None if running else ft.Icons.BOLT_ROUNDED,
            disabled=not ready,
            tooltip=blocked_reason or "Запустить конвертацию (Ctrl+Enter)",
            on_click=on_start,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
                padding=ft.Padding.symmetric(horizontal=22, vertical=20),
                text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_600),
            ),
        )
    )

    return ft.Container(
        bgcolor=p.card,
        border=ft.Border.only(top=ft.BorderSide(1, p.hairline)),
        padding=ft.Padding.symmetric(horizontal=theme.SPACE_LG, vertical=12),
        content=ft.Row(
            spacing=theme.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[left, ft.Row(actions, spacing=8, tight=True)],
        ),
    )
