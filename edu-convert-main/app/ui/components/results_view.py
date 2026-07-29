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


def _diff_row(index: int, subject: str, field: str, old: str, new: str,
              dark: bool, compact: bool = False) -> ft.Control:
    p = theme.palette(dark)
    # Пара «было → стало» не сжимается: числа короткие, но зачёркнутое старое
    # значение со стрелкой требует своей ширины, и на узком окне колонка
    # с дисциплиной выдавливала её за правый край.
    change = ft.Row(
        expand=None if compact else 3,
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        tight=compact,
        controls=[
            ft.Text(old, size=15, color=p.danger,
                    style=ft.TextStyle(
                        color=p.danger,
                        decoration=ft.TextDecoration.LINE_THROUGH)),
            ft.Icon(ft.Icons.ARROW_RIGHT_ALT_ROUNDED, size=20,
                    color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(new, size=15, color=p.ok, weight=ft.FontWeight.W_700),
        ],
    )
    field_text = ft.Text(field, size=15, expand=True if compact else 4,
                         max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                         tooltip=field)
    if compact:
        # Три колонки в 600 px не помещаются, поэтому строка становится
        # карточкой: дисциплина сверху, поле и изменение — под ней.
        content: ft.Control = ft.Column(
            spacing=4,
            tight=True,
            controls=[
                ft.Text(subject, size=13, color=ft.Colors.ON_SURFACE_VARIANT,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                        tooltip=subject),
                ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[field_text, change],
                ),
            ],
        )
    else:
        content = ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(subject, size=15, expand=3, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS, tooltip=subject),
                field_text,
                change,
            ],
        )
    return ft.Container(
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW if index % 2 else None,
        padding=ft.Padding.symmetric(horizontal=18, vertical=14),
        content=content,
    )


def _file_row(result: FileResult, dark: bool, compact: bool = False) -> ft.Control:
    name = ft.Column(
        spacing=2,
        expand=None if compact else 5,
        tight=True,
        controls=[
            ft.Text(result.filename, size=15, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=result.filename),
            ft.Text(result.index or "индекс не определён", size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT),
        ],
    )
    message = ft.Text(result.message or "—", size=14,
                      expand=True if compact else 5, max_lines=2,
                      color=ft.Colors.ON_SURFACE_VARIANT,
                      overflow=ft.TextOverflow.ELLIPSIS, tooltip=result.message)
    if compact:
        # Имя файла, бейдж и сообщение в одну строку на 600 px не влезают:
        # бейдж «Расхождение» отжимал имя до пары букв.
        content: ft.Control = ft.Column(
            spacing=6,
            tight=True,
            controls=[
                name,
                ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[StatusBadge(result.status, dark), message],
                ),
            ],
        )
    else:
        content = ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                name,
                ft.Container(StatusBadge(result.status, dark), expand=2),
                message,
            ],
        )
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=18, vertical=13),
        content=content,
    )


def _empty(text: str) -> ft.Control:
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=theme.SPACE_XL),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.INBOX_ROUNDED, size=40, color=ft.Colors.OUTLINE),
                ft.Text(text, size=15, italic=True, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )


