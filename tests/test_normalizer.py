"""Тесты нормализатора (цель ≥95% покрытия, ТЗ §7.5).

Параметризация покрывает граничные условия: «ё»/регистр, варианты индексов
и разделителей, разбор «108 (3)», безопасное приведение чисел.
"""

from __future__ import annotations

import pytest

from app.core import normalizer as nz


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Зачёт", "зачет"),
        ("ЗАЧЁТ С ОЦЕНКОЙ", "зачет с оценкой"),
        ("  много   пробелов  ", "много пробелов"),
        ("Ёлка и ёж", "елка и еж"),
        ("", ""),
    ],
)
def test_normalize_text(text: str, expected: str) -> None:
    assert nz.normalize_text(text) == expected


def test_normalize_text_none() -> None:
    assert nz.normalize_text(None) == ""


@pytest.mark.parametrize(
    ("a", "b"),
    [("зачёт", "Зачет"), ("ЁЖ", "еж"), ("Экзамен", "ЭКЗАМЕН")],
)
def test_fold_yo_case_insensitive_equiv(a: str, b: str) -> None:
    assert nz.normalize_text(a) == nz.normalize_text(b)


@pytest.mark.parametrize(
    ("haystack", "keyword", "expected"),
    [
        ("Форма контроля: Зачёт", "зачет", True),
        ("Лекционные занятия", "практические", False),
        ("Общая трудоёмкость", "трудоемкость", True),
    ],
)
def test_contains_keyword(haystack: str, keyword: str, expected: bool) -> None:
    assert nz.contains_keyword(haystack, keyword) is expected


def test_contains_any() -> None:
    assert nz.contains_any("Зачёт с оценкой", ["экзамен", "зачет"]) is True
    assert nz.contains_any("Лекции", ["экзамен", "зачет"]) is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Б1_О_01", "Б1.О.01"),
        ("б1.о.01 ", "Б1.О.01"),
        ("Б1 В ДВ 03 01", "Б1.В.ДВ.03.01"),
        ("Б1.В.ДВ.03.01", "Б1.В.ДВ.03.01"),
        ("Б1-О-01", "Б1.О.01"),
        ("", ""),
    ],
)
def test_normalize_index(raw: str, expected: str) -> None:
    assert nz.normalize_index(raw) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("Б1_О_01_РПД_Методология_научных_исследований.docx", "Б1.О.01"),
        ("Б1_В_ДВ_03_01_РПД_Эксплуатация.docx", "Б1.В.ДВ.03.01"),
        ("ФОС_Б1_В_ДВ_02_02_Модели.doc", "Б1.В.ДВ.02.02"),
        ("ФОС_Б1_О_01_Методология.docx", "Б1.О.01"),
        ("РПД_Б1_В_05_Инфраструктура.docx", "Б1.В.05"),
        ("ФТД_01_РПД_Русский_язык_в_специальных_целях_экономика.docx", "ФТД.01"),
        ("ФОС_ФТД_02_Создание_приложений.docx", "ФТД.02"),
        ("случайный_файл.docx", None),
        ("", None),
    ],
)
def test_index_from_filename(filename: str, expected: str | None) -> None:
    assert nz.index_from_filename(filename) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Б1.О.01 МЕТОДОЛОГИЯ НАУЧНЫХ", "Б1.О.01"),
        ("шум Б1.В.ДВ.02.02 Модели", "Б1.В.ДВ.02.02"),
        ("ФТД.01 Русский язык в специальных целях", "ФТД.01"),
        ("текст без индекса", None),
    ],
)
def test_index_from_text(text: str, expected: str | None) -> None:
    assert nz.index_from_text(text) == expected


def test_index_from_text_does_not_eat_following_word() -> None:
    # «01 МЕТОДОЛОГИЯ» не должно превратиться в «01.МЕ»
    assert nz.index_from_text("Б1.О.01 МЕТОДОЛОГИЯ") == "Б1.О.01"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("108 (3)", (108.0, 3.0)),
        ("108(3)", (108.0, 3.0)),
        ("1 (1)", (1.0, 1.0)),
        ("144 (4)", (144.0, 4.0)),
        ("12", (12.0, None)),
        ("12,5", (12.5, None)),
        ("", (None, None)),
    ],
)
def test_parse_hours_ze(raw: str, expected: tuple[float | None, float | None]) -> None:
    assert nz.parse_hours_ze(raw) == expected


def test_parse_hours_ze_none() -> None:
    assert nz.parse_hours_ze(None) == (None, None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12", 12.0), ("12.0", 12.0), ("12,5", 12.5), ("", None), (None, None), ("abc", None),
     ("≈ 18 ч", 18.0)],
)
def test_to_float(value: object, expected: float | None) -> None:
    assert nz.to_float(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12", 12), (12.0, 12), ("12.6", 13), ("", None), (None, None)],
)
def test_to_int(value: object, expected: int | None) -> None:
    assert nz.to_int(value) == expected


def test_as_int_default() -> None:
    assert nz.as_int("", default=0) == 0
    assert nz.as_int(None, default=-1) == -1
    assert nz.as_int("7") == 7
