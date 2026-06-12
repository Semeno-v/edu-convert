"""Главный экран EduConvert (Flet, декларативный подход, Material Design 3).

Состояние приложения — реактивный объект :class:`AppState` (``@ft.observable``):
мутация его полей автоматически перерисовывает UI без ручных ``page.update()``.
Тяжёлая конвертация выполняется асинхронно через оркестратор; прогресс
обновляется колбэком, меняющим поля состояния (ТЗ §5).

Визуальный язык — фирменный стиль ГУУ (:mod:`app.ui.theme`): секции-карточки
с номерами шагов, градиентная шапка, светлая тема.
"""

from __future__ import annotations

import atexit
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import flet as ft

from app import __version__
from app.config import settings
from app.core.models import FileResult
from app.services.orchestrator import Orchestrator, RunResult
from app.ui import theme
from app.ui.components.file_list import FileList
from app.ui.components.report_table import ReportTable
from app.ui.components.section_card import SectionCard
from app.ui.components.upload_card import UploadCard

_INPUT_SUFFIXES = {".doc", ".docx"}


def _paste_clipboard_files(state: "AppState", page: ft.Page) -> None:
    """Читает пути .doc/.docx из CF_HDROP буфера обмена.

    Пользователь выделяет файлы в Проводнике → Ctrl+C → переключается
    в приложение → Ctrl+V — файлы добавляются в список.
    Только для десктопа: на вебе буфер обмена недоступен.
    """
    if page.web:
        return
    try:
        import win32clipboard  # noqa: PLC0415
        import win32con        # noqa: PLC0415
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                paths = list(win32clipboard.GetClipboardData(win32con.CF_HDROP))
                state.add_files(paths)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:  # noqa: BLE001
        pass

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
    status: str = ""
    error: str = ""
    results: list[FileResult] = field(default_factory=list)

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
    def ready(self) -> bool:
        return self.db_ok and self.rpd_ok and self.fos_ok and bool(self.input_files) and not self.running

    # --- мутации (вызываются из обработчиков FilePicker) --- #
    def set_db(self, path: str | None) -> None:
        if path:
            self.db_path = Path(path)

    def set_rpd(self, path: str | None) -> None:
        if path:
            self.rpd_path = Path(path)

    def set_fos(self, path: str | None) -> None:
        if path:
            self.fos_path = Path(path)

    def add_files(self, paths: list[str]) -> None:
        existing = {str(p) for p in self.input_files}
        new = [Path(p) for p in paths if p and p not in existing and Path(p).suffix.lower() in _INPUT_SUFFIXES]
        if new:
            self.input_files = [*self.input_files, *new]

    def add_dir(self, directory: str | None) -> None:
        if not directory:
            return
        found = [
            p for p in sorted(Path(directory).iterdir())
            if p.suffix.lower() in _INPUT_SUFFIXES and not p.name.startswith("~$")
        ]
        self.add_files([str(p) for p in found])

    def clear_inputs(self) -> None:
        self.input_files = []

    def remove_file(self, path: Path) -> None:
        """Убирает один файл из списка выбранных (крестик в строке списка).

        Список переприсваивается (не мутируется in-place): ``@ft.observable``
        реагирует только на присваивание поля.
        """
        self.input_files = [p for p in self.input_files if p != path]

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

        def on_progress(done: int, total: int, message: str) -> None:
            self.progress = done / max(total, 1)
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
        except Exception as exc:  # noqa: BLE001 — показываем пользователю
            self.error = f"Ошибка: {exc}"
            self.status = "Прервано из-за ошибки"
        finally:
            self.running = False

    def save_zip_to(self, dest: str | None) -> None:
        if dest and self._run_result is not None:
            shutil.copy(self._run_result.zip_path, dest)
            self.status = f"Архив сохранён: {dest}"

    def _dispose_previous(self) -> None:
        if self._run_result is not None:
            self._run_result.cleanup()  # очистка temp прошлого прогона (ТЗ §7.3)
            if self._run_result in _pending_cleanup:
                _pending_cleanup.remove(self._run_result)
            self._run_result = None


def _name(path: Path | None) -> str | None:
    return path.name if path else None


def _counter_pill(count: int) -> ft.Control:
    """Счётчик выбранных файлов в заголовке секции 2."""
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
        border_radius=999,
        padding=ft.Padding.symmetric(horizontal=12, vertical=4),
        content=ft.Text(
            f"файлов: {count}", size=12, weight=ft.FontWeight.W_600,
            color=ft.Colors.PRIMARY,
        ),
    )


@ft.component
def App() -> ft.Control:
    state, _ = ft.use_state(AppState())

    # Регистрируем state в page.data, чтобы клавиатурный обработчик из main()
    # мог добавлять файлы в правильный экземпляр AppState.
    ft.context.page.data["state"] = state

