"""Главный экран EduConvert (Flet, декларативный подход, Material Design 3).

Рабочая область — две колонки: слева источники данных (учебный план и
официальные шаблоны), справа документы к конвертации. Внизу закреплена панель
действий с единственной главной кнопкой, поэтому запуск всегда на виду
и не требует прокрутки. После прогона правая часть заменяется экраном
результатов.

Здесь только разметка. Состояние живёт в :mod:`app.ui.state`
(:class:`~app.ui.state.AppState`, ``@ft.observable``): мутация его полей
автоматически перерисовывает UI без ручных ``page.update()``. Тяжёлая
конвертация выполняется асинхронно через оркестратор; прогресс обновляется
колбэком, меняющим поля состояния (ТЗ §5).
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import flet as ft

from app import __version__
from app.core.doc_converter import doc_support_hint
from app.ui import clipboard_files, persistence, theme
from app.ui.components import help_sheet
from app.ui.components.action_bar import ActionBar
from app.ui.components.file_list import FileList
from app.ui.components.help_sheet import HelpSheet
from app.ui.components.panel import Panel
from app.ui.components.pick_zone import PickZone
from app.ui.components.results_view import ResultsView
from app.ui.components.source_tile import SourceTile
from app.ui.components.status_badge import Pill
from app.ui.components.top_bar import TopBar
from app.ui.state import (
    RESULTS,
    SETUP,
    make_initial_state,
    plural_files,
    skip_reason,
)


def _snack(page: ft.Page, message: str, action: str | None = None,
           on_action=None) -> None:
    page.show_dialog(ft.SnackBar(
        content=ft.Text(message),
        behavior=ft.SnackBarBehavior.FLOATING,
        duration=3000,
        show_close_icon=True,
        action=action,
        on_action=on_action,
    ))


def _reveal(path: Path) -> None:
    """Открывает файловый менеджер на сохранённом файле."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603, S607
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])  # noqa: S603, S607
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])  # noqa: S603, S607
    except OSError:  # pragma: no cover — файловый менеджер недоступен
        pass


def _name(path: Path | None) -> str | None:
    return path.name if path else None