def _framed(content: ft.Control, dark: bool, fill: bool = False) -> ft.Control:
    return ft.Container(
        expand=fill,
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
    fill: bool = False,
    compact: bool = False,
) -> ft.Control:
    """Панель результатов.

    ``fill`` — растянуть таблицы на всю высоту окна. ``compact`` — узкое окно:
    шапка разъезжается на два этажа, у вкладок остаются только подписи, а
    плитки сводки встают друг под друга. В одну строку это не помещается,
    а ``Row`` не переносит содержимое, а обрезает.
    """
    tab, set_tab = ft.use_state(SUMMARY)
    query, set_query = ft.use_state("")
    p = theme.palette(dark)

    total = len(results)
    succeeded = sum(1 for r in results if r.status == FileStatus.SUCCESS)
    with_diffs = sum(1 for r in results if r.status == FileStatus.DISCREPANCY)
    failed = sum(1 for r in results if r.status == FileStatus.ERROR)
    diffs = [(r, d) for r in results for d in r.diffs]

    # Поле обёрнуто в ``Row``: ``Column`` выравнивает детей по левому краю и
    # оставляет им собственную ширину, поэтому поиск занимал половину карточки
    # и обрывал подсказку на «Поиск по дисциплине, полю …».
    search = ft.Row([
        ft.TextField(
            value=query,
            expand=True,
            hint_text="Поиск по дисциплине, полю или файлу…",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            dense=True,
            filled=True,
            border_radius=theme.RADIUS_CONTROL,
            border_color=p.hairline,
            content_padding=ft.Padding.symmetric(horizontal=18, vertical=16),
            text_size=16,
            on_change=lambda e: set_query(e.control.value),
        )
    ])

    if tab == SUMMARY:
        cards = [
            StatCard("Успешно", succeeded, total, p.ok, p.ok_bg,
                     ft.Icons.CHECK_CIRCLE_ROUNDED, compact),
            StatCard("Расхождения", with_diffs, total, p.warn, p.warn_bg,
                     ft.Icons.CHANGE_CIRCLE_ROUNDED, compact),
            StatCard("Ошибки", failed, total, p.danger, p.danger_bg,
                     ft.Icons.ERROR_ROUNDED, compact),
        ]
        body: ft.Control = ft.Column(
            spacing=theme.SPACE_MD,
            controls=[
                # На узком окне три плитки делили бы между собой около 170 px,
                # и подпись «Расхождения» обрезалась многоточием сразу за «Рас».
                # Каждая плитка обёрнута в свой ``Row``: у ``StatCard`` стоит
                # ``expand``, и внутри колонки он растягивал бы её по высоте.
                ft.Column(spacing=theme.SPACE_SM, tight=True,
                          controls=[ft.Row([c]) for c in cards])
                if compact
                else ft.Row(spacing=theme.SPACE_MD, controls=cards),
                ft.Container(
                    bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                    border_radius=theme.RADIUS_CONTROL,
                    padding=ft.Padding.all(theme.SPACE_MD),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=21,
                                            color=ft.Colors.PRIMARY),
                                    ft.Text("Что внутри архива", size=17,
                                            weight=ft.FontWeight.W_600),
                                ],
                            ),
                            ft.Text(
                                f"{total} готовых документов по форме 2026 "
                                "и report.xlsx со всеми расхождениями. "
                                "Всё, что подставила конвертация, выделено жёлтым; "
                                "числа взяты из учебного плана.",
                                size=15,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                    ),
                ),
            ],
        )
    elif tab == DIFFS:
        rows = [
            _diff_row(i, r.index or r.filename, d.field, d.old_value, d.new_value,
                      dark, compact)
            for i, (r, d) in enumerate(
                (r, d) for r, d in diffs
                if _matches(query, r.index, r.filename, d.field, d.old_value, d.new_value)
            )
        ]
        body = ft.Column(
            spacing=theme.SPACE_SM,
            expand=fill,
            controls=[
                search,
                _framed(
                    ft.ListView(controls=rows, expand=fill,
                                height=None if fill else 380) if rows
                    else _empty("Расхождений не найдено"),
                    dark,
                    fill=fill,
                ),
                ft.Text(
                    "Слева — значение из старого документа, справа — из учебного плана "
                    "(записано в новый файл).",
                    size=14,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
        )
    else:
        rows = [
            _file_row(r, dark, compact) for r in results
            if _matches(query, r.filename, r.index, r.message)
        ]
        body = ft.Column(
            spacing=theme.SPACE_SM,
            expand=fill,
            controls=[
                search,
                _framed(
                    ft.ListView(controls=rows, expand=fill,
                                height=None if fill else 380) if rows
                    else _empty("Ничего не найдено"),
                    dark,
                    fill=fill,
                ),
            ],
        )

    # На узком окне у сегментов убираются иконки и ужимаются поля: подпись
    # «Расхождения · 12» вместе с иконкой не помещалась, и переключатель
    # вылезал за правый край карточки.
    tabs = ft.SegmentedButton(
        selected=[tab],
        allow_empty_selection=False,
        show_selected_icon=False,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
            text_style=ft.TextStyle(size=14 if compact else 15,
                                    weight=ft.FontWeight.W_600),
            padding=ft.Padding.symmetric(horizontal=6 if compact else 16,
                                         vertical=18),
        ),
        segments=[
            ft.Segment(value=SUMMARY, label=ft.Text("Сводка"),
                       icon=None if compact
                       else ft.Icon(ft.Icons.DONUT_LARGE_ROUNDED, size=20)),
            ft.Segment(value=DIFFS, label=ft.Text(f"Расхождения · {len(diffs)}"),
                       icon=None if compact
                       else ft.Icon(ft.Icons.COMPARE_ARROWS_ROUNDED, size=20)),
            ft.Segment(value=FILES, label=ft.Text(f"Файлы · {total}"),
                       icon=None if compact
                       else ft.Icon(ft.Icons.FOLDER_COPY_OUTLINED, size=20)),
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
                padding=ft.Padding.all(theme.SPACE_MD),
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=21,
                                        color=p.danger),
                                ft.Text(f"Не обработано: {len(failed_names)}", size=15,
                                        weight=ft.FontWeight.W_600, color=p.danger),
                            ],
                        ),
                        ft.Text(
                            ", ".join(r.filename for r in failed_names[:4])
                            + ("…" if len(failed_names) > 4 else ""),
                            size=14,
                            color=p.danger,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
            )
        )

    title = ft.Column(
        spacing=2,
        expand=True,
        tight=True,
        controls=[
            ft.Text("Результаты конвертации", size=20 if compact else 23,
                    weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(f"Обработано документов: {total}", size=15,
                    color=ft.Colors.ON_SURFACE_VARIANT),
        ],
    )
    back = ft.IconButton(
        icon=ft.Icons.ARROW_BACK_ROUNDED,
        icon_size=24,
        tooltip="Вернуться к настройке",
        on_click=on_back,
    )
    ok_pill = Pill(f"{succeeded} успешно", icon=ft.Icons.CHECK_ROUNDED,
                   fg=p.ok, bg=p.ok_bg, compact=True)
    download = ft.FilledButton(
        "Скачать .zip",
        icon=ft.Icons.DOWNLOAD_ROUNDED,
        on_click=on_download,
        expand=compact,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
            padding=ft.Padding.symmetric(horizontal=16 if compact else 26,
                                         vertical=28),
            text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600),
        ),
    )
    # Заголовок, пилюля и кнопка скачивания в 600 px в одну строку не влезают:
    # «Скачать .zip» съезжала за край, а заголовок сжимался до многоточия.
    header: ft.Control = (
        ft.Column(
            spacing=theme.SPACE_SM,
            tight=True,
            controls=[
                ft.Row([back, title], spacing=theme.SPACE_SM,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([ok_pill, download], spacing=theme.SPACE_SM,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ],
        )
        if compact
        else ft.Row(
            spacing=theme.SPACE_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[back, title, ok_pill, download],
        )
    )

    return ft.Column(
        spacing=theme.SPACE_MD,
        expand=fill,
        controls=[
            header,
            tabs,
            *warning,
            body,
        ],
    )
