"""Шапка приложения: марка, режим оформления, справка и версия.

Тонкая полоса с фирменным градиентом ГУУ. Держит только глобальные действия —
всё, что относится к работе с документами, живёт в рабочей области.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.ui import theme


@ft.component
def TopBar(
    version: str,
    dark: bool,
    on_toggle_theme: Callable[[ft.Event[ft.Control]], None],
    on_help: Callable[[ft.Event[ft.Control]], None],
) -> ft.Control:
    """Верхняя панель приложения."""
    p = theme.palette(dark)
    return ft.Container(
        height=theme.TOP_BAR_HEIGHT,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT,
            colors=[p.accent_from, p.accent_to],
        ),
        padding=ft.Padding.symmetric(horizontal=theme.SPACE_LG),
        content=ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=34,
                    height=34,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.AUTO_AWESOME_MOTION_ROUNDED, size=19,
                                    color=p.on_accent),
                ),
                ft.Column(
                    spacing=0,
                    tight=True,
                    expand=True,
                    controls=[
                        ft.Text("EduConvert", size=16, weight=ft.FontWeight.BOLD,
                                color=p.on_accent,
                                style=ft.TextStyle(letter_spacing=-0.2)),
                        ft.Text(
                            "РПД и ФОС → форма 2026",
                            size=11,
                            color=ft.Colors.with_opacity(0.75, p.on_accent),
                        ),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.LIGHT_MODE_ROUNDED if dark else ft.Icons.DARK_MODE_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.with_opacity(0.85, p.on_accent),
                    tooltip="Светлая тема" if dark else "Тёмная тема",
                    on_click=on_toggle_theme,
                ),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.with_opacity(0.85, p.on_accent),
                    tooltip="Как это работает (F1)",
                    on_click=on_help,
                ),
                ft.Container(
                    border_radius=theme.RADIUS_PILL,
                    padding=ft.Padding.symmetric(horizontal=9, vertical=3),
                    bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.WHITE),
                    content=ft.Text(f"v{version}", size=10,
                                    color=ft.Colors.with_opacity(0.9, p.on_accent)),
                ),
            ],
        ),
    )
