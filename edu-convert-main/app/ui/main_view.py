"""Главный экран EduConvert (Flet, декларативный подход, Material Design 3).

Рабочая область — две колонки: слева источники данных (учебный план и
официальные шаблоны), справа документы к конвертации. Внизу закреплена панель
действий с единственной главной кнопкой, поэтому запуск всегда на виду
и не требует прокрутки. После прогона правая часть заменяется экраном
результатов.

Состояние приложения — реактивный объект :class:`AppState` (``@ft.observable``):
мутация его полей автоматически перерисовывает UI без ручных ``page.update()``.
Тяжёлая конвертация выполняется асинхронно через оркестратор; прогресс
обновляется колбэком, меняющим поля состояния (ТЗ §5).
"""

from __future__ import annotations

import atexit
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import flet as ft

from app import __version__
from app.config import settings
from app.core.doc_converter import doc_support_hint
from app.core.models import FileResult, FileStatus
from app.services.orchestrator import Orchestrator, RunResult
from app.ui import clipboard_files, persistence, theme
from app.ui.components import file_list as fl
from app.ui.components.action_bar import ActionBar
from app.ui.components.file_list import FileList
from app.ui.components.panel import Panel
from app.ui.components.pick_zone import PickZone
from app.ui.components.results_view import ResultsView
from app.ui.components.source_tile import SourceTile
from app.ui.components.status_badge import Pill
from app.ui.components.top_bar import TopBar

_INPUT_SUFFIXES = {".doc", ".docx"}

SETUP = "setup"
RESULTS = "results"


def _plural_files(n: int) -> str:
    """«1 файл», «2 файла», «5 файлов» — правила русского языка."""
    if 11 <= (n % 100) <= 14:
        return f"{n} файлов"
    r = n % 10
    if r == 1:
        return f"{n} файл"
    if 2 <= r <= 4:
        return f"{n} файла"
    return f"{n} файлов"


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


def _make_initial_state() -> "AppState":
    """Создаёт AppState с путями, восстановленными из сохранённых настроек."""
    saved = persistence.load()
    state = AppState(dark=persistence.get_dark_mode())
    if (db := saved.get("db_path")) and Path(db).exists():
        state.db_path = Path(db)
    if (rpd := saved.get("rpd_path")) and Path(rpd).exists():
        state.rpd_path = Path(rpd)
    if (fos := saved.get("fos_path")) and Path(fos).exists():
        state.fos_path = Path(fos)
    return state


# Очистка temp последнего прогона при выходе из приложения (ТЗ §7.3):
# без этого workdir и ZIP последнего запуска оставались на диске навсегда.
_pending_cleanup: list[RunResult] = []


@atexit.register
def _cleanup_pending() -> None:
    for result in _pending_cleanup:
        result.cleanup()
    _pending_cleanup.clear()


