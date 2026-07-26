"""Экран результатов: сводка, расхождения и статусы по файлам.

Три представления переключаются сегментированной кнопкой, чтобы длинные
таблицы не соревновались за место на экране. Расхождения и файлы фильтруются
живым поиском по дисциплине, полю и имени файла. Списки виртуализированы
(:class:`ft.ListView`) — партия в сотню документов не роняет FPS.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.core.models import FileResult, FileStatus
from app.ui import theme
from app.ui.components.status_badge import Pill, StatCard, StatusBadge, status_colors

SUMMARY = "summary"
DIFFS = "diffs"
FILES = "files"


def _matches(query: str, *fields: str) -> bool:
    q = query.strip().lower()
    return not q or any(q in (f or "").lower() for f in fields)


def _diff_row(index: int, subject: str, field: str, old: str, new: str, dark: bool) -> ft.Control:
    p = theme.palette(dark)
    return ft.Container(
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW if index % 2 else None,
        padding=ft.Padding.symmetric(horizontal=12, vertical=9),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(subject, size=12, expand=3, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS, tooltip=subject),
                ft.Text(field, size=12, expand=4, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS, tooltip=field),
                ft.Row(
                    expand=3,
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(old, size=12, color=p.danger,
                                style=ft.TextStyle(
                                    decoration=ft.TextDecoration.LINE_THROUGH)),
                        ft.Icon(ft.Icons.ARROW_RIGHT_ALT_ROUNDED, size=15,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(new, size=12, color=p.ok, weight=ft.FontWeight.W_700),
                    ],
                ),
            ],
        ),
    )


def _file_row(result: FileResult, dark: bool) -> ft.Control:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=1,
                    expand=5,
                    tight=True,
                    controls=[
                        ft.Text(result.filename, size=12.5, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                tooltip=result.filename),
                        ft.Text(result.index or "индекс не определён", size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                ),
                ft.Container(StatusBadge(result.status, dark), expand=2),
                ft.Text(result.message or "—", size=11, expand=5, max_lines=2,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        overflow=ft.TextOverflow.ELLIPSIS, tooltip=result.message),
            ],
        ),
    )


def _empty(text: str) -> ft.Control:
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=28),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.INBOX_ROUNDED, size=28, color=ft.Colors.OUTLINE),
                ft.Text(text, size=12, italic=True, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )


def _framed(content: ft.Control, dark: bool) -> ft.Control:
    return ft.Container(
        border=ft.Border.all(1, theme.palette(dark).hairline),
        border_radius=theme.RADIUS_CONTROL,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=content,
    )


@ft.component
def ResultsView(
    results: list[FileResult],
    on_download: Callable[[ft.Event[ft.Control]], None],
    on_back: Callable[[ft.Event[ft.Control]], None],
    dark: bool = False,
) -> ft.Control:
    """Панель результатов прогона с тремя представлениями."""
    tab, set_tab = ft.use_state(SUMMARY)
    query, set_query = ft.use_state("")
    p = theme.palette(dark)

    total = len(results)
    succeeded = sum(1 for r in results if r.status == FileStatus.SUCCESS)
    with_diffs = sum(1 for r in results if r.status == FileStatus.DISCREPANCY)
    failed = sum(1 for r in results if r.status == FileStatus.ERROR)
    diffs = [(r, d) for r in results for d in r.diffs]

    search = ft.TextField(
        value=query,
        hint_text="Поиск по дисциплине, полю или файлу…",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        dense=True,
        filled=True,
        border_radius=theme.RADIUS_CONTROL,
        border_color=p.hairline,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        text_size=13,
        on_change=lambda e: set_query(e.control.value),
    )

    if tab == SUMMARY:
        body: ft.Control = ft.Column(
            spacing=theme.SPACE_MD,
            controls=[
                ft.Row(
                    spacing=10,
                    controls=[
                        StatCard("Успешно", succeeded, total, p.ok, p.ok_bg,
                                 ft.Icons.CHECK_CIRCLE_ROUNDED),
                        StatCard("Расхождения", with_diffs, total, p.warn, p.warn_bg,
                                 ft.Icons.CHANGE_CIRCLE_ROUNDED),
                        StatCard("Ошибки", failed, total, p.danger, p.danger_bg,
                                 ft.Icons.ERROR_ROUNDED),
                    ],
                ),
                ft.Container(
                    bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                    border_radius=theme.RADIUS_CONTROL,
                    padding=ft.Padding.all(14),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16,
                                            color=ft.Colors.PRIMARY),
                                    ft.Text("Что внутри архива", size=13,
                                            weight=ft.FontWeight.W_600),
                                ],
                            ),
                            ft.Text(
                                f"{total} готовых документов по форме 2026 "
                                "и report.xlsx со всеми расхождениями. "
                                "Всё, что подставила конвертация, выделено жёлтым; "
                                "числа взяты из учебного плана.",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                    ),
                ),
            ],
        )
    elif tab == DIFFS:
        rows = [
            _diff_row(i, r.index or r.filename, d.field, d.old_value, d.new_value, dark)
            for i, (r, d) in enumerate(
                (r, d) for r, d in diffs
                if _matches(query, r.index, r.filename, d.field, d.old_value, d.new_value)
            )
        ]
        body = ft.Column(
            spacing=theme.SPACE_SM,
            controls=[
                search,
                _framed(
                    ft.ListView(controls=rows, height=300) if rows
                    else _empty("Расхождений не найдено"),
                    dark,
                ),
                ft.Text(
                    "Слева — значение из старого документа, справа — из учебного плана "
                    "(записано в новый файл).",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
        )
    else:
        rows = [
            _file_row(r, dark) for r in results
            if _matches(query, r.filename, r.index, r.message)
        ]
        body = ft.Column(
            spacing=theme.SPACE_SM,
            controls=[
                search,
                _framed(
                    ft.ListView(controls=rows, height=300) if rows
                    else _empty("Ничего не найдено"),
                    dark,
                ),
            ],
        )

    tabs = ft.SegmentedButton(
        selected=[tab],
        allow_empty_selection=False,
        show_selected_icon=False,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
            text_style=ft.TextStyle(size=12, weight=ft.FontWeight.W_600),
            padding=ft.Padding.symmetric(horizontal=10, vertical=12),
        ),
        segments=[
            ft.Segment(value=SUMMARY, label=ft.Text("Сводка"),
                       icon=ft.Icon(ft.Icons.DONUT_LARGE_ROUNDED, size=15)),
            ft.Segment(value=DIFFS, label=ft.Text(f"Расхождения · {len(diffs)}"),
                       icon=ft.Icon(ft.Icons.COMPARE_ARROWS_ROUNDED, size=15)),
            ft.Segment(value=FILES, label=ft.Text(f"Файлы · {total}"),
                       icon=ft.Icon(ft.Icons.FOLDER_COPY_OUTLINED, size=15)),
        ],
        on_change=lambda e: set_tab(next(iter(e.data), SUMMARY)),
    )

    failed_names = [r for r in results if r.status == FileStatus.ERROR]
    warning: list[ft.Control] = []
    if failed_names:
        warning.append(
            ft.Container(
                bgcolor=p.danger_bg,
                border_radius=theme.RADIUS_CONTROL,
                padding=ft.Padding.all(12),
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=16,
                                        color=p.danger),
                                ft.Text(f"Не обработано: {len(failed_names)}", size=12,
                                        weight=ft.FontWeight.W_600, color=p.danger),
                            ],
                        ),
                        ft.Text(
                            ", ".join(r.filename for r in failed_names[:4])
                            + ("…" if len(failed_names) > 4 else ""),
                            size=11,
                            color=p.danger,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
            )
        )

    return ft.Column(
        spacing=theme.SPACE_MD,
        controls=[
            ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        icon_size=18,
                        tooltip="Вернуться к настройке",
                        on_click=on_back,
                    ),
                    ft.Column(
                        spacing=1,
                        expand=True,
                        tight=True,
                        controls=[
                            ft.Text("Результаты конвертации", size=17,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.ON_SURFACE),
                            ft.Text(f"Обработано документов: {total}", size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    Pill(f"{succeeded} успешно", icon=ft.Icons.CHECK_ROUNDED,
                         fg=p.ok, bg=p.ok_bg, compact=True),
                    ft.FilledButton(
                        "Скачать .zip",
                        icon=ft.Icons.DOWNLOAD_ROUNDED,
                        on_click=on_download,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
                            padding=ft.Padding.symmetric(horizontal=16, vertical=18),
                        ),
                    ),
                ],
            ),
            tabs,
            *warning,
            body,
        ],
    )
