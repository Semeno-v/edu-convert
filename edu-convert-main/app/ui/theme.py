"""Визуальный язык EduConvert: палитра ГУУ в современной оболочке.

Базовые цвета — из «Руководства по использованию фирменного стиля» ГУУ
(guu.ru): синий Pantone 654C, красный Pantone 199C, серые Cool Gray. Поверх
них построены две согласованные схемы — светлая и тёмная (:func:`build_theme`),
плюс токены, которые нельзя выразить через ``ft.ColorScheme``: статусные цвета,
градиенты шапки, радиусы, тени и типографика.

Компоненты обращаются к семантическим токенам ``ft.Colors.*``
(PRIMARY, SURFACE_CONTAINER, ON_SURFACE_VARIANT…) — они автоматически
подхватывают активную схему. «Сырые» цвета для статусов берутся из
:func:`palette`, которая возвращает вариант под текущий режим.
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

# --------------------------------------------------------------------------- #
#  Фирменная палитра ГУУ
# --------------------------------------------------------------------------- #
GUU_BLUE = "#20426C"  # Pantone 654C — основной
GUU_BLUE_BRIGHT = "#2858A5"  # Pantone 7455C
GUU_BLUE_SKY = "#71A3D8"  # Pantone 659C
GUU_RED = "#E51E40"  # Pantone 199C
GUU_GRAY_LIGHT = "#DDDDDA"  # Cool Gray 1
GUU_GRAY = "#99999B"  # Cool Gray 7
GUU_GRAY_DARK = "#55565B"  # Cool Gray 11

# --------------------------------------------------------------------------- #
#  Геометрия и типографика
# --------------------------------------------------------------------------- #
RADIUS_CARD = 18
RADIUS_CONTROL = 12
RADIUS_PILL = 999

SPACE_XS = 6
SPACE_SM = 10
SPACE_MD = 16
SPACE_LG = 22

TOP_BAR_HEIGHT = 62
ACTION_BAR_HEIGHT = 78

# Предел ширины рабочей области: на 4K-мониторе строки не должны
# расползаться на весь экран.
MAX_CONTENT_WIDTH = 1440


@dataclass(frozen=True)
class Palette:
    """Токены, не выражаемые через ``ColorScheme`` (статусы, фоны, тени)."""

    dark: bool

    # статусы
    ok: str
    ok_bg: str
    warn: str
    warn_bg: str
    danger: str
    danger_bg: str

    # поверхности и линии
    canvas: str
    card: str
    card_hover: str
    hairline: str
    shadow: str

    # акценты шапки
    accent_from: str
    accent_to: str
    on_accent: str


_LIGHT = Palette(
    dark=False,
    ok="#0F7B4F",
    ok_bg="#E4F4EC",
    warn="#9A5B00",
    warn_bg="#FCF0DC",
    danger=GUU_RED,
    danger_bg="#FCE5EA",
    canvas="#F5F7FB",
    card="#FFFFFF",
    card_hover="#F8FAFD",
    hairline="#E4E8F0",
    shadow="#0F1D33",
    accent_from=GUU_BLUE,
    accent_to=GUU_BLUE_BRIGHT,
    on_accent="#FFFFFF",
)

_DARK = Palette(
    dark=True,
    ok="#4ADE99",
    ok_bg="#12291F",
    warn="#FBBF5C",
    warn_bg="#2A2113",
    danger="#FF6B84",
    danger_bg="#2E1620",
    canvas="#0E131C",
    card="#161C28",
    card_hover="#1B2331",
    hairline="#27303F",
    shadow="#000000",
    accent_from="#16233A",
    accent_to="#22406E",
    on_accent="#EAF1FF",
)


def palette(dark: bool = False) -> Palette:
    """Возвращает набор токенов под светлый или тёмный режим."""
    return _DARK if dark else _LIGHT


# --------------------------------------------------------------------------- #
#  Тени
# --------------------------------------------------------------------------- #
def soft_shadow(dark: bool = False, *, strong: bool = False) -> ft.BoxShadow:
    """Мягкая рассеянная тень карточек (в тёмной теме — заметно слабее)."""
    p = palette(dark)
    opacity = (0.30 if strong else 0.22) if dark else (0.10 if strong else 0.05)
    return ft.BoxShadow(
        blur_radius=28 if strong else 18,
        spread_radius=0,
        color=ft.Colors.with_opacity(opacity, p.shadow),
        offset=ft.Offset(0, 8 if strong else 4),
    )


# --------------------------------------------------------------------------- #
#  Тема
# --------------------------------------------------------------------------- #
def _light_scheme() -> ft.ColorScheme:
    p = _LIGHT
    return ft.ColorScheme(
        primary=GUU_BLUE,
        on_primary="#FFFFFF",
        primary_container="#DCE7F7",
        on_primary_container="#12294A",
        secondary=GUU_BLUE_BRIGHT,
        on_secondary="#FFFFFF",
        secondary_container="#E7EEFA",
        on_secondary_container="#16294A",
        tertiary=GUU_BLUE_SKY,
        error=GUU_RED,
        on_error="#FFFFFF",
        error_container=p.danger_bg,
        on_error_container="#7A1024",
        surface=p.card,
        on_surface="#101828",
        on_surface_variant="#5B6579",
        surface_container_lowest="#FFFFFF",
        surface_container_low="#FAFBFE",
        surface_container=p.canvas,
        surface_container_high="#EDF1F8",
        surface_container_highest="#E6ECF6",
        surface_tint=GUU_BLUE,
        outline=GUU_GRAY,
        outline_variant=p.hairline,
        shadow=p.shadow,
        inverse_surface="#1B2434",
        on_inverse_surface="#F1F4FA",
        inverse_primary=GUU_BLUE_SKY,
    )


def _dark_scheme() -> ft.ColorScheme:
    p = _DARK
    return ft.ColorScheme(
        primary="#8FB6EC",
        on_primary="#0C1B31",
        primary_container="#1E3557",
        on_primary_container="#D6E4FB",
        secondary="#9FC0F0",
        on_secondary="#0C1B31",
        secondary_container="#1C2F4D",
        on_secondary_container="#D8E5FA",
        tertiary=GUU_BLUE_SKY,
        error=p.danger,
        on_error="#3A0A15",
        error_container=p.danger_bg,
        on_error_container="#FFD9E0",
        surface=p.card,
        on_surface="#E6EBF4",
        on_surface_variant="#9AA6BA",
        surface_container_lowest="#0B1017",
        surface_container_low="#131A25",
        surface_container=p.canvas,
        surface_container_high="#1D2533",
        surface_container_highest="#232C3C",
        surface_tint="#8FB6EC",
        outline="#5C6779",
        outline_variant=p.hairline,
        shadow="#000000",
        inverse_surface="#E6EBF4",
        on_inverse_surface="#161C28",
        inverse_primary=GUU_BLUE,
    )


def _text_theme(on_surface: str) -> ft.TextTheme:
    """Типографика приложения.

    Цвет проставляется каждому стилю явно: если оставить его пустым, Flutter
    берёт белый текст по умолчанию, и в светлой теме заголовки исчезают.
    """
    sizes = {
        "display_large": 40, "display_medium": 34, "display_small": 28,
        "headline_large": 26, "headline_medium": 24, "headline_small": 22,
        "title_large": 18, "title_medium": 15, "title_small": 13,
        "body_large": 14, "body_medium": 13, "body_small": 12,
        "label_large": 13, "label_medium": 12, "label_small": 11,
    }
    bold = {"display_large", "display_medium", "display_small",
            "headline_large", "headline_medium", "headline_small"}
    semibold = {"title_large", "title_medium", "title_small",
                "label_large", "label_medium", "label_small"}

    def style(name: str) -> ft.TextStyle:
        if name in bold:
            weight, spacing = ft.FontWeight.BOLD, -0.4
        elif name in semibold:
            weight, spacing = ft.FontWeight.W_600, -0.1
        else:
            weight, spacing = ft.FontWeight.NORMAL, 0.0
        return ft.TextStyle(size=sizes[name], weight=weight,
                            letter_spacing=spacing, color=on_surface)

    return ft.TextTheme(**{name: style(name) for name in sizes})


def build_theme(dark: bool = False) -> ft.Theme:
    """Собирает тему приложения для светлого или тёмного режима."""
    p = palette(dark)
    scheme = _dark_scheme() if dark else _light_scheme()
    return ft.Theme(
        color_scheme_seed=GUU_BLUE,
        color_scheme=scheme,
        visual_density=ft.VisualDensity.COMPACT,
        scaffold_bgcolor=p.canvas,
        divider_color=p.hairline,
        card_theme=ft.CardTheme(
            elevation=0,
            color=p.card,
            shape=ft.RoundedRectangleBorder(radius=RADIUS_CARD),
        ),
        scrollbar_theme=ft.ScrollbarTheme(
            thumb_visibility=False,
            thickness=6,
            radius=3,
            thumb_color=ft.Colors.with_opacity(0.28, scheme.on_surface_variant),
        ),
        progress_indicator_theme=ft.ProgressIndicatorTheme(
            color=scheme.primary,
            linear_track_color=ft.Colors.with_opacity(0.18, scheme.primary),
            linear_min_height=6,
            border_radius=RADIUS_PILL,
        ),
        tooltip_theme=ft.TooltipTheme(
            text_style=ft.TextStyle(size=12, color=scheme.on_inverse_surface),
            decoration=ft.BoxDecoration(
                bgcolor=ft.Colors.with_opacity(0.95, scheme.inverse_surface),
                border_radius=ft.BorderRadius.all(8),
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            wait_duration=ft.Duration(milliseconds=350),
        ),
        snackbar_theme=ft.SnackBarTheme(
            behavior=ft.SnackBarBehavior.FLOATING,
            bgcolor=scheme.inverse_surface,
            content_text_style=ft.TextStyle(size=13, color=scheme.on_inverse_surface),
            shape=ft.RoundedRectangleBorder(radius=RADIUS_CONTROL),
        ),
        text_theme=_text_theme(scheme.on_surface),
    )