@ft.observable
@dataclass
class AppState:
    """Реактивное состояние приложения."""

    db_path: Path | None = None
    rpd_path: Path = field(default_factory=lambda: settings.rpd_template)
    fos_path: Path = field(default_factory=lambda: settings.fos_template)
    input_files: list[Path] = field(default_factory=list)

    running: bool = False
    done: bool = False
    progress: float = 0.0
    processed: int = 0
    status: str = ""
    error: str = ""
    results: list[FileResult] = field(default_factory=list)

    dark: bool = False
    view: str = SETUP

    _run_result: RunResult | None = None

    # --- производные признаки --- #
    @property
    def db_ok(self) -> bool:
        return self.db_path is not None and self.db_path.exists()

    @property
    def rpd_ok(self) -> bool:
        return self.rpd_path.exists()

    @property
    def fos_ok(self) -> bool:
        return self.fos_path.exists()

    @property
    def sources_ok(self) -> bool:
        return self.db_ok and self.rpd_ok and self.fos_ok

    @property
    def ready(self) -> bool:
        return self.sources_ok and bool(self.input_files) and not self.running

    @property
    def blocked_reason(self) -> str | None:
        """Почему кнопка запуска недоступна (подсказка на кнопке)."""
        if self.running:
            return "Идёт конвертация…"
        if not self.sources_ok:
            return "Выберите учебный план и оба шаблона 2026"
        if not self.input_files:
            return "Добавьте хотя бы один файл РПД или ФОС"
        return None

    @property
    def file_states(self) -> dict[str, str]:
        """Состояние каждой строки списка файлов (очередь/работа/итог)."""
        if self.results:
            by_status = {
                FileStatus.SUCCESS: fl.DONE,
                FileStatus.DISCREPANCY: fl.WARN,
                FileStatus.ERROR: fl.FAILED,
            }
            return {r.filename: by_status[r.status] for r in self.results}
        if not self.running:
            return {}
        states: dict[str, str] = {}
        for i, path in enumerate(self.input_files):
            if i < self.processed:
                states[path.name] = fl.DONE
            elif i == self.processed:
                states[path.name] = fl.RUNNING
            else:
                states[path.name] = fl.QUEUED
        return states

    # --- мутации --- #
    def set_db(self, path: str | None) -> None:
        if path:
            self.db_path = Path(path)

    def set_rpd(self, path: str | None) -> None:
        if path:
            self.rpd_path = Path(path)

    def set_fos(self, path: str | None) -> None:
        if path:
            self.fos_path = Path(path)

    def add_files(self, paths: list[str]) -> int:
        """Добавляет .doc/.docx, пропуская дубли; возвращает число добавленных."""
        existing = {str(p) for p in self.input_files}
        new = [
            Path(p) for p in paths
            if p and p not in existing and Path(p).suffix.lower() in _INPUT_SUFFIXES
        ]
        if new:
            self.input_files = [*self.input_files, *new]
        return len(new)

    def add_dir(self, directory: str | None) -> int:
        if not directory:
            return 0
        found = [
            p for p in sorted(Path(directory).iterdir())
            if p.suffix.lower() in _INPUT_SUFFIXES and not p.name.startswith("~$")
        ]
        return self.add_files([str(p) for p in found])

    def clear_inputs(self) -> None:
        self.input_files = []

    def remove_file(self, path: Path) -> None:
        """Убирает один файл из списка.

        Список переприсваивается (не мутируется in-place): ``@ft.observable``
        реагирует только на присваивание поля.
        """
        self.input_files = [p for p in self.input_files if p != path]

    def toggle_theme(self) -> None:
        self.dark = not self.dark
        persistence.save_dark_mode(self.dark)

    # --- запуск конвертации --- #
    async def start(self, e: ft.Event[ft.Control] | None = None) -> None:
        if not self.ready:
            return
        self._dispose_previous()
        self.running = True
        self.done = False
        self.error = ""
        self.results = []
        self.progress = 0.0
        self.processed = 0
        self.view = SETUP

        def on_progress(done: int, total: int, message: str) -> None:
            self.progress = done / max(total, 1)
            self.processed = done
            self.status = message

        try:
            orch = Orchestrator(self.db_path, self.rpd_path, self.fos_path)
            result = await orch.run(list(self.input_files), on_progress)
            self._run_result = result
            _pending_cleanup.append(result)
            self.results = result.report.results
            self.status = (
                f"Готово: успешно {result.report.succeeded}, "
                f"расхождений {result.report.with_discrepancies}, "
                f"ошибок {result.report.failed}"
            )
            self.done = True
            self.view = RESULTS
        except Exception as exc:  # noqa: BLE001 — показываем пользователю
            self.error = f"{exc}"
            self.status = "Прервано из-за ошибки"
        finally:
            self.running = False

    def save_zip_to(self, dest: str | None) -> Path | None:
        if dest and self._run_result is not None:
            shutil.copy(self._run_result.zip_path, dest)
            return Path(dest)
        return None

    def _dispose_previous(self) -> None:
        if self._run_result is not None:
            self._run_result.cleanup()  # очистка temp прошлого прогона (ТЗ §7.3)
            if self._run_result in _pending_cleanup:
                _pending_cleanup.remove(self._run_result)
            self._run_result = None


def _name(path: Path | None) -> str | None:
    return path.name if path else None


def _help_dialog(dark: bool) -> ft.AlertDialog:
    """Короткая справка: порядок работы и горячие клавиши."""
    def line(icon: str, text: str) -> ft.Control:
        return ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Icon(icon, size=21, color=ft.Colors.PRIMARY),
                ft.Text(text, size=15, expand=True),
            ],
        )

    def key(combo: str, text: str) -> ft.Control:
        return ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=120,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Text(combo, size=14, weight=ft.FontWeight.W_600),
                ),
                ft.Text(text, size=15, expand=True),
            ],
        )

    return ft.AlertDialog(
        title=ft.Text("Как это работает", size=23, weight=ft.FontWeight.BOLD),
        shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_CARD),
        scrollable=True,
        content=ft.Container(
            width=580,
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    line(ft.Icons.TABLE_VIEW_ROUNDED,
                         "Числа (зачётные единицы, часы, семестры) берутся из учебного "
                         "плана — он единственный источник истины."),
                    line(ft.Icons.DESCRIPTION_OUTLINED,
                         "Текстовые блоки (литература, темы, оценочные средства) "
                         "переносятся из старых РПД и ФОС."),
                    line(ft.Icons.FORMAT_PAINT_OUTLINED,
                         "Всё подставленное конвертацией выделяется жёлтым, "
                         "старые числа попадают только в отчёт о расхождениях."),
                    ft.Divider(),
                    key("Ctrl + O", "выбрать файлы"),
                    key("Ctrl + D", "добавить папку"),
                    key("Ctrl + V", "вставить файлы из буфера"),
                    key("Ctrl + Enter", "запустить конвертацию"),
                    key("Ctrl + L", "очистить список"),
                ],
            ),
        ),
        actions=[
            ft.TextButton("Понятно", on_click=lambda e: ft.context.page.pop_dialog()),
        ],
    )