@ft.component
def App() -> ft.Control:
    state, _ = ft.use_state(make_initial_state())
    page = ft.context.page
    page.data["state"] = state

    # тема следует за состоянием (и запоминается между запусками)
    def _apply_theme() -> None:
        page.theme = theme.build_theme(state.dark)
        page.theme_mode = ft.ThemeMode.DARK if state.dark else ft.ThemeMode.LIGHT
        page.bgcolor = theme.palette(state.dark).canvas
        # без этого Flutter меняет всю Material-палитру одним кадром
        page.theme_animation_style = theme.theme_animation_style()

    ft.use_effect(_apply_theme, dependencies=[state.dark])

    def _save_paths() -> None:
        persistence.save_paths(
            str(state.db_path) if state.db_path else None,
            str(state.rpd_path),
            str(state.fos_path),
        )

    ft.use_effect(_save_paths, dependencies=[state.db_path, state.rpd_path, state.fos_path])

    def _update_recent_db() -> None:
        if state.db_path and state.db_path.exists():
            persistence.add_recent_db(str(state.db_path))

    ft.use_effect(_update_recent_db, dependencies=[state.db_path])

    # История баз читает файл настроек и проверяет каждый путь на диске.
    # Без memo это происходило на каждой перерисовке — в том числе на каждом
    # кадре перетаскивания окна и на каждом наведении мыши.
    recent_dbs = ft.use_memo(persistence.get_recent_dbs, dependencies=[state.db_path])
    recent_db_items = [
        (Path(p).name, lambda e, p=p: state.set_db(p))
        for p in recent_dbs
        if Path(p) != state.db_path
    ]

    # FilePicker и Clipboard — сервисы, а не визуальные контролы: создаются
    # через use_ref (автоматически регистрируются на странице) и НЕ попадают
    # в дерево controls.
    db_picker = ft.use_ref(ft.FilePicker)
    rpd_picker = ft.use_ref(ft.FilePicker)
    fos_picker = ft.use_ref(ft.FilePicker)
    files_picker = ft.use_ref(ft.FilePicker)
    dir_picker = ft.use_ref(ft.FilePicker)
    save_picker = ft.use_ref(ft.FilePicker)
    clipboard = ft.use_ref(ft.Clipboard)

    doc_hint = ft.use_memo(doc_support_hint, dependencies=[])
    paste_note = ft.use_memo(clipboard_files.unavailable_reason, dependencies=[])
    paste_hint = clipboard_files.hint()

    async def pick_db(e: ft.Event[ft.Control]) -> None:
        files = await db_picker.current.pick_files(
            dialog_title="Учебный план (Excel)",
            allowed_extensions=["xlsx", "xls", "xlsm"],
            allow_multiple=False,
        )
        if files:
            state.set_db(files[0].path)

    async def pick_rpd(e: ft.Event[ft.Control]) -> None:
        files = await rpd_picker.current.pick_files(
            dialog_title="Шаблон РПД 2026", allowed_extensions=["docx"],
            allow_multiple=False,
        )
        if files:
            state.set_rpd(files[0].path)

    async def pick_fos(e: ft.Event[ft.Control]) -> None:
        files = await fos_picker.current.pick_files(
            dialog_title="Шаблон ФОС 2026", allowed_extensions=["docx"],
            allow_multiple=False,
        )
        if files:
            state.set_fos(files[0].path)

    async def pick_inputs(e: ft.Event[ft.Control] | None = None) -> None:
        files = await files_picker.current.pick_files(
            dialog_title="Старые РПД и ФОС",
            allowed_extensions=["doc", "docx"],
            allow_multiple=True,
        )
        if files:
            paths = [f.path for f in files]
            added = state.add_files(paths)
            _snack(page, f"Добавлено {plural_files(added)}" if added
                   else skip_reason(paths))

    async def pick_dir(e: ft.Event[ft.Control] | None = None) -> None:
        directory = await dir_picker.current.get_directory_path(
            dialog_title="Папка со старыми РПД и ФОС"
        )
        if directory is None:
            return
        added = state.add_dir(directory)
        _snack(page, f"Добавлено {plural_files(added)}" if added
               else "В папке нет новых .doc или .docx")

    async def paste(e: ft.Event[ft.Control] | None = None) -> None:
        paths = await clipboard_files.clipboard_paths(clipboard.current)
        added = state.add_files(paths)
        if added:
            _snack(page, f"Добавлено {plural_files(added)} из буфера обмена")
        elif paths:
            _snack(page, skip_reason(paths))
        else:
            _snack(page, paste_note or "В буфере обмена нет файлов .doc или .docx")

    async def download(e: ft.Event[ft.Control] | None = None) -> None:
        dest = await save_picker.current.save_file(
            dialog_title="Сохранить результаты",
            file_name="EduConvert_результат.zip",
            allowed_extensions=["zip"],
        )
        if saved := await state.save_zip_to(dest):
            _snack(page, f"Архив сохранён: {saved.name}", action="Показать",
                   on_action=lambda e, p=saved: _reveal(p))

    async def start_conversion(e: ft.Event[ft.Control] | None = None) -> None:
        # локальная обёртка: bound-метод observable, переданный в on_click
        # контрола из props компонента, в Flet 0.85+ не срабатывает
        await state.start(e)

    def clear_inputs(e: ft.Event[ft.Control] | None = None) -> None:
        state.clear_inputs()

    async def _open_help() -> None:
        # карточку монтируют сжатой и разворачивают следующим кадром:
        # Flutter анимирует изменение свойства, а не стартовое значение
        await asyncio.sleep(0.03)
        if state.help_phase == help_sheet.ENTER:
            state.help_phase = help_sheet.OPEN

    async def _finish_close_help() -> None:
        # держим карточку в дереве, пока она втягивается обратно в «?»
        await asyncio.sleep(help_sheet.EXIT_HOLD_S)
        if state.help_phase == help_sheet.EXIT:
            state.help_phase = help_sheet.CLOSED

    def show_help(e: ft.Event[ft.Control] | None = None) -> None:
        if state.help_phase in (help_sheet.ENTER, help_sheet.OPEN):
            return
        state.help_phase = help_sheet.ENTER
        page.run_task(_open_help)

    def close_help(e: ft.Event[ft.Control] | None = None) -> None:
        if state.help_phase not in (help_sheet.ENTER, help_sheet.OPEN):
            return
        state.help_phase = help_sheet.EXIT
        page.run_task(_finish_close_help)

    # хендлеры для горячих клавиш из main()
    page.data["actions"] = {
        "pick_files": pick_inputs,
        "pick_dir": pick_dir,
        "paste": paste,
        "start": start_conversion,
        "clear": clear_inputs,
        "help": show_help,
        "close_help": close_help,
    }

    p = theme.palette(state.dark)
    width = state.width or page.width
    lay = theme.layout_for(width)

    # --- левая колонка: источники данных --- #
    sources = Panel(
        title="Источники данных",
        subtitle="Учебный план и официальные формы 2026",
        icon=ft.Icons.INVENTORY_2_OUTLINED,
        dark=state.dark,
        trailing=Pill(
            "готово" if state.sources_ok else "нужно выбрать",
            icon=ft.Icons.CHECK_ROUNDED if state.sources_ok else ft.Icons.EDIT_OUTLINED,
            fg=p.ok if state.sources_ok else ft.Colors.ON_SURFACE_VARIANT,
            bg=p.ok_bg if state.sources_ok else None,
            compact=True,
        ),
        content=ft.Column(
            spacing=theme.SPACE_SM,
            controls=[
                SourceTile("Учебный план (Excel)", _name(state.db_path), state.db_ok,
                           ft.Icons.TABLE_VIEW_ROUNDED, pick_db, state.dark,
                           menu_items=recent_db_items or None,
                           full_path=str(state.db_path) if state.db_path else None),
                SourceTile("Шаблон РПД 2026", _name(state.rpd_path), state.rpd_ok,
                           ft.Icons.ARTICLE_OUTLINED, pick_rpd, state.dark,
                           full_path=str(state.rpd_path)),
                SourceTile("Шаблон ФОС 2026", _name(state.fos_path), state.fos_ok,
                           ft.Icons.FACT_CHECK_OUTLINED, pick_fos, state.dark,
                           full_path=str(state.fos_path)),
            ],
        ),
    )

    tips: list[ft.Control] = []
    has_doc = any(f.suffix.lower() == ".doc" for f in state.input_files)
    if doc_hint and has_doc:
        tips.append(_notice(doc_hint, ft.Icons.WARNING_AMBER_ROUNDED, p.warn, p.warn_bg))
    if state.error:
        tips.append(_notice(state.error, ft.Icons.ERROR_OUTLINE_ROUNDED,
                            p.danger, p.danger_bg))

    left_column = ft.Column(spacing=lay.gap, tight=True, controls=[sources, *tips])

    # На широком экране правая колонка тянется на всю высоту окна; в одной
    # колонке она живёт внутри скролла, где растягиваться нельзя.
    fill = lay.two_columns

    # --- правая колонка: документы или результаты --- #
    if state.view == RESULTS and state.results:
        right_content: ft.Control = ft.Container(
            key="results",
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=theme.RADIUS_CARD,
            shadow=theme.soft_shadow(state.dark),
            padding=ft.Padding.all(theme.SPACE_LG),
            content=ResultsView(
                state.results,
                on_download=download,
                on_back=lambda e: setattr(state, "view", SETUP),
                dark=state.dark,
                fill=fill,
                compact=lay.compact,
            ),
        )
    else:
        header_actions: list[ft.Control] = [
            Pill(plural_files(len(state.input_files)),
                 icon=ft.Icons.DESCRIPTION_OUTLINED,
                 fg=ft.Colors.PRIMARY if state.input_files else ft.Colors.ON_SURFACE_VARIANT,
                 bg=(ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY)
                     if state.input_files else None),
                 compact=True)
        ]
        if state.input_files and not state.running:
            header_actions.append(
                ft.IconButton(icon=ft.Icons.DELETE_SWEEP_OUTLINED, icon_size=22,
                              tooltip="Очистить список (Ctrl+L)", on_click=clear_inputs)
            )

        # Ключ постоянен: AnimatedSwitcher обязан отличать «настройку» от
        # «результатов», но не отдельные состояния списка. С ключом, зависящим
        # от числа файлов, каждое добавление подменяло контрол целиком —
        # панель гасла и проявлялась заново вместо того, чтобы дорисовать строку.
        right_content = ft.Container(
            key="setup",
            expand=fill,
            content=Panel(
                title="Документы к конвертации",
                subtitle="Старые РПД и ФОС в форматах .doc и .docx",
                icon=ft.Icons.DRIVE_FOLDER_UPLOAD_OUTLINED,
                dark=state.dark,
                expand=fill,
                trailing=ft.Row(header_actions, spacing=4, tight=True),
                content=ft.Column(
                    spacing=theme.SPACE_MD,
                    expand=fill,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        PickZone(
                            on_pick_files=pick_inputs,
                            on_pick_dir=pick_dir,
                            on_paste=paste,
                            paste_hint=paste_hint,
                            compact=bool(state.input_files) or not lay.hero,
                            # пустая панель: зона выбора занимает её целиком
                            expand=fill and not state.input_files,
                        ),
                        *(
                            [
                                FileList(
                                    state.input_files,
                                    state.file_states,
                                    None if state.running else state.remove_file,
                                    state.dark,
                                    doc_unsupported=bool(doc_hint),
                                    fill=fill,
                                )
                            ]
                            if state.input_files or not lay.hero
                            else []
                        ),
                    ],
                ),
            ),
        )

    right_column = ft.AnimatedSwitcher(
        expand=fill,
        duration=ft.Duration(milliseconds=220),
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
        switch_out_curve=ft.AnimationCurve.EASE_IN,
        transition=ft.AnimatedSwitcherTransition.FADE,
        content=right_content,
    )

    if lay.two_columns:
        workspace: ft.Control = ft.Row(
            expand=True,
            spacing=lay.gap,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Container(width=lay.side_width, content=left_column),
                ft.Container(expand=True, content=right_column),
            ],
        )
    else:
        workspace = ft.Column(
            expand=True,
            spacing=lay.gap,
            scroll=ft.ScrollMode.AUTO,
            controls=[left_column, right_column],
        )

    shell = ft.Column(
        expand=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            TopBar(__version__, state.dark,
                   on_toggle_theme=lambda e: state.toggle_theme(),
                   on_help=show_help,
                   gutter=lay.gutter),
            # Отступы рабочей области зависят от ширины окна. С общим
            # ``animate`` контейнер догонял новую раскладку 680 мс, и при
            # перетаскивании края окна содержимое заметно отставало от рамки.
            ft.Container(
                expand=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                padding=ft.Padding.symmetric(
                    horizontal=lay.gutter, vertical=lay.gap
                ),
                # на широких мониторах контент не должен расползаться
                # во всю ширину — держим читаемую меру по центру
                alignment=ft.Alignment.TOP_CENTER,
                content=ft.Container(
                    expand=True,
                    width=min(width or lay.max_width, lay.max_width),
                    content=workspace,
                ),
            ),
            ActionBar(
                ready=state.ready,
                running=state.running,
                done=state.done,
                files_count=len(state.input_files),
                sources_ok=state.sources_ok,
                progress=state.progress,
                status=state.status,
                blocked_reason=state.blocked_reason,
                on_start=start_conversion,
                on_show_results=lambda e: setattr(state, "view", RESULTS),
                dark=state.dark,
                gutter=lay.gutter,
                compact=lay.compact,
            ),
        ],
    )

    if state.help_phase == help_sheet.CLOSED:
        return shell
    return ft.Stack(
        expand=True,
        controls=[
            shell,
            HelpSheet(state.help_phase, close_help, state.dark, lay.gutter,
                      window_width=width or 0.0,
                      window_height=state.height or page.height or 0.0),
        ],
    )


