"""Разметка официальных форм 2026 тегами docxtpl (этап B плана).

Берёт исходные пустые формы ГУУ (с редакторскими подписями) и порождает
размеченные шаблоны в ``templates/``:

* ``rpd_2026_tagged.docx`` — РПД;
* ``fos_2026_tagged.docx`` — ФОС.

Редакторские подписи («Из п. 2 Исходной РПД…», «Берём из учебного плана»)
заменяются тегами ``{{ }}``; пустые ячейки таблицы часов — тегами ``{{ hours_* }}``;
стандартные пред-заполненные разделы (ЭБС, ПО, помещения) остаются без изменений.

Скрипт идемпотентный и самодокументирующий: показывает, как именно получены
поставляемые шаблоны. Запуск::

    python -m tools.build_templates --rpd-src "Шаблон РП (2026) ММЭУ.docx" \
        --fos-src "ФОС_ШАБЛОН (2026) ММЭУ.docx"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

from app.core.normalizer import normalize_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"


# --------------------------------------------------------------------------- #
#  Утилиты редактирования docx
# --------------------------------------------------------------------------- #
def set_text(paragraph: Paragraph, text: str) -> None:
    """Заменяет весь текст абзаца одним runом (сохраняя стиль абзаца)."""
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    paragraph.add_run(text)


def clear(paragraph: Paragraph) -> None:
    set_text(paragraph, "")


def insert_after(paragraph: Paragraph, text: str) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    np = Paragraph(new_p, paragraph._parent)
    np.add_run(text)
    return np


def n(text: str) -> str:
    return normalize_text(text)


# --------------------------------------------------------------------------- #
#  РПД
# --------------------------------------------------------------------------- #
def tag_rpd(src: Path, dst: Path) -> None:
    doc = Document(str(src))

    # --- Абзацы: замена подписей на теги, очистка примеров --- #
    for p in doc.paragraphs:
        t = n(p.text)
        if not t:
            continue
        if "код и наименование дисциплины" in t and p.text.strip().isupper():
            set_text(p, "{{ index }} {{ name }}")
        elif t.startswith("по направлению подготовки"):
            set_text(p, "по направлению подготовки {{ direction }}")
        elif t.startswith("направленности"):
            set_text(p, "направленности (профиля) {{ profile }}")
        elif t.startswith("форма обучения"):
            set_text(p, "форма обучения {{ form_study }}")
        elif "цели в исходной программе нет" in t:
            set_text(p, "{{ goals }}")
        elif "из п. 2 исходной рпд (столбцы 2,3)" in t:
            set_text(p, "{{ competencies }}")
        elif "из п. 2 исходной рпд (столбец 4)" in t:
            clear(p)
        elif "из исходной рпд п.3" in t:
            # Тематический план заполняется автором по официальной структуре
            # (надёжного источника в старых РПД нет) — убираем редакторскую подпись.
            clear(p)
        elif "указать основную литературу" in t:
            set_text(p, "{{ literature_main }}")
        elif "указать дополнительную литературу" in t:
            set_text(p, "{{ literature_extra }}")
        elif "указать ресурсы сети интернет" in t:
            set_text(p, "{{ internet_resources }}")
        elif "берем из учебного плана" in t:
            clear(p)
        elif t.startswith("опк-1"):  # примеры компетенций/индикаторов
            clear(p)

    # --- Таблица часов: значения из Excel --- #
    _tag_hours_table(doc)

    # --- Остальные редакторские пометки (§3 тематический план, §8 оценивание) --- #
    _clean_editorial(doc)

    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dst))
    print(f"[РПД] {src.name} → {dst}")


def _clean_editorial(doc: Document) -> None:
    """Убирает/заполняет оставшиеся редакторские пометки в РПД.

    * §3: убирает инструкции «Указать несколько тем…» и «Проверка итого…»
      (тематический план заполняется автором по официальной пустой таблице);
    * §8: примечание «Исходная РПД п.п.8…» убирается, ячейки «Код/коды
      компетенций» → тег ``{{ competence_codes }}`` (из Базы), инструкции
      «(перечислить)» удаляются.
    """
    # Верхнеуровневые красные примечания.
    for p in doc.paragraphs:
        t = n(p.text)
        if "проверка итого" in t or "исходная рпд п. п. 8" in t or "столбцы 2 и 5" in t:
            clear(p)

    for table in doc.tables:
        header = n(" ".join(c.text for c in table.rows[0].cells))
        if "формируемая компетенция" in header:  # §8 «Система оценивания»
            for row in table.rows:
                for cell in row.cells:
                    ct = n(cell.text)
                    if "коды компетенци" in ct:
                        set_text(cell.paragraphs[0], "{{ competence_codes }}")
                        for extra in cell.paragraphs[1:]:
                            clear(extra)
                    else:
                        for p in cell.paragraphs:
                            for run in list(p.runs):
                                if "перечислить" in n(run.text):
                                    run._element.getparent().remove(run._element)
        else:  # §3 «Тематический план» и прочие
            for row in table.rows:
                for cell in row.cells:
                    if "указать несколько тем" in n(cell.text):
                        for p in cell.paragraphs:
                            clear(p)


def _tag_hours_table(doc: Document) -> None:
    # строка-метка (нормализованная) → имя тега для колонки «Всего» (c2) и «семестр» (c3)
    row_tags = {
        "зач. ед.": "{{ ze }}",
        "ак.ч.": "{{ hours_total }}",
        "часы контактной работы": "{{ hours_contact }}",
        "из них аудиторной работы": "{{ hours_aud }}",
        "лекции": "{{ hours_lectures }}",
        "практические занятия": "{{ hours_practical }}",
        "лабораторные занятия": "{{ hours_lab }}",
        "проектное обучение": "{{ hours_project }}",
        "часы внеаудиторной работы": "{{ hours_extra_contact }}",
        "часы самостоятельной работы": "{{ hours_srs }}",
        "вид промежуточной аттестации": "{{ control_summary }}",
    }
    for table in doc.tables:
        header = " ".join(c.text for c in table.rows[0].cells)
        if "Вид учебной работы" not in header:
            continue
        for row in table.rows:
            # «Общая трудоёмкость» в c0, а единица («зач. ед.»/«ак.ч.») — в c1
            label = n(row.cells[0].text + " " + (row.cells[1].text if len(row.cells) > 1 else ""))
            tag = next((v for k, v in row_tags.items() if k in label), None)
            if tag is None:
                continue
            # колонка «Всего» = индекс 2; «в семестре» = 3 (для односеместровых равны)
            if len(row.cells) > 2:
                set_text(row.cells[2].paragraphs[0], tag)
            if len(row.cells) > 3 and "{{ control" not in tag:
                set_text(row.cells[3].paragraphs[0], tag)
        break


# --------------------------------------------------------------------------- #
#  ФОС
# --------------------------------------------------------------------------- #
def tag_fos(src: Path, dst: Path) -> None:
    doc = Document(str(src))
    gia_heading: Paragraph | None = None

    for p in doc.paragraphs:
        t = n(p.text)
        if not t:
            continue
        if t == "код наименование":
            set_text(p, "{{ index }} {{ name }}")
        elif t.startswith("по направлению подготовки"):
            set_text(p, "по направлению подготовки {{ direction }}")
        elif t.startswith("направленности"):
            set_text(p, "направленности (профиля) {{ profile }}")
        elif t.startswith("форма обучения"):
            set_text(p, "форма обучения {{ form_study }}")
        elif "примерный перечень задач" in t:
            set_text(p, "{{ current_control }}")
        elif "примерный состав тестовых вопросов" in t:
            set_text(p, "{{ interim_attestation }}")
        elif t.startswith("задачи к разделу") or t.startswith("задача") or t == "ответ:":
            clear(p)
        elif "обязательно с ответами" in t:
            clear(p)
        elif "государственной итоговой" in t:
            gia_heading = p

    if gia_heading is not None:
        insert_after(gia_heading, "{{ gia }}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dst))
    print(f"[ФОС] {src.name} → {dst}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Разметка шаблонов 2026 тегами docxtpl")
    ap.add_argument("--rpd-src", default=str(PROJECT_ROOT / "Шаблон РП (2026) ММЭУ.docx"))
    ap.add_argument("--fos-src", default=str(PROJECT_ROOT / "ФОС_ШАБЛОН (2026) ММЭУ.docx"))
    args = ap.parse_args()

    tag_rpd(Path(args.rpd_src), TEMPLATES_DIR / "rpd_2026_tagged.docx")
    tag_fos(Path(args.fos_src), TEMPLATES_DIR / "fos_2026_tagged.docx")


if __name__ == "__main__":
    main()
