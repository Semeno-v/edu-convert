"""Тесты сравнения старых чисел с эталоном (отчёт о расхождениях)."""

from __future__ import annotations

from app.core.differ import compute_diffs
from app.core.models import ControlForm, ControlKind, OldNumbers, SubjectData


def _subject(**kw: object) -> SubjectData:
    base = dict(
        index="Б1.О.01", name="Тест", ze=3.0, hours_total=108,
        hours_lectures=12, hours_practical=10, hours_lab=0, hours_project=6,
        control_forms=(ControlForm(kind=ControlKind.CREDIT, semester=1),),
    )
    base.update(kw)
    return SubjectData(**base)


def test_no_diffs_when_match() -> None:
    old = OldNumbers(ze=3, hours_total=108, hours_lectures=12, hours_practical=10, semester=1,
                     control_raw="Зачет")
    assert compute_diffs(old, _subject()) == []


def test_lecture_discrepancy() -> None:
    old = OldNumbers(hours_lectures=14)
    diffs = compute_diffs(old, _subject())
    assert len(diffs) == 1
    assert diffs[0].field == "Лекции, часов"
    assert diffs[0].old_value == "14"
    assert diffs[0].new_value == "12"


def test_multiple_numeric_discrepancies() -> None:
    old = OldNumbers(ze=4, hours_total=144, hours_lectures=16, hours_practical=32)
    diffs = compute_diffs(old, _subject())
    fields = {d.field for d in diffs}
    assert fields == {"Зачётные единицы (з.е.)", "Всего часов", "Лекции, часов", "Практические, часов"}


def test_none_fields_skipped() -> None:
    # Все старые числа None → нет расхождений (нечего сравнивать).
    assert compute_diffs(OldNumbers(), _subject()) == []


def test_semester_discrepancy() -> None:
    old = OldNumbers(semester=3)
    diffs = compute_diffs(old, _subject())
    assert any(d.field == "Семестр" for d in diffs)


def test_control_form_discrepancy() -> None:
    old = OldNumbers(control_raw="Экзамен")
    diffs = compute_diffs(old, _subject())
    assert any(d.field == "Форма контроля" for d in diffs)


def test_control_form_match_no_diff() -> None:
    old = OldNumbers(control_raw="зачёт")  # с «ё», другой регистр
    assert all(d.field != "Форма контроля" for d in compute_diffs(old, _subject()))


def test_ze_float_formatting() -> None:
    old = OldNumbers(ze=4)
    diffs = compute_diffs(old, _subject())
    rec = next(d for d in diffs if d.field == "Зачётные единицы (з.е.)")
    assert rec.old_value == "4" and rec.new_value == "3"