# FilePicker-сервисы (создаются один раз, монтируются в дерево). В Flet 0.85
    # методы pick_files/get_directory_path/save_file асинхронные и возвращают
    # результат напрямую (без on_result).
    db_picker = ft.use_ref(lambda: ft.FilePicker())
    rpd_picker = ft.use_ref(lambda: ft.FilePicker())
    fos_picker = ft.use_ref(lambda: ft.FilePicker())
    files_picker = ft.use_ref(lambda: ft.FilePicker())
    dir_picker = ft.use_ref(lambda: ft.FilePicker())
    save_picker = ft.use_ref(lambda: ft.FilePicker())

    async def pick_db(e: ft.Event[ft.Control]) -> None:
        files = await db_picker.current.pick_files(allow_multiple=False)
        if files:
            state.set_db(files[0].path)

    async def pick_rpd(e: ft.Event[ft.Control]) -> None:
        files = await rpd_picker.current.pick_files(allow_multiple=False)
        if files:
            state.set_rpd(files[0].path)

    async def pick_fos(e: ft.Event[ft.Control]) -> None:
        files = await fos_picker.current.pick_files(allow_multiple=False)
        if files:
            state.set_fos(files[0].path)

    async def pick_inputs(e: ft.Event[ft.Control]) -> None:
        files = await files_picker.current.pick_files(allow_multiple=True)
        if files:
            state.add_files([f.path for f in files])

    async def pick_dir(e: ft.Event[ft.Control]) -> None:
        directory = await dir_picker.current.get_directory_path()
        state.add_dir(directory)

    async def download(e: ft.Event[ft.Control]) -> None:
        dest = await save_picker.current.save_file(file_name="EduConvert_результат.zip")
        state.save_zip_to(dest)

    async def start_conversion(e: ft.Event[ft.Control]) -> None:
        # локальная обёртка: bound-метод observable, переданный в on_click
        # контрола из props компонента, в Flet 0.85 не срабатывает
        await state.start(e)

    # --- Зона 1: базовые файлы --- #
    settings_zone = SectionCard(
        number="1",
        title="Базовые файлы",
        subtitle="База дисциплин и официальные шаблоны 2026",
        content=ft.Column(
            spacing=8,
            controls=[
                UploadCard("База данных (Excel)", _name(state.db_path), state.db_ok,
                           ft.Icons.TABLE_VIEW, pick_db),
                UploadCard("Шаблон РПД (2026)", _name(state.rpd_path), state.rpd_ok,
                           ft.Icons.DESCRIPTION, pick_rpd),
                UploadCard("Шаблон ФОС (2026)", _name(state.fos_path), state.fos_ok,
                           ft.Icons.FACT_CHECK, pick_fos),
            ],
        ),
    )

    # --- Зона 2: исходные документы --- #
    def _do_paste(e: ft.Event[ft.Control]) -> None:
        _paste_clipboard_files(state, ft.context.page)

    pick_buttons: list[ft.Control] = [
        ft.FilledButton("Выбрать файлы", icon=ft.Icons.NOTE_ADD, on_click=pick_inputs),
        ft.OutlinedButton("Выбрать папку", icon=ft.Icons.FOLDER, on_click=pick_dir),
        ft.OutlinedButton("Вставить", icon=ft.Icons.CONTENT_PASTE_ROUNDED,
                          tooltip="Скопируйте файлы в Проводнике (Ctrl+C), затем нажмите кнопку или Ctrl+V",
                          on_click=_do_paste),
    ]
    if state.input_files:  # «Очистить» видна только при непустом списке
        pick_buttons.append(
            ft.TextButton("Очистить", icon=ft.Icons.CLEAR,
                          on_click=lambda e: state.clear_inputs())
        )

    files_zone = SectionCard(
        number="2",
        title="Исходные документы",
        subtitle="Старые РПД и ФОС (.doc / .docx)",
        trailing=_counter_pill(len(state.input_files)),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Container(
                    border=ft.Border.all(2, ft.Colors.OUTLINE_VARIANT),
                    border_radius=12,
                    padding=ft.Padding.symmetric(horizontal=24, vertical=20),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.UPLOAD_FILE, size=40, color=ft.Colors.PRIMARY),
                            ft.Text("Выберите старые файлы РПД и ФОС (или папку с ними)",
                                    size=14, text_align=ft.TextAlign.CENTER),
                            ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=10,
                                   controls=pick_buttons),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=4,
                                controls=[
                                    ft.Icon(ft.Icons.KEYBOARD_ROUNDED, size=13,
                                            color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(
                                        "Ctrl+C в Проводнике → Ctrl+V сюда",
                                        size=11, italic=True,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                FileList(state.input_files, state.remove_file),
            ],
        ),
    )

    # --- Зона 3: конвертация и прогресс --- #
    percent = int(state.progress * 100)
    if state.running:
        progress_block: list[ft.Control] = [
            ft.ProgressBar(value=state.progress, bar_height=8, border_radius=4),
            ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=18, height=18, stroke_width=2.5),
                    ft.Text(f"{percent} %", size=13, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.PRIMARY),
                    # state.status содержит имя обрабатываемого файла
                    # (его пишет колбэк on_progress)
                    ft.Text(state.status, size=13, expand=True, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            color=ft.Colors.ON_SURFACE_VARIANT),
                ],
            ),
        ]
    elif state.status:
        progress_block = [
            ft.Text(state.status, size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        ]
    else:
        progress_block = []

    control_zone = SectionCard(
        number="3",
        title="Конвертация",
        content=ft.Column(
            spacing=12,
            controls=[
                ft.FilledButton(
                    "Начать конвертацию",
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    disabled=not state.ready,
                    on_click=start_conversion,
                    height=48,
                    style=ft.ButtonStyle(
                        text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_600)
                    ),
                ),
                *progress_block,
            ],
        ),
    )

    body: list[ft.Control] = [settings_zone, files_zone, control_zone]

    if state.error:
        body.append(
            ft.Container(
                bgcolor=ft.Colors.ERROR_CONTAINER,
                border_radius=8,
                padding=12,
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE, size=18,
                                color=ft.Colors.ON_ERROR_CONTAINER),
                        ft.Text(state.error, color=ft.Colors.ON_ERROR_CONTAINER,
                                expand=True),
                    ],
                ),
            )
        )

    # --- Зона 4: результаты (появляются с плавным переходом) --- #
    if state.done:
        results_content: ft.Control = ft.Column(
            key="results",
            spacing=0,
            controls=[
                SectionCard(
                    number="4",
                    title="Результаты",
                    subtitle="Отчёт о расхождениях и архив готовых документов",
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ReportTable(state.results),
                            ft.FilledButton(
                                "Скачать результаты (.zip)",
                                icon=ft.Icons.DOWNLOAD,
                                on_click=download,
                            ),
                        ],
                    ),
                ),
            ],
        )
    else:
        results_content = ft.Container(key="empty", height=0)

    body.append(
        ft.AnimatedSwitcher(
            duration=ft.Duration(milliseconds=250),  # дефолт 1 с — слишком медленно
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
            transition=ft.AnimatedSwitcherTransition.FADE,
            content=results_content,
        )
    )

    # --- шапка: градиент фирменных синих ГУУ + версия --- #
    header = ft.Container(
        gradient=ft.LinearGradient(
            begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT,
            colors=[theme.GUU_BLUE, theme.GUU_BLUE_BRIGHT],
        ),
        padding=ft.Padding.symmetric(horizontal=28, vertical=18),
        content=ft.Row(
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=52,
                    height=52,
                    border_radius=26,
                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.SWAP_HORIZONTAL_CIRCLE_OUTLINED,
                                    size=34, color=ft.Colors.WHITE),
                ),
                ft.Column(
                    spacing=2,
                    tight=True,
                    expand=True,
                    controls=[
                        ft.Text("EduConvert", size=24, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE),
                        ft.Text(
                            "Конвертация РПД и ФОС в шаблоны 2026",
                            size=13,
                            color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),
                        ),
                    ],
                ),
                ft.Container(
                    border_radius=999,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                    content=ft.Text(f"v{__version__}", size=11, color=ft.Colors.WHITE),
                ),
            ],
        ),
    )

    # FilePicker — это сервисы, а не визуальные контролы: создаются через use_ref
    # (автоматически регистрируются на странице) и НЕ добавляются в дерево controls.
    return ft.Column(
        expand=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # шапка во всю ширину
        controls=[
            header,
            ft.Container(
                expand=True,
                alignment=ft.Alignment.TOP_CENTER,
                padding=ft.Padding.symmetric(horizontal=24, vertical=20),
                # ширина контента ограничена: на широких экранах (веб)
                # колонка не растягивается во весь вьюпорт
                content=ft.Container(
                    width=880,
                    content=ft.Column(body, spacing=16, scroll=ft.ScrollMode.AUTO),
                ),
            ),
        ],
    )


def main(page: ft.Page) -> None:
    """Точка входа Flet-приложения."""
    page.title = "EduConvert — конвертер РПД и ФОС"
    page.theme_mode = ft.ThemeMode.LIGHT  # только светлая тема (решение кафедры)
    page.theme = theme.build_theme()
    page.padding = 0
    page.data = {}  # разделяемый словарь между main() и компонентами

    if not page.web:  # свойства окна применимы только на десктопе
        page.window.width = 920
        page.window.height = 780
        page.window.min_width = 760
        page.window.min_height = 620
        page.window.alignment = ft.Alignment.CENTER

    async def on_keyboard(e: ft.KeyboardEvent) -> None:
        state: AppState | None = page.data.get("state")
        if e.ctrl and e.key.lower() == "v" and state is not None:
            _paste_clipboard_files(state, page)

    page.on_keyboard_event = on_keyboard
    page.render(App)


def run_desktop() -> None:
    """Запуск настольного приложения."""
    ft.run(main)


if __name__ == "__main__":
    run_desktop()