def _notice(text: str, icon: str, fg: str, bg: str) -> ft.Control:
    """Цветная плашка-предупреждение под панелью источников."""
    # Высота плашки зависит от того, во сколько строк ляжет текст, а это
    # меняется при каждом изменении ширины окна. Общий ``animate`` заставлял
    # её переползать к новой высоте, толкая всё под собой.
    return ft.Container(
        bgcolor=bg,
        border_radius=theme.RADIUS_CONTROL,
        padding=ft.Padding.all(theme.SPACE_MD),
        content=ft.Row(
            spacing=theme.SPACE_SM,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Icon(icon, size=22, color=fg),
                ft.Text(text, size=15, color=fg, expand=True, selectable=True),
            ],
        ),
    )


def main(page: ft.Page) -> None:
    """Точка входа Flet-приложения."""
    page.title = "EduConvert — конвертер РПД и ФОС"
    page.theme = theme.build_theme(persistence.get_dark_mode())
    page.theme_mode = (
        ft.ThemeMode.DARK if persistence.get_dark_mode() else ft.ThemeMode.LIGHT
    )
    page.theme_animation_style = theme.theme_animation_style()
    page.padding = 0
    page.data = {}  # разделяемый словарь между main() и компонентами

    if not page.web:  # свойства окна применимы только на десктопе
        page.window.width = 1560
        page.window.height = 980
        page.window.min_width = 600
        page.window.min_height = 600
        page.window.alignment = ft.Alignment.CENTER

    async def on_keyboard(e: ft.KeyboardEvent) -> None:
        actions = page.data.get("actions") or {}
        key = e.key.lower()
        if key == "f1":
            actions.get("help", lambda e=None: None)(None)
            return
        if key == "escape":
            actions.get("close_help", lambda e=None: None)(None)
            return
        if not e.ctrl:
            return
        handler = {
            "o": "pick_files",
            "d": "pick_dir",
            "v": "paste",
            "l": "clear",
            "enter": "start",
        }.get(key)
        if handler and (action := actions.get(handler)):
            result = action(None)
            if hasattr(result, "__await__"):
                await result

    page.on_keyboard_event = on_keyboard

    def on_resize(e: ft.Event[ft.Control]) -> None:
        """Прокидывает ширину окна в состояние, чтобы раскладка шла за окном.

        ``page.update()`` пересылает клиенту уже собранное дерево и компонент
        заново не выполняет — при перетаскивании края окна раскладка оставалась
        прежней и перескакивала позже, вместе с посторонним обновлением.
        Присваивание поля observable-состояния запускает честную пересборку.
        """
        if (state := page.data.get("state")) is not None:
            state.width = page.width or 0.0
            state.height = page.height or 0.0

    page.on_resize = on_resize
    page.render(App)


def run_desktop() -> None:
    """Запуск настольного приложения."""
    ft.run(main)


if __name__ == "__main__":
    run_desktop()
