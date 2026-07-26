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

from app.ui import theme

_ROW_HEIGHT = 44
_MAX_LIST_HEIGHT = 320

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
        return ft.ProgressRing(width=15, height=15, stroke_width=2)
    icon, color = {
        DONE: (ft.Icons.CHECK_CIRCLE_ROUNDED, p.ok),
        WARN: (ft.Icons.CHANGE_CIRCLE_ROUNDED, p.warn),
        FAILED: (ft.Icons.ERROR_ROUNDED, p.danger),
        QUEUED: (ft.Icons.SCHEDULE_ROUNDED, ft.Colors.OUTLINE),
    }[state]
    return ft.Icon(icon, size=16, color=color)


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
    lowered = path.name.lower()
    kind = "ФОС" if ("фос" in lowered or "fos" in lowered) else "РПД"

    trailing: list[ft.Control] = []
    if unsupported:
        trailing.append(
            ft.Icon(
                ft.Icons.WARNING_AMBER_ROUNDED,
                size=16,
                color=p.warn,
                tooltip="Формат .doc на этой системе не конвертируется",
            )
        )
    trailing.append(_mark(state, dark))
    if on_remove is not None:
        trailing.append(
            ft.IconButton(
                icon=ft.Icons.CLOSE_ROUNDED,
                icon_size=15,
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
        padding=ft.Padding.only(left=10, right=4),
        border_radius=10,
        bgcolor=p.card_hover if hovered else None,
        on_hover=lambda e: set_hovered(e.data),
        content=ft.Row(
            spacing=9,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=34,
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                    padding=ft.Padding.symmetric(vertical=3),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(kind, size=10, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.PRIMARY),
                ),
                ft.Text(
                    path.name,
                    size=13,
                    expand=True,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=str(path),
                ),
                ft.Text(path.suffix.lower().lstrip("."), size=10,
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
) -> ft.Control:
    """Список файлов; пустой — с деликатной заглушкой."""
    if not files:
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=18),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                "Пока ничего не добавлено",
                size=12,
                italic=True,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        )
    return ft.ListView(
        height=min(_ROW_HEIGHT * len(files) + 8, _MAX_LIST_HEIGHT),
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
