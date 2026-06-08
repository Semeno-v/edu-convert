"""Сравнение старых чисел (Word) с эталоном (Excel) — отчёт о расхождениях.

Реализует «золотое правило»: числа в новый документ берутся из Excel, а старые
значения из Word используются **только** для фиксации расхождений (ТЗ §4 Этап 2.4,
§8). Политика сравнения (какие поля и как сравнивать) собрана здесь, чтобы её
можно было настроить под нужды кафедры, не трогая оркестратор.
"""

from __future__ import annotations

from app.core.models import DiffRecord, OldNumbers, SubjectData
from app.core.normalizer import normalize_text

# Числовые поля: (человекочитаемое имя, атрибут OldNumbers, атрибут SubjectData)
_NUMERIC_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("Зачётные единицы (з.е.)", "ze", "ze"),
    ("Всего часов", "hours_total", "hours_total"),
    ("Лекции, часов", "hours_lectures", "hours_lectures"),
    ("Практические, часов", "hours_practical", "hours_practical"),
    ("Лабораторные, часов", "hours_lab", "hours_lab"),
    ("Проектное обучение, часов", "hours_project", "hours_project"),
)

# Ключевые слова форм контроля для нечёткого сравнения «Зачёт»/«Экзамен».
_CONTROL_KEYWORDS = ("экзамен", "зачет с оценкой", "зачет")


def compute_diffs(old: OldNumbers, subject: SubjectData) -> list[DiffRecord]:
    """Возвращает список расхождений между старыми числами и эталоном.

    Расхождение фиксируется, только если старое значение присутствует и
    отличается от эталона (числа сравниваются как числа, формы контроля и
    семестр — по смыслу).
    """
    diffs: list[DiffRecord] = []

    for label, old_attr, new_attr in _NUMERIC_FIELDS:
        old_val = getattr(old, old_attr)
        new_val = getattr(subject, new_attr)
        if old_val is None:
            continue
        if float(old_val) != float(new_val):
            diffs.append(
                DiffRecord(field=label, old_value=_fmt(old_val), new_value=_fmt(new_val))
            )

    # Семестр: старое значение должно входить в множество семестров эталона.
    if old.semester is not None and subject.semesters:
        if old.semester not in subject.semesters:
            diffs.append(
                DiffRecord(
                    field="Семестр",
                    old_value=str(old.semester),
                    new_value=", ".join(str(s) for s in subject.semesters),
                )
            )

    # Форма контроля: вид (экзамен/зачёт) из старого файла должен встречаться
    # в эталонной сводке форм контроля.
    if old.control_raw and subject.control_forms:
        old_kind = _control_kind(old.control_raw)
        new_norm = normalize_text(subject.control_summary)
        if old_kind and old_kind not in new_norm:
            diffs.append(
                DiffRecord(
                    field="Форма контроля",
                    old_value=old.control_raw.strip(),
                    new_value=subject.control_summary,
                )
            )

    return diffs


def _control_kind(raw: str) -> str | None:
    norm = normalize_text(raw)
    for kw in _CONTROL_KEYWORDS:
        if kw in norm:
            return kw
    return None


def _fmt(value: float | int) -> str:
    """Форматирует число без лишнего хвоста .0 (3.0 → «3»)."""
    fval = float(value)
    return str(int(fval)) if fval.is_integer() else str(fval)
