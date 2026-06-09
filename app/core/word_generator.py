"""Генерация целевого документа из шаблона docxtpl (ТЗ §4 Этап 2.6).

Контекст рендера собирается строго из Pydantic-моделей:

* **числа** — из :class:`SubjectData` (источник истины, Excel);
* **текст** — из :class:`ContentBlocks` (старый Word), причём каждый смысловой
  блок превращается в *subdoc* (вложенный документ) для сохранения структуры —
  списков, жирного шрифта, таблиц.

Реализация :class:`~app.core.interfaces.DocumentGenerator`.
"""

from __future__ import annotations

from pathlib import Path

from docxtpl import DocxTemplate

from app.config import settings
from app.core.exceptions import TemplateValidationError
from app.core.models import (
    ContentBlock,
    ContentBlocks,
    DocType,
    ElementKind,
    RichParagraph,
    SubjectData,
)

# Какие блоки контента вставляются в каждый тип документа (ключ блока → имя тега).
# Стандартные пред-заполненные разделы шаблона (ЭБС, ПО, помещения) НЕ трогаем
# (решение пользователя), поэтому здесь только размечаемые теги.
_RPD_BLOCK_TAGS = {
    "goals": "goals",
    "competencies": "competencies",
    "literature_main": "literature_main",
    "literature_extra": "literature_extra",
    "internet_resources": "internet_resources",
}
_FOS_BLOCK_TAGS = {
    "current_control": "current_control",
    "interim_attestation": "interim_attestation",
    "gia": "gia",
}


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
        import re
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
        # --- Числа (источник истины — Excel) --- #
        context: dict[str, object] = {
            "index": subject.index,
            "name": subject.name,
            "ze": _num(subject.ze),
            "hours_total": subject.hours_total,
            "hours_contact": subject.hours_contact,
            "hours_aud": subject.hours_aud,
            "hours_lectures": subject.hours_lectures,
            "hours_practical": subject.hours_practical,
            "hours_lab": subject.hours_lab,
            "hours_project": subject.hours_project,
            "hours_srs": subject.hours_srs,
            "hours_control": subject.hours_control,
            # консультации / иная контактная работа = контактная − аудиторная
            "hours_extra_contact": max(subject.hours_contact - subject.hours_aud, 0),
            "control_summary": subject.control_summary,
            "semesters": ", ".join(str(s) for s in subject.semesters),
            "department": subject.department or "",
            # Коды компетенций из Базы — для §8 «Система оценивания».
            "competence_codes": "; ".join(subject.competence_codes),
            # --- Метаданные титула (текст из старого документа) --- #
            "direction": content.direction or "",
            "profile": content.profile or "",
            "form_study": content.form_study or "очная",
            "per_semester": subject.per_semester,
        }

        # --- Текстовые блоки (subdoc) --- #
        tag_map = _RPD_BLOCK_TAGS if doc_type == DocType.RPD else _FOS_BLOCK_TAGS
        for block_key, tag in tag_map.items():
            block = content.get(block_key)
            context[tag] = self._block_to_subdoc(tpl, block)
        return context

    def _block_to_subdoc(self, tpl: DocxTemplate, block: ContentBlock | None):
        """Строит subdoc из IR блока (пустой, если блока нет)."""
        sd = tpl.new_subdoc()
        if block is None or block.is_empty:
            sd.add_paragraph("Не предусмотрено программой / нет данных в исходном файле.")
            return sd
        for element in block.elements:
            if element.kind == ElementKind.PARAGRAPH and element.paragraph is not None:
                self._add_paragraph(sd, element.paragraph)
            elif element.kind == ElementKind.TABLE and element.table is not None:
                self._add_table(sd, element.table)
        return sd

    @staticmethod
    def _add_paragraph(sd, rich: RichParagraph) -> None:
        style = "List Bullet" if rich.list_level is not None else None
        try:
            paragraph = sd.add_paragraph(style=style) if style else sd.add_paragraph()
        except KeyError:
            paragraph = sd.add_paragraph()
        for run in rich.runs:
            r = paragraph.add_run(run.text)
            r.bold = run.bold
            r.italic = run.italic
            r.underline = run.underline

    def _add_table(self, sd, rich) -> None:
        if not rich.rows:
            return
        ncols = max((len(row.cells) for row in rich.rows), default=0)
        if ncols == 0:
            return
        table = sd.add_table(rows=len(rich.rows), cols=ncols)
        try:
            table.style = "Table Grid"
        except KeyError:  # стиль отсутствует в базовом шаблоне subdoc
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
                        r.bold = run.bold
                        r.italic = run.italic


def _num(value: float) -> str | int:
    """3.0 → 3, 2.5 → 2.5 (убираем хвост .0 для целых з.е.)."""
    return int(value) if float(value).is_integer() else value