@ft.component
def App() -> ft.Control:
    state, _ = ft.use_state(_make_initial_state())
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

    recent_db_items = [
        (Path(p).name, lambda e, p=p: state.set_db(p))
        for p in persistence.get_recent_dbs()
        if Path(p) != state.db_path
    ]

    # FilePicker и Clipboard — сервисы, а не визуальные контролы: создаются
    # через use_ref (автоматически регистрируются на странице) и НЕ попадают
    # в дерево controls.
    db_picker = ft.use_ref(lambda: ft.FilePicker())
    rpd_picker = ft.use_ref(lambda: ft.FilePicker())
    fos_picker = ft.use_ref(lambda: ft.FilePicker())
    files_picker = ft.use_ref(lambda: ft.FilePicker())
    dir_picker = ft.use_ref(lambda: ft.FilePicker())
    save_picker = ft.use_ref(lambda: ft.FilePicker())
    clipboard = ft.use_ref(lambda: ft.Clipboard())

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
            added = state.add_files([f.path for f in files])
            _snack(page, f"Добавлено {_plural_files(added)}" if added
                   else "Эти файлы уже в списке")

    async def pick_dir(e: ft.Event[ft.Control] | None = None) -> None:
        directory = await dir_picker.current.get_directory_path(
            dialog_title="Папка со старыми РПД и ФОС"
        )
        if directory is None:
            return
        added = state.add_dir(directory)
        _snack(page, f"Добавлено {_plural_files(added)}" if added
               else "В папке нет новых .doc или .docx")

    async def paste(e: ft.Event[ft.Control] | None = None) -> None:
        paths = await clipboard_files.clipboard_paths(clipboard.current)
        added = state.add_files(paths)
        if added:
            _snack(page, f"Добавлено {_plural_files(added)} из буфера обмена")
        elif paths:
            _snack(page, "Эти файлы уже в списке")
        else:
            _snack(page, paste_note or "В буфере обмена нет файлов .doc или .docx")

    async def download(e: ft.Event[ft.Control] | None = None) -> None:
        dest = await save_picker.current.save_file(
            dialog_title="Сохранить результаты",
            file_name="EduConvert_результат.zip",
            allowed_extensions=["zip"],
        )
        if saved := state.save_zip_to(dest):
            _snack(page, f"Архив сохранён: {saved.name}", action="Показать",
                   on_action=lambda e, p=saved: _reveal(p))

    async def start_conversion(e: ft.Event[ft.Control] | None = None) -> None:
        # локальная обёртка: bound-метод observable, переданный в on_click
        # контрола из props компонента, в Flet 0.85+ не срабатывает
        await state.start(e)

    def clear_inputs(e: ft.Event[ft.Control] | None = None) -> None:
        state.clear_inputs()

    def show_help(e: ft.Event[ft.Control] | None = None) -> None:
        page.show_dialog(_help_dialog(state.dark))

    # хендлеры для горячих клавиш из main()
    page.data["actions"] = {
        "pick_files": pick_inputs,
        "pick_dir": pick_dir,
        "paste": paste,
        "start": start_conversion,
        "clear": clear_inputs,
        "help": show_help,
    }

    p = theme.palette(state.dark)
    lay = theme.layout_for(page.width)

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
            bgcolor=p.card,
            border=ft.Border.all(1, p.hairline),
            border_radius=theme.RADIUS_CARD,
            shadow=theme.soft_shadow(state.dark),
            animate=theme.theme_motion(),
            padding=ft.Padding.all(theme.SPACE_LG),
            content=ResultsView(
                state.results,
                on_download=download,
                on_back=lambda e: setattr(state, "view", SETUP),
                dark=state.dark,
                fill=fill,
            ),
        )
    else:
        header_actions: list[ft.Control] = [
            Pill(_plural_files(len(state.input_files)),
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

        right_content = ft.Container(
            key=f"setup-{len(state.input_files)}",
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
                            dark=state.dark,
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

    return ft.Column(
        expand=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            TopBar(__version__, state.dark,
                   on_toggle_theme=lambda e: state.toggle_theme(),
                   on_help=show_help,
                   gutter=lay.gutter),
            ft.Container(
                expand=True,
                bgcolor=p.canvas,
                animate=theme.theme_motion(),
                padding=ft.Padding.symmetric(
                    horizontal=lay.gutter, vertical=lay.gap
                ),
                # на широких мониторах контент не должен расползаться
                # во всю ширину — держим читаемую меру по центру
                alignment=ft.Alignment.TOP_CENTER,
                content=ft.Container(
                    expand=True,
                    width=min(page.width or lay.max_width, lay.max_width),
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
            ),
        ],
    )


def _notice(text: str, icon: str, fg: str, bg: str) -> ft.Control:
    """Цветная плашка-предупреждение под панелью источников."""
    return ft.Container(
        bgcolor=bg,
        border_radius=theme.RADIUS_CONTROL,
        animate=theme.theme_motion(),
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
    # раскладка зависит от ширины окна: перерисовываем при изменении размера
    page.on_resize = lambda e: page.update()
    page.render(App)


def run_desktop() -> None:
    """Запуск настольного приложения."""
    ft.run(main)


if __name__ == "__main__":
    run_desktop()
