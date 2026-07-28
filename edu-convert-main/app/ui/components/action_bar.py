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
    gutter: int = theme.SPACE_LG,
    compact: bool = False,
) -> ft.Control:
    """Строка состояния и запуска, закреплённая внизу окна.

    ``compact`` — узкое окно: состояние и кнопки встают в два этажа, кнопки
    растягиваются на всю ширину. В одну строку они там не помещаются, а
    ``Row`` не переносит содержимое, а обрезает: кнопка запуска наезжала
    на счётчик документов и он исчезал под ней.
    """
    p = theme.palette(dark)

    if running:
        left: ft.Control = ft.Column(
            spacing=6,
            expand=not compact,
            tight=True,
            controls=[
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(f"{int(progress * 100)} %", size=16,
                                weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                        ft.Text(status or "Конвертация…", size=15, expand=True,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                ),
                ft.ProgressBar(value=progress, bar_height=9,
                               border_radius=theme.RADIUS_PILL),
            ],
        )
    else:
        # ``wrap`` — страховка и для широкого окна: длинная подпись «Выберите
        # базу и шаблоны» вместе со счётчиком не всегда влезает в отведённую
        # ширину, и без переноса вторая пилюля уходила под кнопку.
        left = ft.Row(
            spacing=8,
            run_spacing=8,
            wrap=True,
            expand=not compact,
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

    # На узком окне кнопки делят ширину поровну (``expand``) и сжимают поля:
    # иначе пара «Результаты + Конвертировать» не помещается даже в минимальные
    # 600 px окна.
    actions: list[ft.Control] = []
    if done and not running:
        actions.append(
            ft.OutlinedButton(
                "Результаты",
                icon=ft.Icons.ASSESSMENT_OUTLINED,
                on_click=on_show_results,
                expand=compact,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
                    padding=ft.Padding.symmetric(
                        horizontal=14 if compact else 24, vertical=24 if compact else 28
                    ),
                    text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600),
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
            expand=compact,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
                padding=ft.Padding.symmetric(
                    horizontal=16 if compact else 32, vertical=26 if compact else 30
                ),
                text_style=ft.TextStyle(size=17, weight=ft.FontWeight.W_600),
            ),
        )
    )

    # Без ``animate``: горизонтальный отступ здесь зависит от ширины окна,
    # и общая анимация контейнера растягивала его перестройку на 680 мс —
    # панель отставала от края окна при перетаскивании. Перекраску при смене
    # темы берут на себя токены ``ColorScheme``.
    buttons = ft.Row(actions, spacing=10, tight=not compact)
    content = (
        ft.Column(spacing=theme.SPACE_SM, tight=True, controls=[left, buttons])
        if compact
        else ft.Row(
            spacing=theme.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[left, buttons],
        )
    )

    return ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        padding=ft.Padding.symmetric(
            horizontal=gutter,
            vertical=theme.SPACE_SM if compact else theme.SPACE_MD,
        ),
        content=content,
    )
