"""Виртуализированная таблица результатов и расхождений (зона 4, ТЗ §5, §8).

Использует :class:`ft.ListView` для предотвращения падения FPS на больших
объёмах данных. Строки-расхождения подсвечиваются, ненайденные в Базе
дисциплины выводятся отдельным блоком «Не найдено в БД».
"""

from __future__ import annotations

import flet as ft

from app.core.models import FileResult, FileStatus


def _header_row() -> ft.Control:
    def cell(text: str, flex: int) -> ft.Control:
        return ft.Container(
            ft.Text(text, weight=ft.FontWeight.BOLD, size=12), expand=flex, padding=6
        )

    return ft.Container(
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        content=ft.Row(
            [cell("Дисциплина", 3), cell("Поле", 3), cell("Было (старый файл)", 2),
             cell("Стало (База)", 2)],
            spacing=0,
        ),
    )


def _diff_row(index: str, field: str, old: str, new: str) -> ft.Control:
    def cell(text: str, flex: int, color: str | None = None) -> ft.Control:
        return ft.Container(
            ft.Text(text, size=12, color=color), expand=flex, padding=6
        )

    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED),  # подсветка расхождения
        content=ft.Row(
            [cell(index, 3), cell(field, 3),
             cell(old, 2, ft.Colors.RED), cell(new, 2, ft.Colors.GREEN)],
            spacing=0,
        ),
    )


def _status_row(result: FileResult) -> ft.Control:
    color = {
        FileStatus.SUCCESS: ft.Colors.GREEN,
        FileStatus.DISCREPANCY: ft.Colors.ORANGE,
        FileStatus.ERROR: ft.Colors.RED,
    }[result.status]
    return ft.Container(
        padding=6,
        content=ft.Row(
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.CIRCLE, size=10, color=color),
                ft.Text(f"{result.index or result.filename}", size=12, expand=3),
                ft.Text(result.status.value, size=12, color=color, expand=2),
                ft.Text(result.message, size=11, color=ft.Colors.ON_SURFACE_VARIANT, expand=4),
            ],
        ),
    )


@ft.component
def ReportTable(results: list[FileResult]) -> ft.Control:
    """Список расхождений + сводка статусов + блок «не найдено в БД»."""
    not_found = [r for r in results if r.status == FileStatus.ERROR]
    diff_rows: list[ft.Control] = [_header_row()]
    for r in results:
        for d in r.diffs:
            diff_rows.append(_diff_row(r.index or r.filename, d.field, d.old_value, d.new_value))
    if len(diff_rows) == 1:
        diff_rows.append(
            ft.Container(ft.Text("Расхождений не обнаружено", italic=True), padding=8)
        )

    sections: list[ft.Control] = [
        ft.Text("Расхождения чисел (в документы записаны значения из Базы):",
                weight=ft.FontWeight.BOLD),
        ft.Container(
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            content=ft.ListView(controls=diff_rows, spacing=0, height=220),
        ),
        ft.Divider(),
        ft.Text("Статус по файлам:", weight=ft.FontWeight.BOLD),
        ft.Container(
            content=ft.ListView(controls=[_status_row(r) for r in results], height=160),
        ),
    ]

    if not_found:
        sections += [
            ft.Divider(),
            ft.Text("Не найдено в Базе данных:", weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
            ft.Column([ft.Text(f"• {r.filename} ({r.index or '—'})", size=12) for r in not_found]),
        ]

    return ft.Column(sections, spacing=10)
