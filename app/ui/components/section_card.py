"""Карточка-секция с номером шага — единый каркас зон главного экрана.

Каждая зона интерфейса (базовые файлы, исходники, конвертация, результаты)
оформляется одинаково: контурная карточка, круглый номер шага, заголовок
с необязательным подзаголовком и необязательный элемент справа (``trailing``).
При ``done=True`` кружок с номером заменяется зелёной галочкой.
"""

from __future__ import annotations

import flet as ft

from app.ui import theme

_CENTER = ft.Alignment.CENTER


@ft.component
def SectionCard(
    number: str,
    title: str,
    content: ft.Control,
    subtitle: str | None = None,
    trailing: ft.Control | None = None,
    done: bool = False,
) -> ft.Control:
    """Секция экрана: номер/галочка шага + заголовок + содержимое."""
    title_column: list[ft.Control] = [
        ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
    ]
    if subtitle:
        title_column.append(
            ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        )

    step_badge = ft.Container(
        width=30,
        height=30,
        border_radius=15,
        bgcolor=(
            ft.Colors.with_opacity(0.15, theme.OK_GREEN) if done
            else ft.Colors.PRIMARY
        ),
        alignment=_CENTER,
        content=(
            ft.Icon(ft.Icons.CHECK_ROUNDED, color=theme.OK_GREEN, size=18)
            if done else
            ft.Text(number, color=ft.Colors.ON_PRIMARY, size=14, weight=ft.FontWeight.BOLD)
        ),
    )

    header_controls: list[ft.Control] = [
        step_badge,
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
