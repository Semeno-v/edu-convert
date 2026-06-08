"""Карточка загрузки файла (база / шаблон) с индикацией успешной загрузки.

Зона 1 интерфейса (ТЗ §5): выбор файла + зелёная галочка при успешной загрузке.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft


@ft.component
def UploadCard(
    title: str,
    value: str | None,
    ok: bool,
    icon: str,
    on_pick: Callable[[ft.Event[ft.Control]], None],
) -> ft.Control:
    """Карточка одного источника (база/шаблон РПД/шаблон ФОС)."""
    return ft.Card(
        content=ft.Container(
            padding=14,
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(icon, size=28, color=ft.Colors.PRIMARY),
                    ft.Column(
                        spacing=2,
                        expand=True,
                        controls=[
                            ft.Text(title, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                value or "файл не выбран",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE if ok else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        color=ft.Colors.GREEN if ok else ft.Colors.OUTLINE,
                        size=24,
                    ),
                    ft.FilledTonalButton("Выбрать", icon=ft.Icons.FOLDER_OPEN, on_click=on_pick),
                ],
            ),
        ),
    )
