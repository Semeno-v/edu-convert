"""Шапка приложения: марка, режим оформления, справка и версия.

Тонкая полоса с фирменным градиентом ГУУ. Держит только глобальные действия —
всё, что относится к работе с документами, живёт в рабочей области.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import flet as ft

from app.ui import theme


@ft.component
def ThemeToggle(
    dark: bool,
    on_toggle: Callable[[ft.Event[ft.Control]], None],
    on_accent: str,
) -> ft.Control:
    """Переключатель темы: солнце и месяц меняются местами через полуоборот.

    Иконка не подменяется рывком: кнопка доворачивается на 180°, а старый
    символ уезжает вглубь, пока новый выплывает — тот же жест, что и у
    перекраски интерфейса, поэтому смена темы читается как одно движение.
    """
    return ft.Container(
        width=46,
        height=46,
        border_radius=theme.RADIUS_PILL,
        alignment=ft.Alignment.CENTER,
        tooltip="Светлая тема" if dark else "Тёмная тема",
        on_click=on_toggle,
        bgcolor=ft.Colors.with_opacity(0.22 if dark else 0.12, ft.Colors.WHITE),
        animate=theme.theme_motion(),
        rotate=ft.Rotate(math.pi if dark else 0.0),
        animate_rotation=theme.theme_motion(),
        content=ft.AnimatedSwitcher(
            duration=ft.Duration(milliseconds=theme.THEME_MOTION_MS),
            switch_in_curve=ft.AnimationCurve.EASE_OUT_BACK,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
            transition=ft.AnimatedSwitcherTransition.SCALE,
            content=ft.Icon(
                ft.Icons.LIGHT_MODE_ROUNDED if dark else ft.Icons.DARK_MODE_ROUNDED,
                key="sun" if dark else "moon",
                size=24,
                color=on_accent,
            ),
        ),
    )


@ft.component
def TopBar(
    version: str,
    dark: bool,
    on_toggle_theme: Callable[[ft.Event[ft.Control]], None],
    on_help: Callable[[ft.Event[ft.Control]], None],
    gutter: int = theme.SPACE_LG,
) -> ft.Control:
    """Верхняя панель приложения; ``gutter`` выравнивает её с рабочей областью."""
    p = theme.palette(dark)
    return ft.Container(
        height=theme.TOP_BAR_HEIGHT,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT,
            colors=[p.accent_from, p.accent_to],
        ),
        animate=theme.theme_motion(),
        padding=ft.Padding.symmetric(horizontal=gutter),
        content=ft.Row(
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=46,
                    height=46,
                    border_radius=15,
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.AUTO_AWESOME_MOTION_ROUNDED, size=26,
                                    color=p.on_accent),
                ),
                ft.Column(
                    spacing=1,
                    tight=True,
                    expand=True,
                    controls=[
                        ft.Text("EduConvert", size=21, weight=ft.FontWeight.BOLD,
                                color=p.on_accent),
                        ft.Text(
                            "РПД и ФОС → форма 2026",
                            size=14,
                            color=ft.Colors.with_opacity(0.75, p.on_accent),
                        ),
                    ],
                ),
                ThemeToggle(dark, on_toggle_theme, p.on_accent),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE_ROUNDED,
                    icon_size=24,
                    icon_color=ft.Colors.with_opacity(0.85, p.on_accent),
                    tooltip="Как это работает (F1)",
                    on_click=on_help,
                ),
                ft.Container(
                    border_radius=theme.RADIUS_PILL,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=5),
                    bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.WHITE),
                    content=ft.Text(f"v{version}", size=13,
                                    color=ft.Colors.with_opacity(0.9, p.on_accent)),
                ),
            ],
        ),
    )
