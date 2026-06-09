"""Тесты экстрактора Word (цель ≥95% покрытия, ТЗ §7.5).

Покрывают распознавание заголовков, конечный автомат блоков, преобразование в
IR (с сохранением форматирования), разбор старых чисел и извлечение индекса.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.core.exceptions import DocumentParseError
from app.core.models import DocType, ElementKind
from app.core.word_extractor import (
    WordExtractor,
    _heading_key,
    _opt_int,
    is_heading,
    para_to_rich,
    table_to_rich,
)


@pytest.fixture
def extractor() -> WordExtractor:
    return WordExtractor()


# --------------------------------------------------------------------------- #
#  Распознавание и классификация заголовков
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1. Объем дисциплины", True),
        ("3.Формирование компетентностной траектории", True),  # без пробела после номера
        ("4.1.1. Основная литература", True),
        ("8.1. Шкала оценивания", True),
        ("обычный абзац без номера", False),
        ("", False),
        ("1 2 3 4 5 6 7", True),  # начинается с числа — формально заголовок
        ("X" * 250, False),  # слишком длинный
    ],
)
def test_is_heading(text: str, expected: bool) -> None:
    assert is_heading(text) is expected


@pytest.mark.parametrize(
    ("text", "expected_key"),
    [
        ("2. Роль дисциплины в формировании компетенций", "competencies"),
        ("4.1.1. Основная литература", "literature_main"),
        ("4.1.2. Дополнительная литература", "literature_extra"),
        ("6. Программное обеспечение", "software"),
        ("5. Материально-техническое обеспечение", "facilities"),
        ("1.1 Контрольные вопросы для текущего контроля", "current_control"),
        ("3. Вопросы для государственной итоговой аттестации", "gia"),
        ("Цели освоения дисциплины", "goals"),
        ("Нечто непонятное про погоду", None),
    ],
)
def test_heading_key(text: str, expected_key: str | None) -> None:
    assert _heading_key(text) == expected_key




# --------------------------------------------------------------------------- #
#  Индекс
# --------------------------------------------------------------------------- #
def test_extract_index(extractor: WordExtractor, rpd_docx: Path) -> None:
    assert extractor.extract_index(rpd_docx) == "Б1.О.01"


def test_extract_index_from_table(extractor: WordExtractor, tmp_path: Path) -> None:
    doc = Document()
    t = doc.add_table(rows=1, cols=1)
    t.rows[0].cells[0].text = "Дисциплина Б1.В.05 Инфраструктура"
    path = tmp_path / "notitle.docx"
    doc.save(str(path))
    assert extractor.extract_index(path) == "Б1.В.05"


def test_extract_index_none(extractor: WordExtractor, empty_docx: Path) -> None:
    assert extractor.extract_index(empty_docx) is None


# --------------------------------------------------------------------------- #
#  Старые числа (для diff)
# --------------------------------------------------------------------------- #
def test_extract_old_numbers(extractor: WordExtractor, rpd_docx: Path) -> None:
    old = extractor.extract_old_numbers(rpd_docx)
    assert old.ze == 3.0
    assert old.hours_total == 108
    assert old.hours_lectures == 14
    assert old.hours_practical == 20
    assert old.semester == 1
    assert old.control_raw is not None and "Зачет" in old.control_raw


def test_extract_old_numbers_no_table(extractor: WordExtractor, empty_docx: Path) -> None:
    old = extractor.extract_old_numbers(empty_docx)
    assert old.ze is None
    assert old.hours_total is None


# --------------------------------------------------------------------------- #
#  Конечный автомат: текстовые блоки
# --------------------------------------------------------------------------- #
def test_extract_content_blocks(extractor: WordExtractor, rpd_docx: Path) -> None:
    content = extractor.extract(rpd_docx, DocType.RPD)
    assert content.index == "Б1.О.01"
    assert content.direction is not None and "09.04.03" in content.direction
    assert content.profile is not None
    assert content.form_study is not None and "очная" in content.form_study

    assert "competencies" in content.blocks
    assert "literature_main" in content.blocks
    assert "literature_extra" in content.blocks
    assert "software" in content.blocks


def test_competencies_block_has_table(extractor: WordExtractor, rpd_docx: Path) -> None:
    content = extractor.extract(rpd_docx, DocType.RPD)
    comp = content.get("competencies")
    assert comp is not None
    kinds = [e.kind for e in comp.elements]
    assert ElementKind.TABLE in kinds


def test_literature_preserves_bold(extractor: WordExtractor, rpd_docx: Path) -> None:
    content = extractor.extract(rpd_docx, DocType.RPD)
    main = content.get("literature_main")
    assert main is not None and not main.is_empty
    para = main.elements[0].paragraph
    assert para is not None
    assert any(run.bold for run in para.runs)  # «Иванов И.И.» жирным


def test_extract_empty_doc(extractor: WordExtractor, empty_docx: Path) -> None:
    content = extractor.extract(empty_docx, DocType.RPD)
    assert content.blocks == {}
    assert content.index is None


# --------------------------------------------------------------------------- #
#  IR-преобразования напрямую
# --------------------------------------------------------------------------- #
def test_para_to_rich_runs(tmp_path: Path) -> None:
    doc = Document()
    p = doc.add_paragraph()
    p.add_run("жирный").bold = True
    p.add_run(" обычный")
    rich = para_to_rich(p)
    assert rich.text == "жирный обычный"
    assert rich.runs[0].bold is True
    assert rich.runs[1].bold is False
    assert rich.list_level is None


def test_para_to_rich_captures_style(tmp_path: Path) -> None:
    doc = Document()
    p = doc.add_paragraph("элемент списка", style="List Bullet")
    rich = para_to_rich(p)
    assert rich.style == "List Bullet"


def test_list_level_with_numpr() -> None:
    doc = Document()
    p = doc.add_paragraph("элемент")
    pPr = p._p.get_or_add_pPr()
    numPr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "2")
    numPr.append(ilvl)
    pPr.append(numPr)
    assert para_to_rich(p).list_level == 2


def test_table_to_rich() -> None:
    doc = Document()
    t = doc.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "A"
    t.rows[0].cells[1].text = "B"
    t.rows[1].cells[0].text = "C"
    rich = table_to_rich(t)
    assert len(rich.rows) == 2
    assert rich.rows[0].cells[0].paragraphs[0].text == "A"


def test_open_corrupt_file(extractor: WordExtractor, tmp_path: Path) -> None:
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"not a real docx")
    with pytest.raises(DocumentParseError):
        extractor.extract_index(bad)


def test_old_numbers_header_only(extractor: WordExtractor, tmp_path: Path) -> None:
    # Таблица с нужной шапкой, но без числовой строки данных → пустой OldNumbers.
    doc = Document()
    doc.add_paragraph("1. Объем дисциплины")
    t = doc.add_table(rows=1, cols=3)
    t.rows[0].cells[0].text = "Общая трудоёмкость часов (ЗЕТ)"
    t.rows[0].cells[1].text = "Лекционные занятия"
    t.rows[0].cells[2].text = "Практические занятия"
    path = tmp_path / "header_only.docx"
    doc.save(str(path))
    old = extractor.extract_old_numbers(path)
    assert old.hours_total is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", None), ("12", 12), ("18 (5)", 18)],
)
def test_opt_int(value: str, expected: int | None) -> None:
    assert _opt_int(value) == expected


def test_list_level_numpr_without_ilvl() -> None:
    doc = Document()
    p = doc.add_paragraph("текст")
    pPr = p._p.get_or_add_pPr()
    pPr.append(OxmlElement("w:numPr"))  # numPr без ilvl → уровень 0
    assert para_to_rich(p).list_level == 0


def test_parse_hours_table_without_trudoemkost(extractor: WordExtractor) -> None:
    doc = Document()
    t = doc.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "Колонка"
    t.rows[0].cells[1].text = "Другая"
    t.rows[1].cells[0].text = "1"
    # столбца «трудоёмкость» нет → пустой результат
    assert extractor._parse_hours_table(t).hours_total is None


def test_heading_merge_same_key(extractor: WordExtractor, tmp_path: Path) -> None:
    # Повторный распознанный заголовок СЛИВАЕТСЯ в тот же блок (а не дублируется),
    # чтобы не терять контент при дублирующихся/оглавлениях-заголовках.
    doc = Document()
    doc.add_paragraph("6. Программное обеспечение")
    doc.add_paragraph("Первое ПО")
    doc.add_paragraph("7. Программное обеспечение второй раз")
    doc.add_paragraph("Второе ПО")
    path = tmp_path / "dup.docx"
    doc.save(str(path))
    content = extractor.extract(path, DocType.RPD)
    assert "software" in content.blocks
    assert not any(k.startswith("software_") for k in content.blocks)
    texts = [e.paragraph.text for e in content.blocks["software"].elements if e.paragraph]
    assert "Первое ПО" in texts and "Второе ПО" in texts


def test_unrecognized_numbered_heading_is_content(extractor: WordExtractor, tmp_path: Path) -> None:
    # Нумерованный пункт списка (не раздел) остаётся контентом текущего блока.
    doc = Document()
    doc.add_paragraph("6. Программное обеспечение")
    doc.add_paragraph("1. Какой-то вопрос списка?")
    doc.add_paragraph("2. Ещё вопрос списка?")
    path = tmp_path / "list.docx"
    doc.save(str(path))
    content = extractor.extract(path, DocType.RPD)
    texts = [e.paragraph.text for e in content.blocks["software"].elements if e.paragraph]
    assert "1. Какой-то вопрос списка?" in texts and "2. Ещё вопрос списка?" in texts
    assert len(content.blocks) == 1  # вопросы не создали новых блоков
