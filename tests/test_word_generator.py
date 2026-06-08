"""Тесты генератора docxtpl (core/word_generator.py).

Покрывают валидацию шаблона (обе ветки), рендеринг с числами из Excel
(золотое правило), вставку текстового блока и форматирование чисел.
Используются поставляемые размеченные шаблоны templates/*.docx.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from docx import Document

from app.config import settings
from app.core.exceptions import TemplateValidationError
from app.core.models import (
    ContentBlock,
    ContentBlocks,
    ContentElement,
    ControlForm,
    ControlKind,
    DocType,
    ElementKind,
    RichParagraph,
    RichRun,
    RichTable,
    RichTableCell,
    RichTableRow,
    SubjectData,
)
from app.core.word_generator import DocxtplGenerator, _num


@pytest.fixture
def generator() -> DocxtplGenerator:
    return DocxtplGenerator()


@pytest.fixture
def subject() -> SubjectData:
    return SubjectData(
        index="Б1.О.01", name="Тестовая дисциплина", ze=3.0, hours_total=108,
        hours_contact=30, hours_aud=28, hours_lectures=12, hours_practical=10,
        hours_lab=0, hours_project=6, hours_srs=78, hours_control=0,
        control_forms=(ControlForm(kind=ControlKind.CREDIT, semester=1),),
    )


@pytest.fixture
def content() -> ContentBlocks:
    block = ContentBlock(
        key="literature_main", title="Основная литература",
        elements=[ContentElement(
            kind=ElementKind.PARAGRAPH,
            paragraph=RichParagraph(runs=[RichRun(text="Иванов И.И. Книга.", bold=True)]),
        )],
    )
    return ContentBlocks(index="Б1.О.01", direction="09.04.03", profile="Профиль",
                         form_study="очная", blocks={"literature_main": block})


@pytest.mark.parametrize(("value", "expected"), [(3.0, 3), (2.5, 2.5), (6, 6), (4.0, 4)])
def test_num_formatting(value: float, expected: object) -> None:
    assert _num(value) == expected


def test_validate_template_ok(generator: DocxtplGenerator) -> None:
    # На поставляемых размеченных шаблонах валидация проходит без исключений.
    generator.validate_template(settings.rpd_template, DocType.RPD)
    generator.validate_template(settings.fos_template, DocType.FOS)


def test_validate_template_missing_tags(generator: DocxtplGenerator, tmp_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("Документ без обязательных тегов")
    bad = tmp_path / "bad_template.docx"
    doc.save(str(bad))
    with pytest.raises(TemplateValidationError):
        generator.validate_template(bad, DocType.RPD)


def test_generate_uses_excel_numbers(
    generator: DocxtplGenerator, subject: SubjectData, content: ContentBlocks, tmp_path: Path
) -> None:
    out = tmp_path / "out.docx"
    generator.generate(settings.rpd_template, out, subject, content, DocType.RPD)
    assert out.exists()

    doc = Document(str(out))
    hours: dict[str, str] = {}
    for table in doc.tables:
        if "Вид учебной работы" in " ".join(c.text for c in table.rows[0].cells):
            for row in table.rows:
                label = row.cells[0].text.strip()
                val = row.cells[2].text.strip() if len(row.cells) > 2 else ""
                if label == "Лекции":
                    hours["lec"] = val
                elif label == "Практические занятия":
                    hours["pr"] = val
    # Числа строго из Excel (SubjectData), не из Word.
    assert hours.get("lec") == "12"
    assert hours.get("pr") == "10"

    # Текстовый блок перенесён в документ.
    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8", "replace")
    assert "Иванов" in xml


def test_generate_empty_block_placeholder(
    generator: DocxtplGenerator, subject: SubjectData, tmp_path: Path
) -> None:
    # Пустой контент -> subdoc с заглушкой, без ошибки рендеринга.
    out = tmp_path / "out_empty.docx"
    generator.generate(settings.rpd_template, out, subject, ContentBlocks(index="Б1.О.01"),
                       DocType.RPD)
    assert out.exists()


def test_generate_with_table_and_list(
    generator: DocxtplGenerator, subject: SubjectData, tmp_path: Path
) -> None:
    # Блок с таблицей и элементом списка — покрывает _add_table и список в _add_paragraph.
    table = RichTable(rows=[RichTableRow(cells=[
        RichTableCell(paragraphs=[RichParagraph(runs=[RichRun(text="Код")])]),
        RichTableCell(paragraphs=[RichParagraph(runs=[RichRun(text="Наименование")])]),
    ])])
    block = ContentBlock(key="competencies", title="Компетенции", elements=[
        ContentElement(kind=ElementKind.TABLE, table=table),
        ContentElement(kind=ElementKind.PARAGRAPH,
                       paragraph=RichParagraph(runs=[RichRun(text="пункт списка")], list_level=0)),
    ])
    cb = ContentBlocks(index="Б1.О.01", blocks={"competencies": block})
    out = tmp_path / "out_table.docx"
    generator.generate(settings.rpd_template, out, subject, cb, DocType.RPD)
    assert out.exists()
    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8", "replace")
    assert "Наименование" in xml and "пункт списка" in xml


def test_generate_fos(
    generator: DocxtplGenerator, subject: SubjectData, content: ContentBlocks, tmp_path: Path
) -> None:
    out = tmp_path / "out_fos.docx"
    generator.generate(settings.fos_template, out, subject, content, DocType.FOS)
    assert out.exists()
    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8", "replace")
    assert "Б1.О.01" in xml  # индекс на титуле
