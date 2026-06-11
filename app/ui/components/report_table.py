"""Виртуализированная таблица результатов и расхождений (зона 4, ТЗ §5, §8).

Использует :class:`ft.ListView` для предотвращения падения FPS на больших
объёмах данных. Над таблицей — сводка-пилюли по статусам; дифф-строки
с зеброй и подсветкой: старое значение зачёркнуто фирменным красным,
новое — зелёным. Ненайденные в Базе дисциплины — отдельным блоком.
"""

from __future__ import annotations

import flet as ft

from app.core.models import FileResult, FileStatus
from app.ui import theme
from app.ui.components.status_badge import CountPill, StatusBadge


def _header_row() -> ft.Control:
    def cell(text: str, flex: int) -> ft.Control:
        return ft.Container(
            ft.Text(text, weight=ft.FontWeight.BOLD, size=12),
            expand=flex,
            padding=ft.Padding.symmetric(horizontal=8, vertical=7),
        )

    return ft.Container(
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        content=ft.Row(
            [cell("Дисциплина", 3), cell("Поле", 3), cell("Было (старый файл)", 2),
             cell("Стало (База)", 2)],
            spacing=0,
        ),
    )


def _diff_row(row_index: int, index: str, field: str, old: str, new: str) -> ft.Control:
    def cell(content: ft.Control, flex: int) -> ft.Control:
        return ft.Container(
            content, expand=flex, padding=ft.Padding.symmetric(horizontal=8, vertical=6)
        )

    # строки-расхождения всегда слегка красные; зебра — чередованием тона
    tint = 0.05 if row_index % 2 == 0 else 0.10
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(tint, theme.GUU_RED),
        content=ft.Row(
            spacing=0,
            controls=[
                cell(ft.Text(index, size=12), 3),
                cell(ft.Text(field, size=12), 3),
                cell(
                    ft.Text(
                        old,
                        size=12,
                        color=theme.GUU_RED,
                        style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH),
                    ),
                    2,
                ),
                cell(
                    ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(
                                ft.Icons.ARROW_FORWARD,
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                new,
                                size=12,
                                color=theme.OK_GREEN,
                                weight=ft.FontWeight.W_600,
                            ),
                        ],
                    ),
                    2,
                ),
            ],
        ),
    )


def _status_row(result: FileResult) -> ft.Control:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=5),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(
                    f"{result.index or result.filename}",
                    size=12,
                    expand=3,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=result.filename,
                ),
                ft.Container(StatusBadge(result.status), expand=2),
                ft.Text(
                    result.message,
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    expand=4,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=result.message,
                ),
            ],
        ),
    )


@ft.component
def ReportTable(results: list[FileResult]) -> ft.Control:
    """Сводка статусов + список расхождений + блок «не найдено в БД»."""
    succeeded = sum(1 for r in results if r.status == FileStatus.SUCCESS)
    with_diffs = sum(1 for r in results if r.status == FileStatus.DISCREPANCY)
    failed = sum(1 for r in results if r.status == FileStatus.ERROR)
    not_found = [r for r in results if r.status == FileStatus.ERROR]

    summary = ft.Row(
        spacing=8,
        controls=[
            CountPill("Успешно", succeeded, theme.OK_GREEN, theme.OK_GREEN_BG),
            CountPill("Расхождения", with_diffs, theme.WARN_ORANGE, theme.WARN_ORANGE_BG),
            CountPill("Ошибки", failed, theme.GUU_RED, theme.ERROR_RED_BG),
        ],
    )

    diff_rows: list[ft.Control] = [_header_row()]
    row_index = 0
    for r in results:
        for d in r.diffs:
            diff_rows.append(
                _diff_row(row_index, r.index or r.filename, d.field, d.old_value, d.new_value)
            )
            row_index += 1
    if row_index == 0:
        diff_rows.append(
            ft.Container(
                ft.Text("Расхождений не обнаружено", italic=True,
                        color=ft.Colors.ON_SURFACE_VARIANT),
                padding=8,
            )
        )

    sections: list[ft.Control] = [
        summary,
        ft.Text("Расхождения чисел (в документы записаны значения из Базы):",
                weight=ft.FontWeight.BOLD),
        ft.Container(
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,  # скругление углов шапки
            content=ft.ListView(controls=diff_rows, spacing=0, height=220),
        ),
        ft.Divider(),
        ft.Text("Статус по файлам:", weight=ft.FontWeight.BOLD),
        ft.Container(
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            padding=ft.Padding.symmetric(vertical=4),
            content=ft.ListView(controls=[_status_row(r) for r in results], height=160),
        ),
    ]

    if not_found:
        sections += [
            ft.Container(
                bgcolor=ft.Colors.ERROR_CONTAINER,
                border_radius=8,
                padding=12,
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.SEARCH_OFF, size=18,
                                        color=ft.Colors.ON_ERROR_CONTAINER),
                                ft.Text("Не найдено в Базе данных:",
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.ON_ERROR_CONTAINER),
                            ],
                        ),
                        *[
                            ft.Text(f"• {r.filename} ({r.index or '—'})", size=12,
                                    color=ft.Colors.ON_ERROR_CONTAINER)
                            for r in not_found
                        ],
                    ],
                ),
            ),
        ]

    return ft.Column(sections, spacing=10)
