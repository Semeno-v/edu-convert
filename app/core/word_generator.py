"""Генерация целевого документа из шаблона docxtpl (ТЗ §4 Этап 2.6).

Соответствует одобренному эталонному формату:

* **Всё заполненное конвертацией выделяется жёлтым** (заливка шрифта). Статичные
  разделы шаблона (заголовки, §5/§6/§7) остаются без заливки.
* **§2** — компетенции и индикаторы строятся из Базы (лист «Компетенции»,
  :attr:`SubjectData.competencies`) как текстовые абзацы.
* **§3** — числа из Базы (подсветка задаётся в шаблоне на тегах), тематический
  план — из старого документа (best-effort).
* **§4** — литература переформатируется из таблицы старого документа в
  нумерованный список «Автор. Название. Выходные данные. URL».
* **§8** — «Формируемая компетенция» = родительские коды (ПК-1, ПК-2).

Подсветка скалярных значений (титул, часы, коды) задаётся в самом шаблоне
(жёлтый highlight на run-тегах), подсветка subdoc-контента — здесь.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx.enum.text import WD_COLOR_INDEX
from docxtpl import DocxTemplate

from app.config import settings
from app.core.exceptions import TemplateValidationError
from app.core.models import (
    ContentBlock,
    ContentBlocks,
    DocType,
    ElementKind,
    RichParagraph,
    RichTable,
    SubjectData,
)
from app.core.normalizer import normalize_text

_PLACEHOLDER = "Не предусмотрено."


class DocxtplGenerator:
    """Рендерер целевых документов на базе docxtpl."""

    def validate_template(self, template_path: Path, doc_type: DocType) -> None:
        tpl = DocxTemplate(str(template_path))
        try:
            found = tpl.get_undeclared_template_variables()
        except Exception:  # noqa: BLE001 — fallback на текстовый поиск тегов
            found = self._scan_tags(template_path)
        required = (
            settings.required_rpd_tags
            if doc_type == DocType.RPD
            else settings.required_fos_tags
        )
        missing = [tag for tag in required if tag not in found]
        if missing:
            raise TemplateValidationError(missing, template_path.name)

    @staticmethod
    def _scan_tags(template_path: Path) -> set[str]:
        import zipfile

        with zipfile.ZipFile(template_path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", "replace")
        text = re.sub(r"<[^>]+>", "", xml)
        return set(re.findall(r"\{\{\s*r?\s*([a-zA-Z_][a-zA-Z0-9_]*)", text))

    def generate(
        self,
        template_path: Path,
        out_path: Path,
        subject: SubjectData,
        content: ContentBlocks,
        doc_type: DocType,
    ) -> Path:
        tpl = DocxTemplate(str(template_path))
        context = self._build_context(tpl, subject, content, doc_type)
        tpl.render(context, autoescape=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tpl.save(str(out_path))
        return out_path

    # ------------------------------------------------------------------ #
    #  Сборка контекста
    # ------------------------------------------------------------------ #
    def _build_context(
        self,
        tpl: DocxTemplate,
        subject: SubjectData,
        content: ContentBlocks,
        doc_type: DocType,
    ) -> dict[str, object]:
        # Скалярные значения; их жёлтая подсветка задаётся в шаблоне на тегах.
        context: dict[str, object] = {
            "index": subject.index,
            "name": subject.name,
            "ze": _num(subject.ze),
            "hours_total": subject.hours_total,
            "hours_contact": subject.hours_contact,
            "hours_aud": subject.hours_aud,
            "hours_lectures": subject.hours_lectures,
            "hours_practical": subject.hours_practical,
            "hours_lab": subject.hours_lab or "-",
            "hours_project": subject.hours_project,
            "hours_extra_contact": max(subject.hours_contact - subject.hours_aud, 0),
            # «Часы самостоятельной работы» в форме = СРС + контроль (как в эталоне).
            "hours_self_study": subject.hours_srs + subject.hours_control,
            "control_summary": subject.control_summary,
            "semesters": ", ".join(str(s) for s in subject.semesters),
            "department": subject.department or "",
            "department_name": subject.department_name or "",
            # §8 — родительские коды компетенций (ПК-1, ПК-2).
            "competence_parents": ", ".join(subject.competence_parents),
            # Титул — из старого документа (с подсветкой в шаблоне).
            "direction": content.direction or "",
            "profile": content.profile or "",
            "form_study": content.form_study or "очная",
        }

        if doc_type == DocType.RPD:
            # §8: результаты обучения по уровням оценки — из §8 исходной РПД.
            outcomes = _assessment_outcomes(content.get("assessment"))
            for level in ("5", "4", "3", "2"):
                context["outcomes_" + level] = outcomes.get(level, "")
            context["competencies"] = self._competencies_subdoc(tpl, subject)
            context["indicators"] = self._indicators_subdoc(tpl, subject)
            context["thematic_plan"] = self._block_to_subdoc(
                tpl, content.get("thematic_plan"), empty_text=""
            )
            context["literature_main"] = self._literature_subdoc(tpl, content.get("literature_main"))
            context["literature_extra"] = self._literature_subdoc(tpl, content.get("literature_extra"))
            context["internet_resources"] = self._block_to_subdoc(
                tpl, content.get("internet_resources")
            )
        else:
            for key in ("current_control", "interim_attestation", "gia"):
                context[key] = self._block_to_subdoc(tpl, content.get(key))
        return context

    # ------------------------------------------------------------------ #
    #  §2 — компетенции и индикаторы из Базы (текстовые абзацы, жёлтые)
    # ------------------------------------------------------------------ #
    def _competencies_subdoc(self, tpl: DocxTemplate, subject: SubjectData):
        sd = tpl.new_subdoc()
        if not subject.competencies:
            self._add_text(sd, _PLACEHOLDER, highlight=True)
            return sd
        for group in subject.competencies:
            self._add_text(sd, f"{group.code} - {group.text}".strip(" -"), highlight=True)
        return sd

    def _indicators_subdoc(self, tpl: DocxTemplate, subject: SubjectData):
        sd = tpl.new_subdoc()
        indicators = [ind for g in subject.competencies for ind in g.indicators]
        if not indicators:
            self._add_text(sd, _PLACEHOLDER, highlight=True)
            return sd
        for ind in indicators:
            self._add_text(sd, f"{ind.code}. {ind.text}".strip(), highlight=True)
        return sd

    # ------------------------------------------------------------------ #
    #  §4 — литература: таблица старого документа → нумерованный список
    # ------------------------------------------------------------------ #
    def _literature_subdoc(self, tpl: DocxTemplate, block: ContentBlock | None):
        sd = tpl.new_subdoc()
        citations = _table_to_citations(block)
        if not citations:
            self._add_text(sd, _PLACEHOLDER, highlight=True)
            return sd
        for i, cite in enumerate(citations, 1):
            self._add_text(sd, f"{i}. {cite}", highlight=True)
        return sd

    # ------------------------------------------------------------------ #
    #  Общие subdoc-блоки (контент из старого документа, жёлтый)
    # ------------------------------------------------------------------ #
    def _block_to_subdoc(
        self, tpl: DocxTemplate, block: ContentBlock | None, empty_text: str = _PLACEHOLDER
    ):
        sd = tpl.new_subdoc()
        if block is None or block.is_empty:
            self._add_text(sd, empty_text, highlight=bool(empty_text))
            return sd
        for element in block.elements:
            if element.kind == ElementKind.PARAGRAPH and element.paragraph is not None:
                self._add_paragraph(sd, element.paragraph, highlight=True)
            elif element.kind == ElementKind.TABLE and element.table is not None:
                self._add_table(sd, element.table, highlight=True)
        return sd

    # ------------------------------------------------------------------ #
    #  Низкоуровневая вставка с подсветкой
    # ------------------------------------------------------------------ #
    @staticmethod
    def _hl(run, highlight: bool) -> None:
        if highlight:
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW

    def _add_text(self, sd, text: str, *, highlight: bool) -> None:
        run = sd.add_paragraph().add_run(text)
        self._hl(run, highlight)

    def _add_paragraph(self, sd, rich: RichParagraph, *, highlight: bool) -> None:
        style = "List Bullet" if rich.list_level is not None else None
        try:
            paragraph = sd.add_paragraph(style=style) if style else sd.add_paragraph()
        except KeyError:
            paragraph = sd.add_paragraph()
        for run in rich.runs:
            r = paragraph.add_run(run.text)
            r.bold, r.italic, r.underline = run.bold, run.italic, run.underline
            self._hl(r, highlight)

    def _add_table(self, sd, rich: RichTable, *, highlight: bool) -> None:
        if not rich.rows:
            return
        ncols = max((len(row.cells) for row in rich.rows), default=0)
        if ncols == 0:
            return
        table = sd.add_table(rows=len(rich.rows), cols=ncols)
        try:
            table.style = "Table Grid"
        except KeyError:
            pass
        for ri, row in enumerate(rich.rows):
            for ci, cell in enumerate(row.cells):
                if ci >= ncols:
                    continue
                tc = table.cell(ri, ci)
                tc.text = ""
                for pi, para in enumerate(cell.paragraphs):
                    p = tc.paragraphs[0] if pi == 0 else tc.add_paragraph()
                    for run in para.runs:
                        r = p.add_run(run.text)
                        r.bold, r.italic = run.bold, run.italic
                        self._hl(r, highlight)


def _cell_text(cell) -> str:
    return " ".join(p.text for p in cell.paragraphs).strip()


def _assessment_outcomes(block: ContentBlock | None) -> dict[str, str]:
    """Извлекает результаты обучения по уровням оценки из таблицы §8 исходной РПД.

    Возвращает словарь уровень→текст (через перевод строки):
    «5»=отлично, «4»=хорошо, «3»=удовлетворительно, «2»=неудовлетворительно.
    Для дисциплин с зачётом «Зачтено» раскладывается на 5/4/3, «Не зачтено» → 2.
    Источник результатов — последняя колонка таблицы («Формулировка требований»).
    """
    if block is None:
        return {}
    table = next((e.table for e in block.elements if e.table is not None), None)
    if table is None or len(table.rows) < 2:
        return {}
    grades: dict[str, list[str]] = {}
    for row in table.rows[1:]:
        if not row.cells:
            continue
        grade = _cell_text(row.cells[0])
        requirement = _cell_text(row.cells[-1])
        if grade and requirement:
            grades.setdefault(normalize_text(grade), []).append(requirement)

    out: dict[str, str] = {}
    for gnorm, reqs in grades.items():
        joined = "\n".join(dict.fromkeys(reqs))  # уникальные, по порядку
        if "неуд" in gnorm or "не зачт" in gnorm:
            out["2"] = joined
        elif "отл" in gnorm:
            out["5"] = joined
        elif "хор" in gnorm:
            out["4"] = joined
        elif "удовл" in gnorm:
            out["3"] = joined
        elif "зачт" in gnorm:  # зачёт → положительные уровни
            out.setdefault("5", joined)
            out.setdefault("4", joined)
            out.setdefault("3", joined)
    return out


def _table_to_citations(block: ContentBlock | None) -> list[str]:
    """Переформатирует таблицу литературы в список «Автор. Название. Изд. URL»."""
    if block is None:
        return []
    table = next((e.table for e in block.elements if e.table is not None), None)
    if table is None or len(table.rows) < 2:
        return []
    header = [_cell_text(c).lower() for c in table.rows[0].cells]

    def col(*keywords: str) -> int | None:
        return next((i for i, h in enumerate(header) if any(k in h for k in keywords)), None)

    ca, ct, co, cu = col("автор"), col("наименован", "назван"), col("выходн", "издат", "год"), col("url", "адрес", "ссылк", "доступ")
    citations: list[str] = []
    for row in table.rows[1:]:
        cells = [_cell_text(c) for c in row.cells]

        def g(i: int | None, _cells: list[str] = cells) -> str:
            return _cells[i].strip() if i is not None and i < len(_cells) else ""

        parts = [p for p in (g(ca), g(ct), g(co), g(cu)) if p]
        if g(ca) or g(ct):
            cite = re.sub(r"\.\s*\.", ".", ". ".join(parts))  # убираем двойные точки
            citations.append(cite)
    return citations


def _num(value: float) -> str | int:
    """3.0 → 3, 2.5 → 2.5 (убираем хвост .0 для целых з.е.)."""
    return int(value) if float(value).is_integer() else value
