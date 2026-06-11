"""Карточка-секция с номером шага — единый каркас зон главного экрана.

Каждая зона интерфейса (базовые файлы, исходники, конвертация, результаты)
оформляется одинаково: контурная карточка, круглый номер шага, заголовок
с необязательным подзаголовком и необязательный элемент справа (``trailing``).
"""

from __future__ import annotations

import flet as ft


@ft.component
def SectionCard(
    number: str,
    title: str,
    content: ft.Control,
    subtitle: str | None = None,
    trailing: ft.Control | None = None,
) -> ft.Control:
    """Секция экрана: номер шага в круге + заголовок + содержимое."""
    title_column: list[ft.Control] = [
        ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
    ]
    if subtitle:
        title_column.append(
            ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        )

    header_controls: list[ft.Control] = [
        ft.Container(
            width=30,
            height=30,
            border_radius=15,
            bgcolor=ft.Colors.PRIMARY,
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                number, color=ft.Colors.ON_PRIMARY, size=14, weight=ft.FontWeight.BOLD
            ),
        ),
        ft.Column(spacing=0, expand=True, tight=True, controls=title_column),
    ]
    if trailing is not None:
        header_controls.append(trailing)

    return ft.Card(
        variant=ft.CardVariant.OUTLINED,
        content=ft.Container(
            padding=ft.Padding.all(18),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=header_controls,
                    ),
                    content,
                ],
            ),
        ),
    )
