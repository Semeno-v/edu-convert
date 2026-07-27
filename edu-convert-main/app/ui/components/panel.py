"""Панель — базовая карточка рабочей области.

Единый каркас для всех блоков экрана: тонкая линия-контур, мягкая тень,
скруглённые углы и шапка «иконка + заголовок + необязательный элемент
справа». Заменяет прежние карточки-секции с номерами шагов: порядок действий
теперь задаёт компоновка экрана, а не нумерация.
"""

from __future__ import annotations

import flet as ft

from app.ui import theme


@ft.component
def Panel(
    title: str,
    content: ft.Control,
    icon: str | None = None,
    subtitle: str | None = None,
    trailing: ft.Control | None = None,
    dark: bool = False,
    expand: bool | int = False,
) -> ft.Control:
    """Карточка с заголовком и произвольным содержимым."""
    heading: list[ft.Control] = []
    if icon:
        heading.append(
            ft.Container(
                width=50,
                height=50,
                border_radius=15,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(icon, size=26, color=ft.Colors.PRIMARY),
            )
        )

    titles: list[ft.Control] = [
        ft.Text(title, size=20, weight=ft.FontWeight.W_600,
                color=ft.Colors.ON_SURFACE)
    ]
    if subtitle:
        titles.append(ft.Text(subtitle, size=15, color=ft.Colors.ON_SURFACE_VARIANT))

    heading.append(ft.Column(titles, spacing=2, expand=True, tight=True))
    if trailing is not None:
        heading.append(trailing)

    # Цвета взяты токенами ``ColorScheme``, а не из ``Palette``: их
    # перекрашивание при смене темы Flutter анимирует сам через
    # ``page.theme_animation_style``. Прежний ``animate`` на контейнере делал
    # то же самое, но заодно интерполировал размер и отступы — панель, растущая
    # от новой строки в списке или от изменения ширины окна, ползла к своему
    # размеру 680 мс, и это читалось как подтормаживание интерфейса.
    return ft.Container(
        expand=expand,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=theme.RADIUS_CARD,
        shadow=theme.soft_shadow(dark),
        padding=ft.Padding.all(theme.SPACE_LG),
        content=ft.Column(
            spacing=theme.SPACE_MD,
            expand=expand,
            controls=[
                ft.Row(
                    spacing=theme.SPACE_MD,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=heading,
                ),
                content,
            ],
        ),
    )
