"""Главный экран EduConvert (Flet, декларативный подход, Material Design 3).

Состояние приложения — реактивный объект :class:`AppState` (``@ft.observable``):
мутация его полей автоматически перерисовывает UI без ручных ``page.update()``.
Тяжёлая конвертация выполняется асинхронно через оркестратор; прогресс
обновляется колбэком, меняющим поля состояния (ТЗ §5).
"""

from __future__ import annotations

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
            self._run_result = None


def _name(path: Path | None) -> str | None:
    return path.name if path else None


@ft.component
def App() -> ft.Control:
    state, _ = ft.use_state(AppState())

    # FilePicker-сервисы (создаются один раз, монтируются в дерево).
    db_picker = ft.use_ref(
        lambda: ft.FilePicker(on_result=lambda e: state.set_db(e.files[0].path if e.files else None))
    )
    rpd_picker = ft.use_ref(
        lambda: ft.FilePicker(on_result=lambda e: state.set_rpd(e.files[0].path if e.files else None))
    )
    fos_picker = ft.use_ref(
        lambda: ft.FilePicker(on_result=lambda e: state.set_fos(e.files[0].path if e.files else None))
    )
    files_picker = ft.use_ref(
        lambda: ft.FilePicker(
            on_result=lambda e: state.add_files([f.path for f in e.files] if e.files else [])
        )
    )
    dir_picker = ft.use_ref(
        lambda: ft.FilePicker(on_result=lambda e: state.add_dir(e.path))
    )
    save_picker = ft.use_ref(
        lambda: ft.FilePicker(on_result=lambda e: state.save_zip_to(e.path))
    )

    # --- Зона 1: настройки --- #
    settings_zone = ft.Column(
        spacing=8,
        controls=[
            ft.Text("1. Базовые файлы", size=16, weight=ft.FontWeight.BOLD),
            UploadCard("База данных (Excel)", _name(state.db_path), state.db_ok,
                       ft.Icons.TABLE_VIEW,
                       lambda e: db_picker.current.pick_files(allow_multiple=False)),
            UploadCard("Шаблон РПД (2026)", _name(state.rpd_path), state.rpd_ok,
                       ft.Icons.DESCRIPTION,
                       lambda e: rpd_picker.current.pick_files(allow_multiple=False)),
            UploadCard("Шаблон ФОС (2026)", _name(state.fos_path), state.fos_ok,
                       ft.Icons.FACT_CHECK,
                       lambda e: fos_picker.current.pick_files(allow_multiple=False)),
        ],
    )

    # --- Зона 2: рабочая область (выбор исходников) --- #
    drop_zone = ft.Container(
        border=ft.border.all(2, ft.Colors.OUTLINE_VARIANT),
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
                                        on_click=lambda e: files_picker.current.pick_files(allow_multiple=True)),
                        ft.OutlinedButton("Выбрать папку", icon=ft.Icons.FOLDER,
                                          on_click=lambda e: dir_picker.current.get_directory_path()),
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
                on_click=lambda e: save_picker.current.save_file(
                    file_name="EduConvert_результат.zip"
                ),
            ),
        ]

    header = ft.Container(
        bgcolor=ft.Colors.PRIMARY_CONTAINER,
        padding=ft.Padding.symmetric(horizontal=24, vertical=16),
        content=ft.Column(
            spacing=2,
            controls=[
                ft.Text("EduConvert", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("Конвертация РПД и ФОС в шаблоны 2026 — числа из Базы, текст из исходников",
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )

    return ft.Column(
        expand=True,
        spacing=0,
        controls=[
            # невидимые сервисы-пикеры
            db_picker.current, rpd_picker.current, fos_picker.current,
            files_picker.current, dir_picker.current, save_picker.current,
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
