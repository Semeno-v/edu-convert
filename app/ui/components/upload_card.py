"""Карточка загрузки файла (база / шаблон) с индикацией успешной загрузки.

Зона 1 интерфейса (ТЗ §5): выбор файла + зелёная галочка при успешной загрузке.
Контурный вариант карточки, иконка в тонированном круге, галочка появляется
с плавным изменением прозрачности. При ``menu_items`` рядом с кнопкой «Выбрать»
появляется PopupMenuButton с историей недавних файлов.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.ui import theme


@ft.component
def UploadCard(
    title: str,
    value: str | None,
    ok: bool,
    icon: str,
    on_pick: Callable[[ft.Event[ft.Control]], None],
    menu_items: list[tuple[str, Callable]] | None = None,
) -> ft.Control:
    """Карточка одного источника (база/шаблон РПД/шаблон ФОС)."""
    action_controls: list[ft.Control] = [
        ft.FilledTonalButton("Выбрать", icon=ft.Icons.FOLDER_OPEN, on_click=on_pick),
    ]
    if menu_items:
        action_controls.append(
            ft.PopupMenuButton(
                icon=ft.Icons.HISTORY_ROUNDED,
                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                icon_size=18,
                tooltip="Недавние",
                items=[
                    ft.PopupMenuItem(
                        content=ft.Text(label, size=12, max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                        on_click=on_select,
                    )
                    for label, on_select in menu_items
                ],
            )
        )

    return ft.Card(
        variant=ft.CardVariant.OUTLINED,
        content=ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=42,
                        height=42,
                        border_radius=21,
                        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=22, color=ft.Colors.PRIMARY),
                    ),
                    ft.Column(
                        spacing=2,
                        expand=True,
                        controls=[
                            ft.Text(title, size=14, weight=ft.FontWeight.W_600),
                            ft.Text(
                                value or "файл не выбран",
                                size=11,
                                italic=value is None,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_ROUNDED if ok else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        color=theme.OK_GREEN if ok else ft.Colors.OUTLINE,
                        size=22,
                        opacity=1.0 if ok else 0.6,
                        animate_opacity=ft.Animation(
                            duration=ft.Duration(milliseconds=200),
                            curve=ft.AnimationCurve.EASE_OUT,
                        ),
                    ),
                    ft.Row(spacing=2, tight=True, controls=action_controls),
                ],
            ),
        ),
    )
