"""Справка, которая вырастает из кнопки «?» и втягивается обратно в неё.

Обычный :class:`ft.AlertDialog` здесь не подходит: Flutter раскрывает его
из центра экрана, и связь «нажал вопросик — появилась подсказка» теряется.
Поэтому панель собрана вручную поверх :class:`ft.Stack`, а точка роста задана
через ``ft.Scale(alignment=TOP_RIGHT)``: верхний правый угол карточки
закреплён ровно под кнопкой в шапке и остаётся неподвижным, пока остальное
разворачивается вниз-влево. При закрытии всё схлопывается в ту же точку.

Анимация живёт на четырёх фазах. ``ENTER`` нужен потому, что Flutter
анимирует только *изменение* свойства: карточку сначала монтируют сжатой,
и лишь следующим кадром переводят в ``OPEN``. Симметрично ``EXIT`` держит
её в дереве, пока идёт обратный ход, — иначе она исчезла бы мгновенно.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.ui import theme

CLOSED = "closed"
ENTER = "enter"
OPEN = "open"
EXIT = "exit"

ENTER_MS = 360
EXIT_MS = 420
SCRIM_EXIT_MS = 260

ENTER_CURVE = ft.AnimationCurve.EASE_OUT_CUBIC

# Обратный ход разложен на три несинхронных движения — иначе карточка просто
# растворяется и «полёта в кнопку» не видно:
#   * масштаб идёт по ``EASE_IN_BACK``: перед схлопыванием карточка чуть
#     набирает размер — короткий замах, из-за которого уход читается как жест,
#     а не как обрыв;
#   * прозрачность — по ``EASE_IN_EXPO``: значение держится у единицы почти всю
#     дорогу и падает только в самом конце, поэтому карточка остаётся видимой,
#     пока сжимается, и гаснет уже в точке кнопки;
#   * затемнение снимается вдвое быстрее самой карточки, чтобы она летела
#     к «?» на фоне живого интерфейса, а не мутного стекла.
EXIT_SCALE_CURVE = ft.AnimationCurve.EASE_IN_BACK
EXIT_FADE_CURVE = ft.AnimationCurve.EASE_IN_EXPO
SCRIM_EXIT_CURVE = ft.AnimationCurve.EASE_OUT_CUBIC

# Сколько держать карточку в дереве после команды закрыть: длительность ухода
# плюс запас на кадр, иначе хвост анимации обрежется.
EXIT_HOLD_S = (EXIT_MS + 60) / 1000

SHEET_WIDTH = 560

# Расстояние от правого края окна до кнопки «?»: за ней в шапке стоит только
# пилюля с версией, поэтому смещение складывается из отступа рабочей области,
# ширины пилюли и интервала между ними.
_ANCHOR_OFFSET = 88


def _line(icon: str, text: str) -> ft.Control:
    return ft.Row(
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Icon(icon, size=21, color=ft.Colors.PRIMARY),
            ft.Text(text, size=15, expand=True),
        ],
    )


def _key(combo: str, text: str) -> ft.Control:
    return ft.Row(
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                width=126,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                border_radius=9,
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                content=ft.Text(combo, size=14, weight=ft.FontWeight.W_600),
            ),
            ft.Text(text, size=15, expand=True),
        ],
    )


def _content(on_close: Callable[[ft.Event[ft.Control]], None]) -> ft.Control:
    return ft.Column(
        tight=True,
        spacing=theme.SPACE_MD,
        controls=[
            ft.Row(
                spacing=theme.SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text("Как это работает", size=23, weight=ft.FontWeight.BOLD,
                            expand=True, color=ft.Colors.ON_SURFACE),
                    ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=22,
                                  tooltip="Закрыть (Esc)", on_click=on_close),
                ],
            ),
            _line(ft.Icons.TABLE_VIEW_ROUNDED,
                  "Числа (зачётные единицы, часы, семестры) берутся из учебного "
                  "плана — он единственный источник истины."),
            _line(ft.Icons.DESCRIPTION_OUTLINED,
                  "Текстовые блоки (литература, темы, оценочные средства) "
                  "переносятся из старых РПД и ФОС."),
            _line(ft.Icons.FORMAT_PAINT_OUTLINED,
                  "Всё подставленное конвертацией выделяется жёлтым, "
                  "старые числа попадают только в отчёт о расхождениях."),
            ft.Divider(),
            _key("Ctrl + O", "выбрать файлы"),
            _key("Ctrl + D", "добавить папку"),
            _key("Ctrl + V", "вставить файлы из буфера"),
            _key("Ctrl + Enter", "запустить конвертацию"),
            _key("Ctrl + L", "очистить список"),
            _key("Esc", "закрыть справку"),
        ],
    )


@ft.component
def HelpSheet(
    phase: str,
    on_close: Callable[[ft.Event[ft.Control]], None],
    dark: bool = False,
    gutter: int = theme.SPACE_LG,
) -> ft.Control:
    """Слой справки поверх приложения; ``phase`` управляет анимацией."""
    p = theme.palette(dark)
    shown = phase == OPEN
    entering = phase in (ENTER, OPEN)

    scale_motion = ft.Animation(
        ENTER_MS if entering else EXIT_MS,
        ENTER_CURVE if entering else EXIT_SCALE_CURVE,
    )
    fade_motion = ft.Animation(
        ENTER_MS if entering else EXIT_MS,
        ENTER_CURVE if entering else EXIT_FADE_CURVE,
    )
    scrim_motion = ft.Animation(
        ENTER_MS if entering else SCRIM_EXIT_MS,
        ENTER_CURVE if entering else SCRIM_EXIT_CURVE,
    )

    scrim = ft.Container(
        expand=True,
        # затемнение намеренно лёгкое: кнопка «?» должна остаться различимой,
        # иначе теряется точка, из которой карточка выросла
        bgcolor=ft.Colors.with_opacity(0.40, "#070B12"),
        blur=ft.Blur(5, 5),
        opacity=1.0 if shown else 0.0,
        animate_opacity=scrim_motion,
        on_click=on_close,
    )

    sheet = ft.Container(
        key="help-sheet",
        right=gutter + _ANCHOR_OFFSET,
        top=theme.TOP_BAR_HEIGHT - 6,
        width=SHEET_WIDTH,
        bgcolor=p.card,
        border=ft.Border.all(1, p.hairline),
        border_radius=theme.RADIUS_CARD,
        shadow=theme.soft_shadow(dark, strong=True),
        padding=ft.Padding.all(theme.SPACE_LG),
        # угол под кнопкой «?» неподвижен — из него и разворачивается карточка
        scale=ft.Scale(scale=1.0 if shown else 0.0,
                       alignment=ft.Alignment.TOP_RIGHT),
        animate_scale=scale_motion,
        opacity=1.0 if shown else 0.0,
        animate_opacity=fade_motion,
        content=_content(on_close),
    )

    # Форма дерева обязана быть одинаковой во всех фазах. Любое изменение
    # структуры (например, ``ignore_interactions``, который оборачивает
    # содержимое в ``IgnorePointer``) заставляет Flutter пересоздать элемент —
    # карточка монтируется сразу в конечном состоянии, и обратный ход
    # не проигрывается вовсе. Клики на уходе гасить не нужно: ``close_help``
    # игнорирует повторные вызовы, пока фаза не ``ENTER``/``OPEN``.
    return ft.Container(
        expand=True,
        content=ft.Stack(expand=True, controls=[scrim, sheet]),
    )
