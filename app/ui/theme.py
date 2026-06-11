"""Корпоративная тема ГУУ: палитра брендбука и фабрика :func:`build_theme`.

Цвета — из официального «Руководства по использованию фирменного стиля» ГУУ
(guu.ru, основная и дополнительная палитры): синий Pantone 654C, красный
Pantone 199C, серые Cool Gray. Тема только светлая (решение пользователя).

Компоненты приложения используют семантические токены ``ft.Colors.*``
(PRIMARY, ERROR, SURFACE_CONTAINER_LOW...) — они подхватывают переопределения
из :class:`ft.ColorScheme` ниже. «Сырые» hex живут только в этом модуле
и в статусных стилях (:mod:`app.ui.components.status_badge`).
"""

from __future__ import annotations

import flet as ft

# --- основная палитра брендбука ГУУ --- #
GUU_BLUE = "#20426C"  # фирменный синий (Pantone 654C)
GUU_RED = "#E51E40"  # фирменный красный (Pantone 199C) — ошибки и расхождения
GUU_GRAY_LIGHT = "#DDDDDA"  # Cool Gray 1
GUU_GRAY = "#99999B"  # Cool Gray 7
GUU_GRAY_DARK = "#55565B"  # Cool Gray 11

# --- дополнительная палитра брендбука --- #
GUU_BLUE_BRIGHT = "#2858A5"  # Pantone 7455C — градиент шапки, secondary
GUU_BLUE_SKY = "#71A3D8"  # Pantone 659C — tertiary

# --- статусные цвета (не из брендбука, согласованы с палитрой) --- #
OK_GREEN = "#1E7D43"
OK_GREEN_BG = "#E3F1E8"
WARN_ORANGE = "#B25E09"
WARN_ORANGE_BG = "#FBEEDC"
ERROR_RED_DARK = "#7A1024"  # текст на светло-красной подложке
ERROR_RED_BG = "#FCE5EA"  # светлая подложка под фирменный красный

# --- голубоватые тона поверхностей (выведены из фирменного синего) --- #
SURFACE_TINT_LOW = "#F4F6FA"  # фон секций, полос зебры
SURFACE_TINT = "#E9EEF5"  # фон заголовка таблицы


def build_theme() -> ft.Theme:
    """Собирает светлую тему приложения с фирменными цветами ГУУ.

    ``color_scheme_seed`` даёт согласованные производные роли MD3,
    а :class:`ft.ColorScheme` поверх прибивает ключевые роли ровно
    к кодам брендбука (primary, error, контуры, поверхности).
    """
    return ft.Theme(
        color_scheme_seed=GUU_BLUE,
        color_scheme=ft.ColorScheme(
            primary=GUU_BLUE,
            on_primary="#FFFFFF",
            secondary=GUU_BLUE_BRIGHT,
            tertiary=GUU_BLUE_SKY,
            error=GUU_RED,
            on_error="#FFFFFF",
            error_container=ERROR_RED_BG,
            on_error_container=ERROR_RED_DARK,
            outline=GUU_GRAY,
            outline_variant=GUU_GRAY_LIGHT,
            surface="#FFFFFF",
            surface_tint=GUU_BLUE,
            surface_container_low=SURFACE_TINT_LOW,
            surface_container=SURFACE_TINT_LOW,
            surface_container_highest=SURFACE_TINT,
            on_surface_variant=GUU_GRAY_DARK,
        ),
        scrollbar_theme=ft.ScrollbarTheme(
            thumb_visibility=True,
            thickness=6,
            radius=3,
            thumb_color=ft.Colors.with_opacity(0.35, GUU_BLUE),
        ),
        progress_indicator_theme=ft.ProgressIndicatorTheme(
            color=GUU_BLUE_BRIGHT,
            linear_track_color=SURFACE_TINT,
            linear_min_height=8,
            border_radius=4,
        ),
        divider_color=GUU_GRAY_LIGHT,
    )
