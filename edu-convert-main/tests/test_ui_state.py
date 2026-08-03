"""Состояние интерфейса (ui/state.py) — логика без отрисовки.

Проверяются места, где ошибка не приводит к падению и потому не видна:
неверная подсказка при отказе, состояние строк у одноимённых файлов,
недоступная папка, а также условия доступности запуска и уборка временных
файлов прошлого прогона.
"""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from app.core.models import FileResult, FileStatus
from app.services.orchestrator import RunResult
from app.ui import persistence
from app.ui import state as state_mod
from app.ui.components import file_list as fl
from app.ui.state import AppState, make_initial_state, plural_files, skip_reason


def test_skip_reason_distinguishes_wrong_format_from_duplicate() -> None:
    """«Уже в списке» — только когда файлы действительно подходящего формата."""
    assert skip_reason(["/tmp/РПД.docx"]) == "Эти файлы уже в списке"
    assert skip_reason(["/tmp/скан.pdf"]) == "Подходят только файлы .doc и .docx"
    assert skip_reason(["/tmp/скан.pdf", "/tmp/РПД.doc"]) == "Эти файлы уже в списке"


def test_file_states_separate_for_same_named_files() -> None:
    """Одноимённые файлы из разных папок — разные строки и разные состояния.

    Ключ по имени сливал их в одну запись: обе строки показывали итог того
    файла, который обработался последним.
    """
    state = AppState()
    state.input_files = [Path("/каф_А/РПД.docx"), Path("/каф_Б/РПД.docx")]
    state.results = [
        FileResult(filename="РПД.docx", status=FileStatus.SUCCESS),
        FileResult(filename="РПД.docx", status=FileStatus.ERROR),
    ]

    assert state.file_states == {0: fl.DONE, 1: fl.FAILED}


def test_file_states_during_run_marks_only_current() -> None:
    state = AppState()
    state.input_files = [Path(f"/x/{i}.docx") for i in range(3)]
    state.running = True
    state.processed = 1

    assert state.file_states == {0: fl.DONE, 1: fl.RUNNING, 2: fl.QUEUED}


def test_add_dir_reports_unreadable_directory(tmp_path: Path) -> None:
    """Недоступная папка объясняется пользователю, а не проглатывается."""
    state = AppState()

    assert state.add_dir(str(tmp_path / "нет-такой")) == 0
    assert state.error and "папку" in state.error


def test_add_dir_skips_word_lock_files(tmp_path: Path) -> None:
    (tmp_path / "РПД.docx").touch()
    (tmp_path / "~$РПД.docx").touch()
    (tmp_path / "заметки.txt").touch()
    state = AppState()

    assert state.add_dir(str(tmp_path)) == 1
    assert [p.name for p in state.input_files] == ["РПД.docx"]


def test_successful_action_clears_previous_error(tmp_path: Path) -> None:
    """Сообщение об ошибке гаснет на следующем удачном действии.

    Раньше оно сбрасывалось только в start(): красная плашка о недоступной
    папке висела и после того, как файлы были успешно добавлены вручную.
    """
    (tmp_path / "РПД.docx").touch()
    state = AppState()
    state.add_dir(str(tmp_path / "нет-такой"))
    assert state.error

    assert state.add_files([str(tmp_path / "РПД.docx")]) == 1
    assert state.error == ""


def test_every_mutator_clears_error(tmp_path: Path) -> None:
    """Сбрасывает каждый мутатор, а не только добавление файлов."""
    db = tmp_path / "база.xlsx"
    db.touch()
    for mutate in (
        lambda s: s.set_db(str(db)),
        lambda s: s.set_rpd(str(db)),
        lambda s: s.set_fos(str(db)),
        lambda s: s.add_dir(str(tmp_path)),
        lambda s: s.clear_inputs(),
        lambda s: s.remove_file(Path("/x/нет.docx")),
    ):
        state = AppState()
        state.error = "прошлая ошибка"
        mutate(state)
        assert state.error == ""


# --------------------------------------------------------------------------- #
#  Доступность запуска
# --------------------------------------------------------------------------- #
def test_blocked_reason_names_the_missing_piece(tmp_path: Path, plan_xlsx: Path) -> None:
    """Подсказка на кнопке называет ровно то, чего не хватает сейчас."""
    state = AppState()
    assert not state.ready
    assert state.blocked_reason == "Выберите учебный план и оба шаблона 2026"

    state.set_db(str(plan_xlsx))  # шаблоны берутся из settings и существуют
    assert state.sources_ok
    assert state.blocked_reason == "Добавьте хотя бы один файл РПД или ФОС"

    doc = tmp_path / "РПД.docx"
    doc.touch()
    state.add_files([str(doc)])
    assert state.ready
    assert state.blocked_reason is None

    state.running = True
    assert not state.ready
    assert state.blocked_reason == "Идёт конвертация…"


