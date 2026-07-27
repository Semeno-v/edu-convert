"""Список добавленных исходников с живым статусом обработки.

Виртуализированный :class:`ft.ListView` с фиксированной высотой строки
(``item_extent``) — партии в 80+ файлов скроллятся без потери FPS.
Каждая строка показывает тип документа (РПД/ФОС), формат и текущее состояние:
в очереди, обрабатывается, готово, расхождения или ошибка. Hover — локальное
состояние строки, поэтому перерисовывается только она одна.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import flet as ft

from app.core.models import DocType
from app.ui import theme

_ROW_HEIGHT = 60
_MAX_LIST_HEIGHT = 460

# состояния строки
QUEUED = "queued"
RUNNING = "running"
DONE = "ok"
WARN = "warn"
FAILED = "err"


def _mark(state: str, dark: bool) -> ft.Control:
    """Индикатор состояния строки."""
    p = theme.palette(dark)
    if state == RUNNING:
        return ft.ProgressRing(width=20, height=20, stroke_width=2.2)
    icon, color = {
        DONE: (ft.Icons.CHECK_CIRCLE_ROUNDED, p.ok),
        WARN: (ft.Icons.CHANGE_CIRCLE_ROUNDED, p.warn),
        FAILED: (ft.Icons.ERROR_ROUNDED, p.danger),
        QUEUED: (ft.Icons.SCHEDULE_ROUNDED, ft.Colors.OUTLINE),
    }[state]
    return ft.Icon(icon, size=21, color=color)


@ft.component
def FileRow(
    path: Path,
    state: str,
    on_remove: Callable[[Path], None] | None,
    dark: bool = False,
    unsupported: bool = False,
) -> ft.Control:
    """Строка одного файла: тип, имя, формат, состояние и удаление."""
    hovered, set_hovered = ft.use_state(False)
    p = theme.palette(dark)
    # тот же разбор имени, что и в оркестраторе: бейдж обязан совпадать
    # с шаблоном, по которому файл будет собран
    kind = DocType.from_filename(path.name).value

    trailing: list[ft.Control] = []
    if unsupported:
        trailing.append(
            ft.Icon(
                ft.Icons.WARNING_AMBER_ROUNDED,
                size=21,
                color=p.warn,
                tooltip="Формат .doc на этой системе не конвертируется",
            )
        )
    trailing.append(_mark(state, dark))
    if on_remove is not None:
        trailing.append(
            ft.IconButton(
                icon=ft.Icons.CLOSE_ROUNDED,
                icon_size=20,
                icon_color=(
                    ft.Colors.ON_SURFACE_VARIANT if hovered
                    else ft.Colors.with_opacity(0.30, ft.Colors.ON_SURFACE_VARIANT)
                ),
                tooltip="Убрать из списка",
                # file=path фиксирует значение: лямбда в цикле без этого
                # захватила бы последний элемент списка
                on_click=lambda e, file=path: on_remove(file),
            )
        )

    return ft.Container(
        height=_ROW_HEIGHT,
        padding=ft.Padding.only(left=14, right=8),
        border_radius=theme.RADIUS_CONTROL,
        bgcolor=p.card_hover if hovered else None,
        on_hover=lambda e: set_hovered(e.data),
        content=ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=46,
                    border_radius=9,
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                    padding=ft.Padding.symmetric(vertical=5),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(kind, size=13, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.PRIMARY),
                ),
                ft.Text(
                    path.name,
                    size=16,
                    expand=True,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=str(path),
                ),
                ft.Text(path.suffix.lower().lstrip("."), size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT),
                *trailing,
            ],
        ),
    )


@ft.component
def FileList(
    files: list[Path],
    states: dict[str, str],
    on_remove: Callable[[Path], None] | None = None,
    dark: bool = False,
    doc_unsupported: bool = False,
    fill: bool = False,
) -> ft.Control:
    """Список файлов; ``fill`` — растянуть на всю свободную высоту панели."""
    if not files:
        return ft.Container(
            expand=fill,
            padding=ft.Padding.symmetric(vertical=theme.SPACE_LG),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                "Пока ничего не добавлено",
                size=15,
                italic=True,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        )
    return ft.ListView(
        expand=fill,
        height=None if fill else min(_ROW_HEIGHT * len(files) + 8, _MAX_LIST_HEIGHT),
        item_extent=_ROW_HEIGHT,
        padding=ft.Padding.symmetric(vertical=4),
        controls=[
            FileRow(
                file,
                states.get(file.name, QUEUED),
                on_remove,
                dark,
                doc_unsupported and file.suffix.lower() == ".doc",
            )
            for file in files
        ],
    )
