"""Главный экран EduConvert (Flet, декларативный подход, Material Design 3).

Состояние приложения — реактивный объект :class:`AppState` (``@ft.observable``):
мутация его полей автоматически перерисовывает UI без ручных ``page.update()``.
Тяжёлая конвертация выполняется асинхронно через оркестратор; прогресс
обновляется колбэком, меняющим поля состояния (ТЗ §5).
"""

from __future__ import annotations

import atexit
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import flet as ft

from app.config import settings
from app.core.models import FileResult
from app.services.orchestrator import Orchestrator, RunResult
from app.ui.components.report_table import ReportTable
from app.ui.components.upload_card import UploadCard

_INPUT_SUFFIXES = {".doc", ".docx"}

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


@ft.component
def App() -> ft.Control:
    state, _ = ft.use_state(AppState())

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

    # --- Зона 1: настройки --- #
    settings_zone = ft.Column(
        spacing=8,
        controls=[
            ft.Text("1. Базовые файлы", size=16, weight=ft.FontWeight.BOLD),
            UploadCard("База данных (Excel)", _name(state.db_path), state.db_ok,
                       ft.Icons.TABLE_VIEW, pick_db),
            UploadCard("Шаблон РПД (2026)", _name(state.rpd_path), state.rpd_ok,
                       ft.Icons.DESCRIPTION, pick_rpd),
            UploadCard("Шаблон ФОС (2026)", _name(state.fos_path), state.fos_ok,
                       ft.Icons.FACT_CHECK, pick_fos),
        ],
    )

    # --- Зона 2: рабочая область (выбор исходников) --- #
    drop_zone = ft.Container(
        border=ft.Border.all(2, ft.Colors.OUTLINE_VARIANT),
        border_radius=12,
        padding=24,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.UPLOAD_FILE, size=46, color=ft.Colors.PRIMARY),
                ft.Text("Выберите старые файлы РПД и ФОС (или папку с ними)",
                        size=14, text_align=ft.TextAlign.CENTER),
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.FilledButton("Выбрать файлы", icon=ft.Icons.NOTE_ADD,
                                        on_click=pick_inputs),
                        ft.OutlinedButton("Выбрать папку", icon=ft.Icons.FOLDER,
                                          on_click=pick_dir),
                        ft.TextButton("Очистить", icon=ft.Icons.CLEAR,
                                      on_click=lambda e: state.clear_inputs()),
                    ],
                ),
                ft.Text(f"Загружено файлов: {len(state.input_files)}",
                        size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
            ],
        ),
    )

    # --- Зона 3: управление и статус --- #
    control_zone = ft.Column(
        spacing=10,
        controls=[
            ft.FilledButton(
                "Начать конвертацию",
                icon=ft.Icons.PLAY_ARROW,
                disabled=not state.ready,
                on_click=state.start,
                height=46,
            ),
            ft.ProgressBar(value=state.progress, visible=state.running),
            ft.Text(state.status, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ],
    )

    body: list[ft.Control] = [
        settings_zone,
        ft.Divider(),
        ft.Text("2. Исходные документы", size=16, weight=ft.FontWeight.BOLD),
        drop_zone,
        ft.Divider(),
        control_zone,
    ]

    if state.error:
        body.append(
            ft.Container(
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED),
                border_radius=8, padding=12,
                content=ft.Text(state.error, color=ft.Colors.RED),
            )
        )

    # --- Зона 4: результаты --- #
    if state.done:
        body += [
            ft.Divider(),
            ft.Text("3. Результаты", size=16, weight=ft.FontWeight.BOLD),
            ReportTable(state.results),
            ft.FilledButton(
                "Скачать результаты (.zip)",
                icon=ft.Icons.DOWNLOAD,
                on_click=download,
            ),
        ]

    on_primary = ft.Colors.ON_PRIMARY
    header = ft.Container(
        bgcolor=ft.Colors.PRIMARY,
        padding=ft.Padding.symmetric(horizontal=28, vertical=18),
        content=ft.Row(
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.SWAP_HORIZONTAL_CIRCLE_OUTLINED, size=40, color=on_primary),
                ft.Column(
                    spacing=2,
                    tight=True,
                    controls=[
                        ft.Text("EduConvert", size=24, weight=ft.FontWeight.BOLD, color=on_primary),
                        ft.Text(
                            "Конвертация РПД и ФОС в шаблоны 2026",
                            size=13,
                            color=ft.Colors.with_opacity(0.85, on_primary),
                        ),
                    ],
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
                padding=24,
                content=ft.Column(body, spacing=16, scroll=ft.ScrollMode.AUTO),
            ),
        ],
    )


def main(page: ft.Page) -> None:
    """Точка входа Flet-приложения."""
    page.title = "EduConvert — конвертер РПД и ФОС"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)
    page.padding = 0
    page.render(App)


def run_desktop() -> None:
    """Запуск настольного приложения."""
    ft.run(main)


if __name__ == "__main__":
    run_desktop()
