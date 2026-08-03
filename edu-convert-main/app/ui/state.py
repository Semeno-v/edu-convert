"""Реактивное состояние главного экрана EduConvert.

Отделено от разметки (:mod:`app.ui.main_view`) намеренно: здесь живёт вся
тестируемая логика — какие файлы принимаются, когда доступен запуск, что
показывать в строках списка, — и её можно проверять и типизировать без
запуска Flet. Разметка же почти не поддаётся ни тому, ни другому.

Состояние помечено ``@ft.observable``: присваивание поля само перерисовывает
интерфейс, ручной ``page.update()`` не нужен (ТЗ §5).
"""

from __future__ import annotations

import asyncio
import atexit
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import flet as ft

from app.config import settings
from app.core.models import FileResult, FileStatus
from app.services.orchestrator import Orchestrator, RunResult
from app.ui import persistence
from app.ui.components import file_list as fl
from app.ui.components import help_sheet

_INPUT_SUFFIXES = {".doc", ".docx"}

SETUP = "setup"
RESULTS = "results"


def plural_files(n: int) -> str:
    """«1 файл», «2 файла», «5 файлов» — правила русского языка."""
    if 11 <= (n % 100) <= 14:
        return f"{n} файлов"
    r = n % 10
    if r == 1:
        return f"{n} файл"
    if 2 <= r <= 4:
        return f"{n} файла"
    return f"{n} файлов"


def skip_reason(paths: list[str]) -> str:
    """Почему из выбранного ничего не добавилось.

    Раньше на любой отказ показывалось «Эти файлы уже в списке». При вставке
    из буфера чего-то постороннего — картинки, PDF — сообщение сбивало с толку:
    пользователь искал файлы в списке, которых там никогда не было.
    """
    if any(Path(p).suffix.lower() in _INPUT_SUFFIXES for p in paths):
        return "Эти файлы уже в списке"
    return "Подходят только файлы .doc и .docx"


