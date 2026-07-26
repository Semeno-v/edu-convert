"""Строка источника: база дисциплин или официальный шаблон 2026.

Компактная плитка «иконка — название — выбранный файл — состояние». Вся
плитка кликабельна (не только кнопка), при наведении подсвечивается, а справа
появляется меню недавних файлов, если оно передано.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.ui import theme


@ft.component
def SourceTile(
    title: str,
    value: str | None,
    ok: bool,
    icon: str,
    on_pick: Callable[[ft.Event[ft.Control]], None],
    dark: bool = False,
    menu_items: list[tuple[str, Callable]] | None = None,
    full_path: str | None = None,
) -> ft.Control:
    """Плитка одного источника данных."""
    hovered, set_hovered = ft.use_state(False)
    p = theme.palette(dark)

    state_mark = ft.Container(
        width=28,
        height=28,
        border_radius=14,
        bgcolor=ft.Colors.with_opacity(0.14, p.ok) if ok else ft.Colors.TRANSPARENT,
        border=None if ok else ft.Border.all(1.5, ft.Colors.OUTLINE_VARIANT),
        alignment=ft.Alignment.CENTER,
        animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        content=ft.Icon(ft.Icons.CHECK_ROUNDED, size=17, color=p.ok) if ok else None,
    )

    trailing: list[ft.Control] = [state_mark]
    if menu_items:
        trailing.append(
            ft.PopupMenuButton(
                icon=ft.Icons.HISTORY_ROUNDED,
                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                icon_size=22,
                tooltip="Недавние базы",
                items=[
                    ft.PopupMenuItem(
                        content=ft.Text(label, size=14, max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                        on_click=on_select,
                    )
                    for label, on_select in menu_items
                ],
            )
        )

    return ft.Container(
        on_click=on_pick,
        on_hover=lambda e: set_hovered(e.data),
        tooltip=full_path or "Нажмите, чтобы выбрать файл",
        bgcolor=p.card_hover if hovered else ft.Colors.TRANSPARENT,
        border=ft.Border.all(1, p.hairline if not hovered else ft.Colors.with_opacity(0.4, ft.Colors.PRIMARY)),
        border_radius=theme.RADIUS_CONTROL,
        padding=ft.Padding.symmetric(horizontal=18, vertical=16),
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        content=ft.Row(
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=25, color=ft.Colors.PRIMARY if ok else ft.Colors.OUTLINE),
                ft.Column(
                    spacing=3,
                    expand=True,
                    tight=True,
                    controls=[
                        ft.Text(title, size=16, weight=ft.FontWeight.W_600),
                        ft.Text(
                            value or "нажмите, чтобы выбрать",
                            size=14,
                            italic=value is None,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
                *trailing,
            ],
        ),
    )
