"""Зона добавления исходных документов.

Пунктирная область с крупной иконкой и тремя способами добавить файлы:
диалог выбора, выбор папки целиком и вставка из буфера обмена. Подсказка о
буфере формулируется под текущую ОС (:mod:`app.ui.clipboard_files`).
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.ui import theme


@ft.component
def PickZone(
    on_pick_files: Callable[[ft.Event[ft.Control]], None],
    on_pick_dir: Callable[[ft.Event[ft.Control]], None],
    on_paste: Callable[[ft.Event[ft.Control]], None],
    paste_hint: str,
    compact: bool = False,
    expand: bool = False,
) -> ft.Control:
    """Область выбора файлов; ``compact`` — когда файлы уже добавлены."""
    buttons = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=12,
        run_spacing=12,
        wrap=True,
        controls=[
            ft.FilledButton(
                "Выбрать файлы",
                icon=ft.Icons.NOTE_ADD_OUTLINED,
                tooltip="Ctrl+O",
                on_click=on_pick_files,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
                    padding=ft.Padding.symmetric(horizontal=26, vertical=24),
                    text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600),
                ),
            ),
            ft.OutlinedButton(
                "Папка",
                icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                tooltip="Добавить все .doc/.docx из папки (Ctrl+D)",
                on_click=on_pick_dir,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
                    padding=ft.Padding.symmetric(horizontal=26, vertical=24),
                    text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600),
                ),
            ),
            ft.OutlinedButton(
                "Вставить",
                icon=ft.Icons.CONTENT_PASTE_ROUNDED,
                tooltip=paste_hint,
                on_click=on_paste,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CONTROL),
                    padding=ft.Padding.symmetric(horizontal=26, vertical=24),
                    text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600),
                ),
            ),
        ],
    )

    if compact:
        return ft.Container(
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=theme.RADIUS_CONTROL,
            padding=ft.Padding.all(theme.SPACE_SM),
            content=buttons,
        )

    return ft.Container(
        expand=expand,
        border=ft.Border.all(1.5, ft.Colors.with_opacity(0.35, ft.Colors.PRIMARY)),
        border_radius=theme.RADIUS_CARD,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
        padding=ft.Padding.symmetric(horizontal=theme.SPACE_LG, vertical=theme.SPACE_XL),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=theme.SPACE_MD,
            controls=[
                ft.Container(
                    width=92,
                    height=92,
                    border_radius=46,
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=46,
                                    color=ft.Colors.PRIMARY),
                ),
                ft.Text("Добавьте старые РПД и ФОС", size=23,
                        weight=ft.FontWeight.W_600),
                ft.Text(
                    "Форматы .doc и .docx — файлами, папкой целиком "
                    "или вставкой из буфера обмена",
                    size=15,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                buttons,
            ],
        ),
    )
