"""Тесты Excel-парсера (лист «План») на синтетической Базе."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.excel_parser import load_repository
from app.core.exceptions import SubjectNotFoundError
from app.core.models import ControlKind


def test_load_count(plan_xlsx: Path) -> None:
    repo = load_repository(plan_xlsx)
    assert repo.count == 2  # строка-заголовок «Обязательная часть» игнорируется


def test_subject_single_semester(plan_xlsx: Path) -> None:
    s = load_repository(plan_xlsx).get_subject("Б1.О.01")
    assert s.name == "Методология научных исследований"
    assert s.ze == 3.0
    assert s.hours_total == 108
    assert s.hours_contact == 30
    assert s.hours_lectures == 12
    assert s.hours_practical == 10
    assert s.hours_project == 6
    assert s.hours_srs == 78
    assert s.hours_aud == 28  # 12 + 0 + 10 + 6
    assert s.control_forms[0].kind == ControlKind.CREDIT
    assert s.control_forms[0].semester == 1
    assert s.semesters == (1,)
    assert s.competence_codes == ("УК-1-И-1", "ПК-2-И-1")
    assert s.department == "01"
    assert s.department_name == "Тестовая кафедра"


def test_subject_second_semester_block(plan_xlsx: Path) -> None:
    # Лек/Пр лежат во втором блоке семестра — проверяем суммирование по блокам.
    s = load_repository(plan_xlsx).get_subject("Б1.В.ДВ.03.01")
    assert s.ze == 6.0
    assert s.hours_total == 216
    assert s.hours_lectures == 12
    assert s.hours_practical == 22
    assert s.hours_project == 12
    assert s.hours_control == 60
    assert s.control_forms[0].kind == ControlKind.EXAM
    assert s.control_forms[0].semester == 2
    assert s.per_semester[0].semester == 2
    assert s.per_semester[0].lectures == 12


def test_index_lookup_normalized(plan_xlsx: Path) -> None:
    repo = load_repository(plan_xlsx)
    assert repo.has_subject("б1.о.01") is True
    assert repo.get_subject("Б1_О_01").index == "Б1.О.01"


def test_subject_not_found(plan_xlsx: Path) -> None:
    repo = load_repository(plan_xlsx)
    assert repo.has_subject("Б9.Z.99") is False
    with pytest.raises(SubjectNotFoundError):
        repo.get_subject("Б9.Z.99")
