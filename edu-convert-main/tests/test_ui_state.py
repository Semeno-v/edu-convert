"""Состояние интерфейса (ui/main_view.py) — логика без отрисовки.

Проверяются места, где ошибка не приводит к падению и потому не видна:
неверная подсказка при отказе, состояние строк у одноимённых файлов
и недоступная папка.
"""

from __future__ import annotations

from pathlib import Path

from app.core.models import FileResult, FileStatus
from app.ui.components import file_list as fl
from app.ui.main_view import AppState, _skip_reason


def test_skip_reason_distinguishes_wrong_format_from_duplicate() -> None:
    """«Уже в списке» — только когда файлы действительно подходящего формата."""
    assert _skip_reason(["/tmp/РПД.docx"]) == "Эти файлы уже в списке"
    assert _skip_reason(["/tmp/скан.pdf"]) == "Подходят только файлы .doc и .docx"
    assert _skip_reason(["/tmp/скан.pdf", "/tmp/РПД.doc"]) == "Эти файлы уже в списке"


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