def make_initial_state() -> AppState:
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
    help_phase: str = help_sheet.CLOSED
    # Ширина окна живёт в состоянии, а не читается из page.width во время
    # сборки: ``page.update()`` перерисовывает уже готовое дерево, но не
    # перезапускает компонент, поэтому раскладка застывала на старой ширине
    # и «догоняла» окно только при следующей смене состояния — отсюда рывок.
    width: float = 0.0
    # Высота нужна справке: карточка ограничивает свой список высотой окна,
    # иначе на невысоком экране нижние строки уходят за край без прокрутки.
    height: float = 0.0

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
    def file_states(self) -> dict[int, str]:
        """Состояние каждой строки списка файлов (очередь/работа/итог).

        Ключ — порядковый номер файла, а не имя: имена не уникальны. Два
        «РПД.docx» из разных папок делили одну запись, и обе строки показывали
        состояние того файла, который обработался последним — при ошибке
        в одном из них галочка «готово» стояла у обоих. Оркестратор кладёт
        ровно один результат на каждый вход и в том же порядке, поэтому
        позиция совпадает с индексом результата.
        """
        if self.results:
            by_status = {
                FileStatus.SUCCESS: fl.DONE,
                FileStatus.DISCREPANCY: fl.WARN,
                FileStatus.ERROR: fl.FAILED,
            }
            return {i: by_status[r.status] for i, r in enumerate(self.results)}
        if not self.running:
            return {}
        states: dict[int, str] = {}
        for i in range(len(self.input_files)):
            if i < self.processed:
                states[i] = fl.DONE
            elif i == self.processed:
                states[i] = fl.RUNNING
            else:
                states[i] = fl.QUEUED
        return states

    # --- мутации --- #
    # Каждый мутатор начинается со сброса ``error``: сообщение об ошибке
    # относится к конкретной неудавшейся попытке, а раньше гасло только при
    # запуске конвертации. Из-за этого «Не удалось прочитать папку» висело
    # красной плашкой и после того, как пользователь успешно выбрал файлы
    # другим способом. Присвоение того же ``""`` ничего не стоит: observable
    # шлёт уведомление только при фактическом изменении значения.
    def set_db(self, path: str | None) -> None:
        self.error = ""
        if path:
            self.db_path = Path(path)

    def set_rpd(self, path: str | None) -> None:
        self.error = ""
        if path:
            self.rpd_path = Path(path)

    def set_fos(self, path: str | None) -> None:
        self.error = ""
        if path:
            self.fos_path = Path(path)

    def add_files(self, paths: list[str]) -> int:
        """Добавляет .doc/.docx, пропуская дубли; возвращает число добавленных."""
        self.error = ""
        existing = {str(p) for p in self.input_files}
        new = [
            Path(p) for p in paths
            if p and p not in existing and Path(p).suffix.lower() in _INPUT_SUFFIXES
        ]
        if new:
            self.input_files = [*self.input_files, *new]
        return len(new)

    def add_dir(self, directory: str | None) -> int:
        self.error = ""
        if not directory:
            return 0
        try:
            entries = sorted(Path(directory).iterdir())
        except OSError as exc:
            # Папка может быть недоступна на чтение или уже удалена. Без этой
            # ветки исключение уходило в обработчик события: список не менялся,
            # сообщения не было — папка просто «не добавлялась» без объяснений.
            self.error = f"Не удалось прочитать папку: {exc}"
            return 0
        found = [
            p for p in entries
            if p.suffix.lower() in _INPUT_SUFFIXES and not p.name.startswith("~$")
        ]
        return self.add_files([str(p) for p in found])

    def clear_inputs(self) -> None:
        self.error = ""
        self.input_files = []

    def remove_file(self, path: Path) -> None:
        """Убирает один файл из списка.

        Список переприсваивается (не мутируется in-place): ``@ft.observable``
        реагирует только на присваивание поля.
        """
        self.error = ""
        self.input_files = [p for p in self.input_files if p != path]

    def toggle_theme(self) -> None:
        self.dark = not self.dark
        persistence.save_dark_mode(self.dark)

    # --- запуск конвертации --- #
    async def start(self, e: ft.Event[ft.Control] | None = None) -> None:
        # ``ready`` уже гарантирует, что план выбран, но проверка типов этого не
        # видит: db_ok — property. Забираем путь в локальную переменную, чтобы
        # сужение типа было явным.
        db_path = self.db_path
        if not self.ready or db_path is None:
            return
        # Всё, что осталось от прошлого прогона, гасим до очистки, а не после:
        # удаление прошлой выдачи занимает заметное время, и всё это время в
        # строке состояния иначе висело бы «Готово: успешно N…» от предыдущего
        # запуска поверх уже начавшегося нового.
        self.running = True
        self.done = False
        self.error = ""
        self.results = []
        self.progress = 0.0
        self.processed = 0
        self.status = "Подготовка…"
        self.view = SETUP
        await self._dispose_previous()

        def on_progress(done: int, total: int, message: str) -> None:
            self.progress = done / max(total, 1)
            self.processed = done
            self.status = message

        try:
            orch = Orchestrator(db_path, self.rpd_path, self.fos_path)
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

    async def save_zip_to(self, dest: str | None) -> Path | None:
        """Копирует архив результатов по выбранному пути.

        Копирование уходит в поток: архив с сотней документов весит десятки
        мегабайт, и синхронный ``shutil.copy`` прямо в обработчике замораживал
        весь интерфейс на время записи — окно переставало перерисовываться,
        и выглядело это как зависшее приложение.
        """
        if dest and self._run_result is not None:
            await asyncio.to_thread(shutil.copy, self._run_result.zip_path, dest)
            return Path(dest)
        return None

    async def _dispose_previous(self) -> None:
        """Убирает временную папку прошлого прогона (ТЗ §7.3).

        Удаление уходит в поток по той же причине, что и копирование архива
        выше: в папке лежит сотня сгенерированных .docx плюс ZIP, и
        синхронный ``rmtree`` прямо здесь замораживал интерфейс на старте
        каждой повторной конвертации.
        """
        if self._run_result is not None:
            stale = self._run_result
            self._run_result = None
            await asyncio.to_thread(stale.cleanup)
            # Из списка на аварийную уборку снимаем только после удаления:
            # оборвись процесс посреди rmtree, папку добьёт atexit-обработчик.
            if stale in _pending_cleanup:
                _pending_cleanup.remove(stale)
