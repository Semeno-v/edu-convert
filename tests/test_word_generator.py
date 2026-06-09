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
    CompetencyGroup,
    CompetencyIndicator,
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
        competence_codes=("УК-1-И-1", "ПК-2-И-1"),
        competencies=(
            CompetencyGroup(code="УК-1", text="Способен критически мыслить",
                            indicators=(CompetencyIndicator(code="УК-1-И-1", text="Анализирует проблему"),)),
            CompetencyGroup(code="ПК-2", text="Способен моделировать",
                            indicators=(CompetencyIndicator(code="ПК-2-И-1", text="Строит модель"),)),
        ),
    )


def _lit_table() -> RichTable:
    def cell(t: str) -> RichTableCell:
        return RichTableCell(paragraphs=[RichParagraph(runs=[RichRun(text=t)])])
    head = RichTableRow(cells=[cell("№"), cell("Автор(ы)"), cell("Наименование"),
                               cell("Выходные данные"), cell("URL")])
    row = RichTableRow(cells=[cell("1"), cell("Иванов И.И."), cell("Книга про науку"),
                              cell("М., 2023. 200 с."), cell("URL: https://e.lib/1")])
    return RichTable(rows=[head, row])


@pytest.fixture
def content() -> ContentBlocks:
    block = ContentBlock(
        key="literature_main", title="Основная литература",
        elements=[ContentElement(kind=ElementKind.TABLE, table=_lit_table())],
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

    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8", "replace")
    # Литература переформатирована из таблицы в список — автор присутствует.
    assert "Иванов" in xml
    # Жёлтая подсветка заполненного присутствует.
    assert '<w:highlight w:val="yellow"' in xml


def test_competencies_built_from_base(
    generator: DocxtplGenerator, subject: SubjectData, tmp_path: Path
) -> None:
    # §2 строится из Базы (subject.competencies), даже при пустом ContentBlocks.
    out = tmp_path / "out_comp.docx"
    generator.generate(settings.rpd_template, out, subject, ContentBlocks(), DocType.RPD)
    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8", "replace")
    assert "Способен критически мыслить" in xml  # текст компетенции
    assert "Анализирует проблему" in xml          # текст индикатора
    assert "ПК-2" in xml                           # родительский код в §8


def test_generate_empty_block_placeholder(
    generator: DocxtplGenerator, subject: SubjectData, tmp_path: Path
) -> None:
    # Пустой контент -> subdoc с заглушкой, без ошибки рендеринга.
    out = tmp_path / "out_empty.docx"
    generator.generate(settings.rpd_template, out, subject, ContentBlocks(index="Б1.О.01"),
                       DocType.RPD)
    assert out.exists()


def test_generate_thematic_table_highlighted(
    generator: DocxtplGenerator, subject: SubjectData, tmp_path: Path
) -> None:
    # Контентная таблица (тематический план) переносится и подсвечивается жёлтым.
    table = RichTable(rows=[RichTableRow(cells=[
        RichTableCell(paragraphs=[RichParagraph(runs=[RichRun(text="Тема-АБВ")])]),
    ])])
    cb = ContentBlocks(blocks={"thematic_plan": ContentBlock(
        key="thematic_plan", title="ТП",
        elements=[ContentElement(kind=ElementKind.TABLE, table=table)])})
    out = tmp_path / "out_them.docx"
    generator.generate(settings.rpd_template, out, subject, cb, DocType.RPD)
    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8", "replace")
    assert "Тема-АБВ" in xml
    assert '<w:highlight w:val="yellow"' in xml


def test_generate_fos(
    generator: DocxtplGenerator, subject: SubjectData, content: ContentBlocks, tmp_path: Path
) -> None:
    out = tmp_path / "out_fos.docx"
    generator.generate(settings.fos_template, out, subject, content, DocType.FOS)
    assert out.exists()
    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8", "replace")
    assert "Б1.О.01" in xml  # индекс на титуле