def test_missing_template_blocks_start(tmp_path: Path, plan_xlsx: Path) -> None:
    # Шаблон могли переместить между запусками: путь сохранён, файла уже нет.
    state = AppState()
    state.set_db(str(plan_xlsx))
    state.set_rpd(str(tmp_path / "исчез.docx"))
    assert not state.rpd_ok
    assert not state.sources_ok


# --------------------------------------------------------------------------- #
#  Восстановление путей из настроек
# --------------------------------------------------------------------------- #
def test_initial_state_restores_only_existing_paths(
    tmp_path: Path, plan_xlsx: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Пропавший файл не подставляется: иначе запуск падал бы уже после нажатия."""
    monkeypatch.setattr(persistence, "_SETTINGS_PATH", tmp_path / "settings.json")
    persistence.save_paths(str(plan_xlsx), str(tmp_path / "нет_шаблона.docx"), "")

    state = make_initial_state()
    assert state.db_path == plan_xlsx
    assert state.rpd_path != tmp_path / "нет_шаблона.docx"  # остался путь по умолчанию


# --------------------------------------------------------------------------- #
#  Склонение числительных
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "1 файл"), (2, "2 файла"), (4, "4 файла"), (5, "5 файлов"),
     (11, "11 файлов"), (14, "14 файлов"), (21, "21 файл"), (102, "102 файла"),
     (111, "111 файлов"), (0, "0 файлов")],
)
def test_plural_files(count: int, expected: str) -> None:
    assert plural_files(count) == expected


# --------------------------------------------------------------------------- #
#  Уборка временных файлов
# --------------------------------------------------------------------------- #
def _spent_run(tmp_path: Path, name: str) -> RunResult:
    workdir = tmp_path / name
    workdir.mkdir()
    (workdir / "РПД.docx").touch()
    zip_path = tmp_path / f"{name}.zip"
    zip_path.touch()
    return RunResult(report=None, zip_path=zip_path, workdir=workdir)  # type: ignore[arg-type]


def test_dispose_previous_removes_workdir_and_forgets_it(tmp_path: Path) -> None:
    """Повторный запуск убирает выдачу прошлого и снимает её с аварийной уборки."""
    stale = _spent_run(tmp_path, "run_1")
    state = AppState()
    state._run_result = stale
    state_mod._pending_cleanup.append(stale)

    anyio.run(state._dispose_previous)

    assert not stale.workdir.exists()
    assert not stale.zip_path.exists()
    assert state._run_result is None
    assert stale not in state_mod._pending_cleanup


def test_start_clears_previous_status_before_disposing(
    tmp_path: Path, plan_xlsx: Path
) -> None:
    """Итог прошлого прогона гаснет до уборки, а не после неё.

    Уборка выдачи с сотней документов длится несколько секунд, и всё это время
    в строке состояния висело «Готово: успешно N…» от предыдущего запуска —
    поверх уже начавшегося нового.
    """
    seen: list[tuple[bool, str, float]] = []
    state = AppState()
    state.db_path = plan_xlsx
    state.input_files = [str(tmp_path / "РПД.docx")]
    state._run_result = _spent_run(tmp_path, "run_1")
    state.status = "Готово: успешно 3, расхождений 0, ошибок 0"
    state.progress = 1.0
    state.done = True

    async def spy() -> None:
        seen.append((state.running, state.status, state.progress))

    state._dispose_previous = spy  # type: ignore[method-assign]
    # Оркестратор до работы не дойдёт: РПД.docx не существует, и start()
    # свалится в except. Нас интересует только состояние на входе в уборку.
    anyio.run(state.start)

    assert seen == [(True, "Подготовка…", 0.0)]


def test_cleanup_pending_clears_everything_at_exit(tmp_path: Path) -> None:
    # atexit-обработчик — последняя линия: без него временные папки оставались
    # на диске навсегда (ТЗ §7.3).
    runs = [_spent_run(tmp_path, f"run_{i}") for i in range(2)]
    state_mod._pending_cleanup.extend(runs)

    state_mod._cleanup_pending()

    assert state_mod._pending_cleanup == []
    assert all(not r.workdir.exists() for r in runs)


def test_save_zip_copies_archive(tmp_path: Path) -> None:
    run = _spent_run(tmp_path, "run_1")
    run.zip_path.write_bytes(b"PK\x03\x04")
    state = AppState()
    state._run_result = run
    dest = tmp_path / "выгрузка.zip"

    assert anyio.run(state.save_zip_to, str(dest)) == dest
    assert dest.read_bytes() == b"PK\x03\x04"


def test_save_zip_without_result_does_nothing(tmp_path: Path) -> None:
    assert anyio.run(AppState().save_zip_to, str(tmp_path / "нет.zip")) is None
